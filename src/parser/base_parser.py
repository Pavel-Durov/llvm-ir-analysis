from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, TYPE_CHECKING

from .model import Function

if TYPE_CHECKING:
    from report.report import SummaryReport


class BaseParser(ABC):
    """Base class for all parsers (IR, MIR, ASM)."""

    def __init__(self, allowed_functions: set[str] | None = None):
        """Initialize parser with empty function map.
        
        Args:
            allowed_functions: Optional set of function names to include. If provided,
                              only functions in this set will be parsed/kept.
        """
        self.functions: Dict[str, Function] = {}
        self.allowed_functions = allowed_functions

    @abstractmethod
    def parse(self, filename: str, skip_patterns: List[str] | None = None,
              skip_prefixes: List[str] | None = None) -> Dict[str, Function]:
        """Parse the file and return a dictionary of functions.

        Also stores the result internally in self.functions.

        Args:
            filename: Path to the file to parse
            skip_patterns: Skip functions whose name contains any of these substrings
            skip_prefixes: Skip functions whose name starts with any of these prefixes

        Returns:
            Dict mapping function names to Function objects
        """
        pass

    def get_functions(self) -> Dict[str, Function]:
        """Get the parsed functions.
        
        Returns:
            Dict mapping function names to Function objects
        """
        return self.functions

    def _apply_allowed_functions_filter(self) -> None:
        """Apply the allowed_functions filter to the parsed functions.
        
        This should be called by subclasses after parsing.
        """
        if self.allowed_functions is not None:
            self.functions = {n: fn for n, fn in self.functions.items() 
                            if n in self.allowed_functions}

    def create_summary_report(self) -> 'SummaryReport':
        """Create a summary report for the parsed functions.
        
        Returns:
            SummaryReport object with statistics
        """
        from report.report import SummaryReport
        
        num_functions = len(self.functions)
        function_names = list(self.functions.keys())
        num_basic_blocks = sum(fn.blocks for fn in self.functions.values())
        num_instructions = sum(fn.total_instructions for fn in self.functions.values())
        avg_instr_per_block = (num_instructions / num_basic_blocks) if num_basic_blocks > 0 else 0.0
        
        return SummaryReport(
            num_functions=num_functions,
            num_basic_blocks=num_basic_blocks,
            num_instructions=num_instructions,
            avg_instr_per_block=avg_instr_per_block,
            function_names=function_names,
        )

