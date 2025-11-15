from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

from .base_parser import BaseParser
from .model import Block, Function, RawBlock, YK_TRACE_BASICBLOCK_FUNC

if TYPE_CHECKING:
    from report.report import SummaryReport


class IRParser(BaseParser):
    """Parser for LLVM IR (.ll/.ir) files."""

    def __init__(self, allowed_functions: set[str] | None = None):
        """Initialize IR parser.
        
        Args:
            allowed_functions: Optional set of function names to include.
        """
        super().__init__(allowed_functions)

    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse LLVM IR file and return functions with basic block details."""
        blocks = self._extract_blocks(filename, skip_patterns)
        functions: Dict[str, Function] = {}

        for rb in blocks:
            blk = self._parse_basic_block(rb.lines, in_mir=False)
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

        self.functions = functions
        self._apply_allowed_functions_filter()
        return self.functions

    def parse_from_string(self, ir_text: str, skip_patterns: List[str] | None = None,
                          skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse LLVM IR from a string and return functions with basic block details.
        
        This is a convenience method for testing that writes the string to a temporary file.
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ll', delete=False, encoding='utf-8') as f:
            f.write(ir_text)
            temp_path = f.name
        
        try:
            return self.parse(temp_path, skip_patterns, skip_prefixes)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _parse_basic_block(self, block_lines: List[str], in_mir: bool) -> Block:
        """Parse a basic block from IR."""
        label = ""
        text = "\n".join(block_lines) if block_lines else ""
        collected: List[str] = []

        # Find label line
        label_line: str | None = None
        first = next((ln for ln in block_lines if ln.strip()), "")
        if first:
            s = first.strip()
            idx = s.find(":")
            if idx > 0 and "=" not in s[:idx]:
                # This is actually a label
                label_line = first
                label = s[:idx].strip()

        in_switch = False
        for ln in block_lines:
            s = ln.strip()
            if not s:
                continue
            if label_line and ln == label_line:
                continue
            if (s.startswith('source_filename') or 'target datalayout' in s or
                s.startswith('target datalayout') or s.startswith('target triple') or
                s.startswith('!target triple')):
                continue
            if s.startswith(";") or s.startswith("#") or s.startswith("!"):
                continue
            if s == '"':
                continue
            # Handle IR switch statements
            if in_switch:
                if ']' in s:
                    in_switch = False
                continue
            if s.startswith('switch '):
                collected.append(ln)
                in_switch = True
                continue
            collected.append(ln)

        # Count __yk_trace_basicblock calls
        yk_trace_bb_calls = sum(1 for ln in collected if YK_TRACE_BASICBLOCK_FUNC in ln)

        # Include tracing calls in instruction count
        return Block(block=label, instructions=len(collected), instruction_lines=collected, 
                    text=text, yk_trace_bb_calls=yk_trace_bb_calls)

    def _is_ir_block_label(self, line_stripped: str) -> str | None:
        """Check if line is an IR block label."""
        if not line_stripped or line_stripped.startswith(';'):
            return None
        colon_idx = line_stripped.find(':')
        if colon_idx <= 0:
            return None
        before = line_stripped[:colon_idx]
        if '=' in before:
            return None
        return before.strip()

    def _extract_blocks(self, filename: str, skip_patterns: List[str] | None) -> List[RawBlock]:
        """Extract raw basic blocks from IR file."""
        func_start_re = re.compile(r'^\s*define\b[^@]*@(?:"([^"]+)"|([^\(\s]+))\s*\(')
        
        current_function: str | None = None
        blocks: List[RawBlock] = []
        current_block_lines: List[str] | None = None


        with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
            for raw_line in f:
                line = raw_line.rstrip('\n')
                stripped = line.strip()

                m_define = func_start_re.match(line)
                if m_define:
                    current_function = (m_define.group(1) or m_define.group(2))
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=False, lines=current_block_lines))
                    # Start collecting lines for the entry block (which may be unlabeled)
                    current_block_lines = []
                    continue

                # End of function definition (closing brace)
                if stripped == '}' and current_function is not None:
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=False, lines=current_block_lines))
                    current_function = None
                    current_block_lines = None
                    continue

                # IR label as block start
                label_guess = self._is_ir_block_label(stripped)
                if label_guess is not None and current_function is not None:
                    if current_block_lines is not None:
                        blocks.append(RawBlock(function_name=current_function, in_mir=False, lines=current_block_lines))
                    current_block_lines = [line]
                    continue

                # Accumulate lines
                if current_block_lines is not None:
                    current_block_lines.append(line)

            # EOF flush
            if current_block_lines is not None and current_function is not None:
                blocks.append(RawBlock(function_name=current_function, in_mir=False, lines=current_block_lines))

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
        """Apply function type filtering (declared/all) to parsed functions.

        Args:
            filename: Path to the IR file (needed to list declared functions)
            func_type: Type of functions to include ('defined', 'declared', 'all')
            skip_patterns: Skip functions whose name contains any of these substrings
            skip_prefixes: Skip functions whose name starts with any of these prefixes
        """
        if func_type not in ('declared', 'all'):
            return  # Nothing to do for 'defined'
        _, declared_only = list_ir_functions(filename)

        # Apply substring and prefix filters to declared_set
        def keep_name(name: str) -> bool:
            if skip_patterns and any(sub in name for sub in skip_patterns):
                return False
            if skip_prefixes and any(name.startswith(p) for p in skip_prefixes):
                return False
            return True

        declared_filtered = {n for n in declared_only if keep_name(n)}

        if func_type == 'declared':
            # Replace with declared-only map (zero blocks)
            self.functions = {n: Function(name=n) for n in declared_filtered}
        else:  # all
            # Keep existing defined (already filtered), add declared that are not present
            for n in sorted(declared_filtered):
                if n not in self.functions:
                    self.functions[n] = Function(name=n)

    def create_summary_report(self) -> SummaryReport:
        """Create a summary report including IR-specific metrics."""
        # Get base report from parent
        report = super().create_summary_report()
        
        # Compute and add __yk_trace_basicblock statistics
        report.yk_trace_stats = self._compute_yk_trace_stats()
        
        return report


def list_ir_functions(filename: str) -> tuple[set[str], set[str]]:
    """Return (defined_functions, declared_functions) from IR file."""
    define_re = re.compile(r'^\s*define\b[^@]*@(?:"([^"]+)"|([^\(\s]+))\s*\(')
    declare_re = re.compile(r'^\s*declare\b[^@]*@(?:"([^"]+)"|([^\(\s]+))\s*\(')
    defined: set[str] = set()
    declared: set[str] = set()
    with Path(filename).open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = define_re.match(line)
            if m:
                defined.add(m.group(1) or m.group(2))
                continue
            m = declare_re.match(line)
            if m:
                declared.add(m.group(1) or m.group(2))
    declared -= defined
    return defined, declared

