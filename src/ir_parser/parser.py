from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List

from .model import Block, Function, RawBlock


def parse_basic_block(block_lines: List[str], in_mir: bool) -> Block:
    label = ""
    text = "\n".join(block_lines) if block_lines else ""
    collected: List[str] = []

    # Determine label line, adaptively
    label_line: str | None = None
    effective_in_mir = in_mir
    if effective_in_mir:
        bb_label_re = re.compile(r"^\s*bb\.\d+\b")
        for ln in block_lines:
            if bb_label_re.match(ln):
                label_line = ln
                break
    # Fallback: treat as IR-style label if no MIR label detected
    if label_line is None:
        first = next((ln for ln in block_lines if ln.strip()), "")
        if first:
            label_line = first
            s = first.strip()
            idx = s.find(":")
            if idx > 0 and "=" not in s[:idx]:
                effective_in_mir = False

    # Extract label string
    if label_line:
        if effective_in_mir:
            label = label_line.split(":", 1)[0].strip()
        else:
            stripped = label_line.strip()
            colon_idx = stripped.find(":")
            if colon_idx > 0 and "=" not in stripped[:colon_idx]:
                label = stripped[:colon_idx].strip()
            else:
                label = stripped

    in_switch = False
    for ln in block_lines:
        s = ln.strip()
        if not s:
            continue
        # Skip the label line itself
        if label_line and ln == label_line:
            continue
        # Skip debug/module info that may be embedded in block text by dumps
        if (
            s.startswith('source_filename') or
            'target datalayout' in s or
            s.startswith('target datalayout') or
            s.startswith('target triple') or
            s.startswith('!target triple')
        ):
            continue
        if s.startswith(";") or s.startswith("#"):
            continue
        if s.startswith("!"):
            continue
        # Skip dangling quote-only lines from broken string literals in dumps
        if s == '"':
            continue
        # Treat entire IR switch with case list as a single instruction
        if in_switch:
            if ']' in s:
                in_switch = False
            continue
        if s.startswith('switch '):
            collected.append(ln)
            in_switch = True
            continue
        if effective_in_mir and (
            s.startswith("successors:") or
            s.startswith("predecessors:") or
            s.startswith("liveins:") or
            s.startswith("Frame Objects") or
            s.startswith("Function Live Ins") or
            s.startswith("fi#")
        ):
            continue
        collected.append(ln)

    return Block(block=label, instructions=len(collected), instruction_lines=collected, text=text)


def _is_ir_block_label(line_stripped: str) -> str | None:
    if not line_stripped or line_stripped.startswith(';'):
        return None
    colon_idx = line_stripped.find(':')
    if colon_idx <= 0:
        return None
    before = line_stripped[:colon_idx]
    if '=' in before:
        return None
    return before.strip()


def _extract_blocks(filename: str, skip_patterns=None) -> List[RawBlock]:
    """Extract raw basic blocks from the file as RawBlock dataclasses.

    This pass only finds block boundaries and associates them with a function name and mode.
    """
    func_start_re = re.compile(r'^\s*define\b[^@]*@(?:"([^"]+)"|([^\(\s]+))\s*\(')
    func_mir_re = re.compile(r'^\s*Function:\s*(\S+)')
    bb_mir_re = re.compile(r'^\s*bb\.(\d+)\b')

    current_function: str | None = None
    in_mir_function = False
    blocks: List[RawBlock] = []
    current_block_lines: List[str] | None = None
    synth_function_name = Path(filename).name

    with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            stripped = line.strip()

            m_define = func_start_re.match(line)
            if m_define:
                current_function = (m_define.group(1) or m_define.group(2))
                in_mir_function = False
                # terminate any open block
                if current_block_lines is not None:
                    blocks.append(RawBlock(function_name=current_function, in_mir=in_mir_function, lines=current_block_lines))
                    current_block_lines = None
                continue

            m_mir = func_mir_re.match(line)
            if m_mir:
                current_function = m_mir.group(1)
                in_mir_function = True
                if current_block_lines is not None:
                    blocks.append(RawBlock(function_name=current_function, in_mir=in_mir_function, lines=current_block_lines))
                    current_block_lines = None
                continue

            # MIR block start
            if bb_mir_re.match(line):
                # flush previous block
                if current_block_lines is not None:
                    blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=(in_mir_function or True), lines=current_block_lines))
                current_block_lines = [line]
                if current_function is None:
                    current_function = synth_function_name
                    in_mir_function = True
                continue

            # IR label as block start
            label_guess = _is_ir_block_label(stripped)
            if label_guess is not None and not in_mir_function:
                if current_block_lines is not None:
                    blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=False, lines=current_block_lines))
                current_block_lines = [line]
                if current_function is None:
                    current_function = synth_function_name
                continue

            # Accumulate lines inside current block
            if current_block_lines is not None:
                current_block_lines.append(line)

        # EOF flush
        if current_block_lines is not None:
            blocks.append(RawBlock(function_name=(current_function or synth_function_name), in_mir=in_mir_function, lines=current_block_lines))

    # Apply skip filters at block level (by function name)
    if skip_patterns:
        filtered: List[RawBlock] = []
        for rb in blocks:
            if any(pat in (rb.function_name or "") for pat in skip_patterns):
                continue
            filtered.append(rb)
        return filtered

    return blocks


def analyze_ir(filename: str, skip_patterns=None) -> Dict[str, Function]:
    """Parse a textual LLVM .ir/.mir file and count instructions per basic block."""

    functions: Dict[str, Function] = {}
    blocks = _extract_blocks(filename, skip_patterns=skip_patterns)

    for rb in blocks:
        blk = parse_basic_block(rb.lines, in_mir=rb.in_mir)
        if blk.instructions <= 0:
            continue
        fn = functions.get(rb.function_name)
        if fn is None:
            fn = Function(name=rb.function_name)
            functions[rb.function_name] = fn
        # Fill label if parser couldn't
        if not blk.block:
            # derive from first line
            first = next((ln for ln in rb.lines if ln.strip()), "")
            blk.block = (first.split(":", 1)[0].strip() if first else "")
        fn.blocks += 1
        fn.total_instructions += blk.instructions
        fn.blocks_detail.append(blk)

    return functions


