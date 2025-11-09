from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .base_parser import BaseParser
from .model import Block, Function, RawBlock


class MIRParser(BaseParser):
    """Parser for LLVM MIR (Machine IR) files."""

    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse MIR file and return functions with basic block details."""
        blocks = self._extract_blocks(filename, skip_patterns)
        functions: Dict[str, Function] = {}

        for rb in blocks:
            blk = self._parse_basic_block(rb.lines)
            if blk.instructions <= 0:
                continue
            fn = functions.get(rb.function_name)
            if fn is None:
                fn = Function(name=rb.function_name)
                functions[rb.function_name] = fn
            if not blk.block:
                first = next((ln for ln in rb.lines if ln.strip()), "")
                blk.block = (first.split(":", 1)[0].strip() if first else "")
            fn.blocks += 1
            fn.total_instructions += blk.instructions
            fn.blocks_detail.append(blk)

        # Apply prefix filtering
        if skip_prefixes:
            for fn_name in list(functions.keys()):
                if any(fn_name.startswith(p) for p in skip_prefixes):
                    del functions[fn_name]

        return functions

    def _parse_basic_block(self, block_lines: List[str]) -> Block:
        """Parse a MIR basic block."""
        label = ""
        text = "\n".join(block_lines) if block_lines else ""
        collected: List[str] = []

        # Find MIR label line
        label_line: str | None = None
        bb_label_re = re.compile(r"^\s*bb\.\d+\b")
        for ln in block_lines:
            if bb_label_re.match(ln):
                label_line = ln
                break

        # Extract label string
        if label_line:
            # Extract bb.N from "bb.N (%ir-block.X):" or "bb.N:"
            label_raw = label_line.split(":", 1)[0].strip()
            if ' ' in label_raw:
                label = label_raw.split()[0]  # Take only bb.N
            else:
                label = label_raw

        for ln in block_lines:
            s = ln.strip()
            if not s:
                continue
            if label_line and ln == label_line:
                continue
            if s.startswith(";") or s.startswith("#") or s.startswith("!"):
                continue
            if s == '"':
                continue

            # Skip MIR metadata and pseudo-instructions that don't correspond to real machine code.
            # This emulates LLVM's MachineInstr predicates for text-based MIR parsing:
            #   !MI.isDebugInstr() && !MI.isPseudo() && !MI.isMetaInstruction() &&
            #   !MI.isPosition() && !MI.isPseudoProbe() &&
            #   !MI.getFlag(MachineInstr::FrameSetup) && !MI.getFlag(MachineInstr::FrameDestroy)
            if (s.startswith("successors:") or s.startswith("predecessors:") or
                s.startswith("liveins:") or s.startswith("Frame Objects") or
                s.startswith("Function Live Ins") or s.startswith("fi#") or
                s.startswith("frame-setup ") or s.startswith("frame-destroy ") or
                s.startswith("CFI_INSTRUCTION") or
                # Debug instructions (!MI.isDebugInstr())
                s.startswith("DBG_VALUE") or s.startswith("DBG_LABEL") or
                s.startswith("DBG_PHI") or s.startswith("DBG_INSTR_REF") or
                ("DBG_VALUE" in s.split()[0] if s.split() else False) or
                # Pseudo-instructions and meta instructions (!MI.isPseudo(), !MI.isMetaInstruction())
                s.startswith("IMPLICIT_DEF") or s.startswith("KILL") or
                s.startswith("LIFETIME_START") or s.startswith("LIFETIME_END") or
                s.startswith("STACKMAP") or s.startswith("PATCHPOINT") or
                s.startswith("STATEPOINT") or
                # Position markers (!MI.isPosition())
                s.startswith("EH_LABEL") or s.startswith("GC_LABEL") or
                s.startswith("ANNOTATION_LABEL") or
                # Profiling pseudo-probes (!MI.isPseudoProbe())
                s.startswith("PSEUDO_PROBE") or
                # Stack frame pseudo-operations (!MI.getFlag(FrameSetup/FrameDestroy))
                s.startswith("ADJCALLSTACKDOWN") or s.startswith("ADJCALLSTACKUP")):
                continue

            collected.append(ln)

        return Block(block=label, instructions=len(collected), instruction_lines=collected, text=text)

    def _extract_blocks(self, filename: str, skip_patterns: List[str] | None) -> List[RawBlock]:
        """Extract raw basic blocks from MIR file."""
        func_mir_re = re.compile(r'^\s*Function:\s*(\S+)')
        func_mir_machine_code_re = re.compile(r'#\s*Machine code for function\s+(\S+):')
        bb_mir_re = re.compile(r'^\s*bb\.(\d+)\b')

        current_function: str | None = None
        blocks: List[RawBlock] = []
        current_block_lines: List[str] | None = None
        synth_function_name = Path(filename).name

        with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
            for raw_line in f:
                line = raw_line.rstrip('\n')

                m_mir = func_mir_re.match(line)
                if m_mir:
                    current_function = m_mir.group(1)
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=True, lines=current_block_lines))
                        current_block_lines = None
                    continue

                # Alternative MIR format: "# Machine code for function <name>:"
                m_mir_mc = func_mir_machine_code_re.search(line)
                if m_mir_mc:
                    current_function = m_mir_mc.group(1)
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=True, lines=current_block_lines))
                        current_block_lines = None
                    continue

                # MIR block start
                if bb_mir_re.match(line):
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=True, lines=current_block_lines))
                    current_block_lines = [line]
                    if current_function is None:
                        current_function = synth_function_name
                    continue

                # Accumulate lines
                if current_block_lines is not None:
                    current_block_lines.append(line)

            # EOF flush
            if current_block_lines is not None:
                blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=True, lines=current_block_lines))

        # Apply skip filters
        if skip_patterns:
            filtered: List[RawBlock] = []
            for rb in blocks:
                if any(pat in (rb.function_name or "") for pat in skip_patterns):
                    continue
                filtered.append(rb)
            return filtered

        return blocks

