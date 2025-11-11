from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parser.model import YkTraceStats


@dataclass
class SummaryReport:
    """Summary report for parsed functions."""
    num_functions: int
    num_basic_blocks: int
    num_instructions: int
    avg_instr_per_block: float
    function_names: list[str]
    # __yk_trace_basicblock metrics
    yk_trace_stats: 'YkTraceStats | None' = None

    def print_to_console(self, print_function_list: bool = False) -> None:
        """Print the report to console."""
        print(f"Functions: {self.num_functions}")

        if print_function_list and self.function_names:
            print("Function list:")
            for name in sorted(self.function_names):
                print(f"  {name}")

        print(f"Basic blocks (in functions): {self.num_basic_blocks}")
        print(f"Instructions (in basic blocks): {self.num_instructions}")
        print(f"Average instructions per basic block: {self.avg_instr_per_block:.2f}")

        # Print __yk_trace_basicblock statistics if they exist
        if self.yk_trace_stats and self.yk_trace_stats.has_data():
            print(f"\nBlocks with __yk_trace_basicblock: {self.yk_trace_stats.num_blocks}")
            print(f"Instructions in those blocks: {self.yk_trace_stats.num_instructions}")
            print(f"Total __yk_trace_basicblock calls: {self.yk_trace_stats.total_calls}")
            print(f"Average instructions per __yk_trace_basicblock call: {self.yk_trace_stats.avg_instr_per_call:.2f}")

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        report = {
            'summary': {
                'total_functions': self.num_functions,
                'total_basic_blocks': self.num_basic_blocks,
                'total_instructions': self.num_instructions,
                'average_instructions_per_block': self.avg_instr_per_block,
            }
        }
        
        if self.yk_trace_stats and self.yk_trace_stats.has_data():
            report['yk_trace_basicblock'] = {
                'blocks_with_calls': self.yk_trace_stats.num_blocks,
                'instructions_in_blocks': self.yk_trace_stats.num_instructions,
                'total_calls': self.yk_trace_stats.total_calls,
                'average_instructions_per_call': self.yk_trace_stats.avg_instr_per_call,
            }
        
        return report

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


