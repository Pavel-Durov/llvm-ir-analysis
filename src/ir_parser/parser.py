from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List

from .model import Block, Function


def parse_basic_block(block_lines: List[str], in_mir: bool) -> Block:
    label = ""
    instructions = 0
    text = "\n".join(block_lines) if block_lines else ""

    # Determine label from first non-empty line
    first = next((ln for ln in block_lines if ln.strip()), "")
    if first:
        if in_mir:
            label = first.split(":", 1)[0].strip()
        else:
            stripped = first.strip()
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
        if first and ln == first:
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
            instructions += 1
            in_switch = True
            continue
        if in_mir and (s.startswith("successors:") or s.startswith("predecessors:") or s.startswith("liveins:")):
            continue
        instructions += 1

    return Block(block=label, instructions=instructions, text=text)


def analyze_ir(filename: str, skip_patterns=None) -> Dict[str, Function]:
    """Parse a textual LLVM .ir/.mir file and count instructions per basic block."""

    functions: Dict[str, Function] = {}

    # Regex to capture function names in both @name(...) and @"name with space"(...) forms
    func_start_re = re.compile(r'^\s*define\b[^@]*@(?:"([^"]+)"|([^\(\s]+))\s*\(')
    # MIR-style function header: "Function: <name>"
    func_mir_re = re.compile(r'^\s*Function:\s*(\S+)')
    # MIR-style basic block header: "bb.N:" or "bb.N (..):"
    bb_mir_re = re.compile(r'^\s*bb\.(\d+)\b')

    in_function = False
    current_function = None
    in_mir_function = False
    skip_current_function = False
    current_block = None
    current_block_lines: List[str] | None = None

    def finish_block():
        nonlocal current_block, current_function, current_block_lines
        if in_function and not skip_current_function and current_function is not None and current_block is not None:
            fn = functions.get(current_function)
            if fn is None:
                fn = Function(name=current_function)
                functions[current_function] = fn
            blk = parse_basic_block(current_block_lines or [], in_mir_function)
            blk.block = blk.block or current_block
            fn.blocks += 1
            fn.total_instructions += blk.instructions
            fn.blocks_detail.append(blk)
        current_block = None
        current_block_lines = None

    def is_block_label(line_stripped: str) -> str | None:
        if not line_stripped or line_stripped.startswith(';'):
            return None
        colon_idx = line_stripped.find(':')
        if colon_idx <= 0:
            return None
        before = line_stripped[:colon_idx]
        if '=' in before:
            return None
        return before.strip()

    with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
        for raw_line in f:
            line = raw_line.rstrip('\n')
            stripped = line.strip()

            if not in_function:
                m_define = func_start_re.match(line)
                if m_define:
                    candidate = m_define.group(1) or m_define.group(2)
                    skip_current_function = bool(skip_patterns and any(pat in candidate for pat in skip_patterns))
                    current_function = candidate
                    in_function = True
                    in_mir_function = False
                    current_block = None
                    current_block_lines = None
                    continue
                m_mir = func_mir_re.match(line)
                if m_mir:
                    candidate = m_mir.group(1)
                    skip_current_function = bool(skip_patterns and any(pat in candidate for pat in skip_patterns))
                    current_function = candidate
                    in_function = True
                    in_mir_function = True
                    current_block = None
                    current_block_lines = None
                    continue
                # Heuristic: some dumps have blocks without explicit function headers
                # If we see a block label or MIR bb.N outside a function, synthesize one
                if bb_mir_re.match(line):
                    current_function = Path(filename).name
                    in_function = True
                    in_mir_function = True
                    current_block = line.split(':', 1)[0].strip()
                    current_block_lines = [line]
                    skip_current_function = bool(skip_patterns and any(pat in current_function for pat in skip_patterns))
                    continue
                # Generic IR label like "entry:" or numeric "42:" without '=' before ':'
                label_guess = is_block_label(stripped)
                if label_guess is not None:
                    current_function = Path(filename).name
                    in_function = True
                    in_mir_function = False
                    current_block = label_guess
                    current_block_lines = [line]
                    skip_current_function = bool(skip_patterns and any(pat in current_function for pat in skip_patterns))
                    continue
                continue

            if not in_mir_function:
                if stripped == '}':
                    finish_block()
                    in_function = False
                    current_function = None
                    skip_current_function = False
                    continue
            else:
                m_mir_new = func_mir_re.match(line)
                if m_mir_new:
                    finish_block()
                    candidate = m_mir_new.group(1)
                    skip_current_function = bool(skip_patterns and any(pat in candidate for pat in skip_patterns))
                    current_function = candidate
                    in_function = True
                    in_mir_function = True
                    current_block = None
                    current_block_lines = None
                    continue

            if in_mir_function:
                if bb_mir_re.match(line):
                    finish_block()
                    current_block = line.split(':', 1)[0].strip()
                    current_block_lines = [line]
                    continue
            else:
                label = is_block_label(stripped)
                if label is not None:
                    finish_block()
                    current_block = label
                    current_block_lines = [line]
                    continue

            if current_block is not None and not skip_current_function:
                if current_block_lines is not None:
                    current_block_lines.append(line)
    # Finish last block if file ended mid-function
    finish_block()

    return functions


