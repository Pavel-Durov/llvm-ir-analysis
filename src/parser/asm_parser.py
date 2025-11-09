from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from .base_parser import BaseParser
from .model import Block, Function


class ASMParser(BaseParser):
    """Parser for LLVM-style assembly (.s/.asm) files."""

    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse assembly file and return functions with basic block details."""
        begin_func_re = re.compile(r"#\s*--\s*Begin function\s+(\S+)")
        end_func_re = re.compile(r"#\s*--\s*End function")
        bb_start_re = re.compile(r"#\s*%bb\.(\d+):?")

        functions: Dict[str, Function] = {}
        current_function: Function | None = None
        current_block_lines: List[str] | None = None
        current_block_label: str | None = None
        inside_function = False
        inside_basic_block = False
        count_this_function = False
        skip_prefixes = skip_prefixes or []

        def flush_block():
            nonlocal current_block_lines, current_block_label, current_function
            if current_function is None or current_block_lines is None:
                return
            label = (current_block_label or f"bb_{current_function.blocks}")
            instr_lines = [ln for ln in current_block_lines if self._is_instruction_line(ln)]
            blk = Block(block=label, instructions=len(instr_lines), instruction_lines=instr_lines,
                       text="\n".join(current_block_lines))
            current_function.blocks += 1
            current_function.total_instructions += blk.instructions
            current_function.blocks_detail.append(blk)
            current_block_lines = None
            current_block_label = None

        with Path(filename).open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                if not inside_function:
                    m = begin_func_re.search(line)
                    if m:
                        func_name = m.group(1)
                        if any(func_name.startswith(pfx) for pfx in skip_prefixes):
                            count_this_function = False
                            inside_function = True
                            current_function = None
                        else:
                            count_this_function = True
                            inside_function = True
                            current_function = functions.get(func_name)
                            if current_function is None:
                                current_function = Function(name=func_name)
                                functions[func_name] = current_function
                    continue

                if end_func_re.search(line):
                    if count_this_function:
                        flush_block()
                    inside_function = False
                    inside_basic_block = False
                    count_this_function = False
                    current_function = None
                    current_block_lines = None
                    current_block_label = None
                    continue

                m_bb = bb_start_re.search(line)
                if m_bb:
                    if count_this_function:
                        flush_block()
                        inside_basic_block = True
                        current_block_label = f"bb.{m_bb.group(1)}"
                        current_block_lines = []
                    else:
                        inside_basic_block = False
                        current_block_lines = None
                        current_block_label = None
                    continue

                if not count_this_function:
                    continue

                # Try to capture actual label
                if (inside_basic_block and current_block_lines is not None and 
                    current_block_label and current_block_label.startswith("bb.")):
                    stripped = line.strip()
                    if stripped.endswith(":") and not stripped.startswith("#") and not stripped.startswith("."):
                        current_block_label = stripped[:-1]

                if inside_basic_block and current_block_lines is not None:
                    current_block_lines.append(line)

            if count_this_function:
                flush_block()

        return functions

    def _parse_basic_block(self, block_lines: List[str]) -> Block:
        """Parse a basic block from assembly lines (for testing)."""
        label = ""
        # Extract label from first line if it looks like a basic block marker
        if block_lines:
            first_line = block_lines[0].strip()
            if first_line.startswith("# %bb."):
                label = first_line.split()[1].rstrip(":")
            elif first_line.startswith(".LBB") and first_line.endswith(":"):
                label = first_line.rstrip(":")
        
        instr_lines = [ln for ln in block_lines if self._is_instruction_line(ln)]
        text = "\n".join(block_lines)
        return Block(block=label, instructions=len(instr_lines), 
                    instruction_lines=instr_lines, text=text)

    @staticmethod
    def _is_instruction_line(line: str) -> bool:
        """Check if line is an actual assembly instruction."""
        s = line.strip()
        if not s:
            return False
        if s.startswith("#"):
            return False
        if s.startswith("."):
            return False
        if s.endswith(":"):
            return False
        return True

