from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from .base_parser import BaseParser
from .model import Block, Function, YK_TRACE_BASICBLOCK_FUNC

if TYPE_CHECKING:
    from report.report import SummaryReport


class ASMParser(BaseParser):
    """Parser for LLVM-style assembly (.s/.asm) files.
    
    Parses assembly files and extracts basic block information, filtering out
    assembler directives (lines starting with '.') which control assembler
    behavior rather than representing actual CPU instructions.
    """

    def __init__(self, allowed_functions: set[str] | None = None):
        """Initialize ASM parser.

        Args:
            allowed_functions: Optional set of function names to include.
        """
        super().__init__(allowed_functions)

    def _get_block(self, current_function: Function | None,
                     current_block_lines: List[str] | None,
                     current_block_label: str | None,
                     start_line: int = 0) -> Block | None:
        if current_function is None or current_block_lines is None:
            return None

        # Prioritize trace call BB ID over comment-based label
        trace_bb_id = ASMParser._extract_trace_bb_id(current_block_lines)
        if trace_bb_id is not None:
            label = f"bb.{trace_bb_id}"
        elif current_block_label:
            label = current_block_label
        else:
            label = f"bb_{current_function.blocks}"

        instr_lines = [ln for ln in current_block_lines if self._is_instruction_line(ln)]
        # Strip inline comments from instruction lines
        instr_lines_clean = [ASMParser._strip_inline_comment(ln) for ln in instr_lines]
        # Count __yk_trace_basicblock calls in this block
        yk_trace_bb_calls = sum(1 for ln in instr_lines_clean if YK_TRACE_BASICBLOCK_FUNC in ln)

        # Include tracing calls in instruction count
        return Block(block=label, instructions=len(instr_lines_clean),
                   instruction_lines=instr_lines_clean,
                   text="\n".join(current_block_lines), yk_trace_bb_calls=yk_trace_bb_calls,
                   start_line=start_line)


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
        current_block_start_line: int = 0
        inside_function = False
        inside_basic_block = False
        count_this_function = False
        seen_first_trace_call = False  # Track if we've seen the first trace call in current function
        skip_prefixes = skip_prefixes or []
        line_number = 0


        with Path(filename).open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line_number += 1
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
                            seen_first_trace_call = False  # Reset for new function
                            current_function = functions.get(func_name)
                            if current_function is None:
                                current_function = Function(name=func_name)
                                functions[func_name] = current_function
                    continue

                if end_func_re.search(line):
                    if count_this_function:
                        blk = self._get_block(current_function, current_block_lines, current_block_label, current_block_start_line)
                        if blk is not None:
                            current_function.blocks += 1
                            current_function.total_instructions += blk.instructions
                            current_function.blocks_detail.append(blk)
                    inside_function = False
                    inside_basic_block = False
                    count_this_function = False
                    seen_first_trace_call = False  # Reset
                    current_function = None
                    current_block_lines = None
                    current_block_label = None
                    continue

                m_bb = bb_start_re.search(line)
                if m_bb:
                    if count_this_function:
                        blk = self._get_block(current_function, current_block_lines, current_block_label, current_block_start_line)
                        if blk is not None:
                            current_function.blocks += 1
                            current_function.total_instructions += blk.instructions
                            current_function.blocks_detail.append(blk)
                        inside_basic_block = True
                        # Don't set the label yet - we'll determine it from trace calls if present
                        current_block_label = None
                        current_block_lines = []
                        current_block_start_line = line_number
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
                    # Check if this line starts a trace call sequence (movl $N, %edi)
                    # Only split if we've already seen the first trace call
                    stripped = line.strip()
                    if 'movl' in stripped and '%edi' in stripped and re.match(r'\s*movl\s+\$\d+,\s+%edi', stripped):
                        # This might be the start of a trace call sequence
                        # Only split before it if we've seen a trace call before
                        if seen_first_trace_call and current_block_lines:
                            blk = self._get_block(current_function, current_block_lines, current_block_label, current_block_start_line)
                            if blk is not None:
                                current_function.blocks += 1
                                current_function.total_instructions += blk.instructions
                                current_function.blocks_detail.append(blk)

                            # Start a new block - we'll determine the BB ID when we see the complete trace call
                            current_block_lines = [line]
                            current_block_start_line = line_number
                            # We'll set the label later when we find the complete trace call sequence
                            current_block_label = None
                            continue

                    # If we're in a block without a label and see a trace call sequence, extract the BB ID
                    if current_block_label is None and current_block_lines is not None:
                        # Check if we have a complete trace call sequence in current_block_lines
                        trace_bb_id = ASMParser._extract_trace_bb_id(current_block_lines + [line])
                        if trace_bb_id is not None:
                            current_block_label = f"bb.{trace_bb_id}"

                    # Check if this is a trace call - if so, mark that we've seen one
                    if YK_TRACE_BASICBLOCK_FUNC in line and 'callq' in line:
                        seen_first_trace_call = True

                    current_block_lines.append(line)

            if count_this_function:
                blk = self._get_block(current_function, current_block_lines, current_block_label, current_block_start_line)
                if blk is not None:
                    current_function.blocks += 1
                    current_function.total_instructions += blk.instructions
                    current_function.blocks_detail.append(blk)

        # Extract function indices from trace calls
        for func in functions.values():
            if func.blocks_detail:
                # Get function index from first block with trace calls
                for block in func.blocks_detail:
                    if block.yk_trace_bb_calls > 0:
                        func_idx = ASMParser._extract_function_index(block.instruction_lines)
                        if func_idx is not None:
                            func.function_index = func_idx
                            break

        self.functions = functions
        self._apply_allowed_functions_filter()
        return self.functions

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
        # Strip inline comments from instruction lines
        instr_lines_clean = [ASMParser._strip_inline_comment(ln) for ln in instr_lines]
        # Count __yk_trace_basicblock calls
        yk_trace_bb_calls = sum(1 for ln in instr_lines_clean if YK_TRACE_BASICBLOCK_FUNC in ln)
        text = "\n".join(block_lines)
        # Include tracing calls in instruction count
        return Block(block=label, instructions=len(instr_lines_clean), 
                    instruction_lines=instr_lines_clean, text=text, yk_trace_bb_calls=yk_trace_bb_calls)

    def apply_func_type_filter(self, filename: str, func_type: str,
                               skip_patterns: List[str] | None = None,
                               skip_prefixes: List[str] | None = None) -> None:
        """Apply function type filtering for ASM.

        ASM has only defined functions; declared-only results in empty map.

        Args:
            filename: Path to the ASM file (unused, for API consistency)
            func_type: Type of functions to include ('defined', 'declared', 'all')
            skip_patterns: Skip functions (unused, for API consistency)
            skip_prefixes: Skip prefixes (unused, for API consistency)
        """
        if func_type == 'declared':
            # ASM has only defined functions; declared-only => empty map
            self.functions = {}

    def create_summary_report(self) -> 'SummaryReport':
        """Create a summary report including ASM-specific metrics."""
        # Get base report from parent
        report = super().create_summary_report()

        # Compute and add __yk_trace_basicblock statistics
        report.yk_trace_stats = self._compute_yk_trace_stats()

        return report

    @staticmethod
    def _extract_trace_bb_id(lines: List[str]) -> int | None:
        """Extract basic block ID from __yk_trace_basicblock call parameters.

        Looks for the pattern:
            movl $<function_id>, %edi    # First parameter
            movl $<bb_id>, %esi          # Second parameter (or xorl %esi, %esi for bb 0)
            callq __yk_trace_basicblock@PLT

        Returns:
            The basic block ID (second parameter), or None if not found
        """
        for i in range(len(lines) - 2):
            # Check if this is a trace call
            if YK_TRACE_BASICBLOCK_FUNC in lines[i + 2]:
                # Look back for the second parameter (bb_id)
                if i + 1 < len(lines):
                    line = lines[i + 1].strip()
                    # Pattern: movl $<bb_id>, %esi
                    match = re.match(r'movl\s+\$(\d+),\s+%esi', line)
                    if match:
                        return int(match.group(1))
                    # Pattern: xorl %esi, %esi (means bb_id = 0)
                    if 'xorl' in line and '%esi' in line:
                        return 0
        return None

    @staticmethod
    def _extract_function_index(lines: List[str]) -> int | None:
        """Extract function index from __yk_trace_basicblock call parameters.

        Looks for the pattern:
            movl $<function_id>, %edi    # First parameter (function index)
            movl $<bb_id>, %esi          # Second parameter
            callq __yk_trace_basicblock@PLT

        Returns:
            The function index (first parameter), or None if not found
        """
        for i in range(len(lines) - 2):
            # Check if this is a trace call
            if YK_TRACE_BASICBLOCK_FUNC in lines[i + 2]:
                # Look back for the first parameter (function_id)
                if i < len(lines):
                    line = lines[i].strip()
                    # Pattern: movl $<function_id>, %edi
                    match = re.match(r'movl\s+\$(\d+),\s+%edi', line)
                    if match:
                        return int(match.group(1))
        return None

    @staticmethod
    def _strip_inline_comment(line: str) -> str:
        """Strip inline comments from assembly instruction lines.
        
        Removes comments that appear after instructions, e.g.:
            movl	$554, %edi                      # imm = 0x22A
        becomes:
            movl	$554, %edi
        
        Args:
            line: Assembly instruction line that may contain an inline comment
            
        Returns:
            The instruction line with inline comment removed and trailing whitespace stripped.
        """
        # Find the comment marker '#' and remove everything from there onwards
        comment_pos = line.find('#')
        if comment_pos != -1:
            line = line[:comment_pos]
        # Strip trailing whitespace
        return line.rstrip()

    @staticmethod
    def _is_instruction_line(line: str) -> bool:
        """Check if line is an actual assembly instruction.
        
        Filters out:
        - Empty lines
        - Comments (starting with #)
        - Assembler directives (starting with .) - these control assembler behavior,
          not CPU execution, and include commands like .section, .data, .text, 
          .align, .global, .cfi_*, .type, .size, etc.
        - Labels (ending with :)
        
        Returns:
            True if the line represents an actual CPU instruction, False otherwise.
        """
        s = line.strip()
        if not s:
            return False
        # Skip comments
        if s.startswith("#"):
            return False
        # Skip assembler directives - these control assembler behavior, not CPU execution
        if s.startswith("."):
            return False
        # Skip labels
        if s.endswith(":"):
            return False
        return True

