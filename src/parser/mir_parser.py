from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from .base_parser import BaseParser
from .model import Block, Function, RawBlock, YK_TRACE_BASICBLOCK_FUNC

if TYPE_CHECKING:
    from report.report import SummaryReport


class MIRParser(BaseParser):
    """Parser for LLVM MIR (Machine IR) files."""

    def __init__(self, allowed_functions: set[str] | None = None):
        """Initialize MIR parser.
        
        Args:
            allowed_functions: Optional set of function names to include.
        """
        super().__init__(allowed_functions)

    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse MIR file and return functions with basic block details."""
        blocks = self._extract_blocks(filename, skip_patterns)
        functions: Dict[str, Function] = {}

        for rb in blocks:
            blk = self._parse_basic_block(rb.lines)
            if blk.instructions <= 0:
                continue
            blk.start_line = rb.start_line  # Set the line number from RawBlock
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

        self.functions = functions
        self._apply_allowed_functions_filter()
        return self.functions

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

        # Collect ALL instruction lines (including pseudo-ops) for display
        all_instructions: List[str] = []
        
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
            # Skip YAML document separators
            if s == "..." or s == "---":
                continue

            # Add to all_instructions for display
            all_instructions.append(ln)

            # Skip MIR metadata and pseudo-instructions that don't correspond to real machine code.
            # This emulates LLVM's MachineInstr predicates for text-based MIR parsing:
            #   !MI.isDebugInstr() && !MI.isPseudo() && !MI.isMetaInstruction() &&
            #   !MI.isPosition() && !MI.isPseudoProbe() &&
            #   !MI.getFlag(MachineInstr::FrameSetup) && !MI.getFlag(MachineInstr::FrameDestroy)

            # Extract first token (instruction opcode)
            first_token = s.split()[0] if s.split() else ""
            # Remove trailing ':' if present (for instruction definitions)
            first_token_clean = first_token.rstrip(':')

            if (s.startswith("successors:") or s.startswith("predecessors:") or
                s.startswith("liveins:") or s.startswith("Frame Objects") or
                s.startswith("Function Live Ins") or s.startswith("fi#") or
                s.startswith("frame-setup ") or s.startswith("frame-destroy ") or
                s.startswith("CFI_INSTRUCTION") or
                # Debug instructions (!MI.isDebugInstr())
                s.startswith("DBG_VALUE") or s.startswith("DBG_LABEL") or
                s.startswith("DBG_PHI") or s.startswith("DBG_INSTR_REF") or
                # Debug variants (instructions with _DB suffix)
                first_token_clean.endswith("_DB") or
                 ("DBG_VALUE" in s.split()[0] if s.split() else False) or
                # Pseudo-instructions and meta instructions (!MI.isPseudo(), !MI.isMetaInstruction())
                s.startswith("IMPLICIT_DEF") or s.startswith("KILL") or
                s.startswith("COPY") or  # Register copy pseudo-instruction
                s.startswith("LIFETIME_START") or s.startswith("LIFETIME_END") or
                s.startswith("STACKMAP") or s.startswith("PATCHPOINT") or
                s.startswith("STATEPOINT") or
                # Inline assembly markers
                s.startswith("INLINEASM") or
                # Zero-setting pseudo-instructions
                s.startswith("MOV32r0") or s.startswith("V_SET0") or
                s.startswith("FsFLD0SD") or
                # Position markers (!MI.isPosition())
                s.startswith("EH_LABEL") or s.startswith("GC_LABEL") or
                s.startswith("ANNOTATION_LABEL") or
                # Profiling pseudo-probes (!MI.isPseudoProbe())
                s.startswith("PSEUDO_PROBE") or
                # Stack frame pseudo-operations (!MI.getFlag(FrameSetup/FrameDestroy))
                s.startswith("ADJCALLSTACKDOWN") or s.startswith("ADJCALLSTACKUP")):

                continue

            collected.append(ln)

        # Count __yk_trace_basicblock calls (in all instructions)
        yk_trace_bb_calls = sum(1 for ln in all_instructions if YK_TRACE_BASICBLOCK_FUNC in ln)
        
        # Return block with:
        # - instructions: real instruction count (INCLUDING trace calls, excluding pseudo-ops)
        # - instruction_lines: ALL instructions including pseudo-ops
        # - total_instructions: count of all instructions (including pseudo-ops AND trace calls)
        # - yk_trace_bb_calls: separate count of trace calls for statistics
        return Block(
            block=label,
            instructions=len(collected),  # Real instructions INCLUDING trace calls
            instruction_lines=all_instructions,  # ALL instructions for display
            text=text,
            yk_trace_bb_calls=yk_trace_bb_calls,
            total_instructions=len(all_instructions)  # Total including pseudo-ops AND trace calls
        )

    def _extract_blocks(self, filename: str, skip_patterns: List[str] | None) -> List[RawBlock]:
        """Extract raw basic blocks from MIR file.
        
        Supports two MIR formats:
        1. YAML format with "name: <function>" and "body: |" sections
        2. Legacy format with "# Machine code for function <name>:" comments
        """
        func_mir_machine_code_re = re.compile(r'#\s*Machine code for function\s+(\S+):')
        func_yaml_name_re = re.compile(r'^name:\s+(\S+)')
        bb_mir_re = re.compile(r'^\s*bb\.(\d+)\b')

        current_function: str | None = None
        blocks: List[RawBlock] = []
        current_block_lines: List[str] | None = None
        current_block_start_line: int = 0
        synth_function_name = Path(filename).name
        line_number = 0

        with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
            for raw_line in f:
                line_number += 1
                line = raw_line.rstrip('\n')

                # Match "name: <function>" (YAML format)
                m_yaml_name = func_yaml_name_re.match(line)
                if m_yaml_name:
                    # Flush previous block if any
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=(current_function or synth_function_name), 
                                             in_mir=True, lines=current_block_lines, start_line=current_block_start_line))
                        current_block_lines = None
                    current_function = m_yaml_name.group(1)
                    continue

                # Match "# Machine code for function <name>:" (legacy format)
                m_mir_mc = func_mir_machine_code_re.search(line)
                if m_mir_mc:
                    current_function = m_mir_mc.group(1)
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=True, lines=current_block_lines, 
                                             start_line=current_block_start_line))
                        current_block_lines = None
                    continue

                # MIR block start
                if bb_mir_re.match(line):
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=True, 
                                             lines=current_block_lines, start_line=current_block_start_line))
                    current_block_lines = [line]
                    current_block_start_line = line_number
                    if current_function is None:
                        current_function = synth_function_name
                    continue

                # Accumulate lines
                if current_block_lines is not None:
                    current_block_lines.append(line)

            # EOF flush
            if current_block_lines is not None:
                blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=True,
                                     lines=current_block_lines, start_line=current_block_start_line))

        # Apply skip filters
        if skip_patterns:
            filtered: List[RawBlock] = []
            for rb in blocks:
                if any(pat in (rb.function_name or "") for pat in skip_patterns):
                    continue
                filtered.append(rb)
            return filtered

        return blocks

    def apply_func_type_filter(self, filename: str, func_type: str,
                               skip_patterns: List[str] | None = None,
                               skip_prefixes: List[str] | None = None) -> None:
        """Apply function type filtering for MIR.

        MIR has only defined functions; declared-only results in empty map.

        Args:
            filename: Path to the MIR file (unused, for API consistency)
            func_type: Type of functions to include ('defined', 'declared', 'all')
            skip_patterns: Skip functions (unused, for API consistency)
            skip_prefixes: Skip prefixes (unused, for API consistency)
        """
        if func_type == 'declared':
            # MIR has only defined functions; declared-only => empty map
            self.functions = {}

    def create_summary_report(self) -> 'SummaryReport':
        """Create a summary report including MIR-specific metrics."""
        # Get base report from parent
        report = super().create_summary_report()

        # Compute and add __yk_trace_basicblock statistics
        report.yk_trace_stats = self._compute_yk_trace_stats()

        return report

