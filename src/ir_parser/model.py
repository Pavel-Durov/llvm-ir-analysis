from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Block:
    block: str
    instructions: int
    conditional_branches: int = 0
    text: str = ""


@dataclass
class Function:
    name: str
    blocks: int = 0
    total_instructions: int = 0
    total_cond_branches: int = 0
    blocks_detail: List[Block] = field(default_factory=list)


@dataclass
class SummaryReport:
    functions: Dict[str, Function]

    def to_dict(self) -> dict:
        sorted_funcs = sorted(self.functions.values(), key=lambda fn: fn.total_instructions, reverse=True)
        total_blocks = sum(f.blocks for f in self.functions.values())
        total_instructions = sum(f.total_instructions for f in self.functions.values())
        avg_instr_per_block = (total_instructions / total_blocks) if total_blocks else 0.0
        avg_blocks = (sum(f.blocks for f in self.functions.values()) / len(self.functions)) if self.functions else 0.0
        avg_instructions = (sum(f.total_instructions for f in self.functions.values()) / len(self.functions)) if self.functions else 0.0

        # Largest block
        largest_block_fn = None
        largest_block_label = None
        largest_block_size = -1
        largest_block_text = None
        for fn in self.functions.values():
            for block in fn.blocks_detail:
                if block.instructions > largest_block_size:
                    largest_block_size = block.instructions
                    largest_block_fn = fn.name
                    largest_block_label = block.block
                    largest_block_text = block.text

        top_by_instructions = [
            {
                'function': fn.name,
                'blocks': fn.blocks,
                'instructions': fn.total_instructions,
                'conditional_branches': fn.total_cond_branches,
            }
            for fn in sorted_funcs[:10]
        ]

        top_by_blocks = [
            {
                'function': fn.name,
                'blocks': fn.blocks,
                'instructions': fn.total_instructions,
                'conditional_branches': fn.total_cond_branches,
            }
            for fn in sorted(self.functions.values(), key=lambda f: f.blocks, reverse=True)[:10]
        ]

        report = {
            'summary': {
                'total_functions': len(self.functions),
                'total_basic_blocks': total_blocks,
                'total_instructions': total_instructions,
                'average_instructions_per_block': avg_instr_per_block,
                'average_blocks_per_function': avg_blocks,
                'average_instructions_per_function': avg_instructions,
            },
            'largest_block': (
                {
                    'function': largest_block_fn,
                    'block': largest_block_label,
                    'instructions': largest_block_size,
                    'text': largest_block_text,
                } if largest_block_fn is not None else None
            ),
            'top_by_instructions': top_by_instructions,
            'top_by_blocks': top_by_blocks,
        }

        return report

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


