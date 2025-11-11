#!/usr/bin/env python3
"""Export MIR and ASM block comparisons to CSV format.

This utility parses MIR and ASM files, matches blocks based on __yk_trace_basicblock
calls, and exports the comparison data to a CSV file.
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

from parser import MIRParser, ASMParser
from parser.model import Block, Function


def extract_trace_bb_id_from_mir_block(block: Block) -> int | None:
    """Extract the basic block ID from __yk_trace_basicblock call in MIR block.
    
    Looks for patterns like:
        $esi = MOV32ri 19
        $esi = MOV32r0  (for bb_id = 0)
    """
    for line in block.instruction_lines:
        stripped = line.strip()
        # Pattern: $esi = MOV32ri <number>
        if '$esi = MOV32ri' in stripped:
            parts = stripped.split()
            if len(parts) >= 4:
                try:
                    return int(parts[3])
                except (ValueError, IndexError):
                    continue
        # Pattern: $esi = MOV32r0 (indicates bb_id = 0)
        elif '$esi = MOV32r0' in stripped:
            return 0
    return None


def extract_trace_bb_id_from_asm_block(block: Block) -> int | None:
    """Extract the basic block ID from __yk_trace_basicblock call in ASM block.
    
    Looks for patterns like:
        movl $19, %esi
        xorl %esi, %esi  (for bb_id = 0)
    """
    for line in block.instruction_lines:
        stripped = line.strip()
        # Pattern: movl $<number>, %esi
        if 'movl' in stripped and '%esi' in stripped:
            if '$' in stripped:
                parts = stripped.split('$')
                if len(parts) >= 2:
                    num_part = parts[1].split(',')[0].strip()
                    try:
                        return int(num_part)
                    except ValueError:
                        continue
        # Pattern: xorl %esi, %esi (indicates bb_id = 0)
        elif 'xorl' in stripped and '%esi' in stripped and stripped.count('%esi') == 2:
            return 0
    return None


def build_block_index(functions: List[Function], extract_fn) -> Dict[tuple[str, int], List[Block]]:
    """Build an index of blocks by (function_name, trace_bb_id).
    
    Args:
        functions: List of Function objects
        extract_fn: Function to extract trace BB ID from a block
        
    Returns:
        Dictionary mapping (function_name, trace_bb_id) to list of blocks
    """
    index: Dict[tuple[str, int], List[Block]] = {}
    
    for func in functions:
        for block in func.blocks_detail:
            if block.yk_trace_bb_calls > 0:
                trace_id = extract_fn(block)
                if trace_id is not None:
                    key = (func.name, trace_id)
                    if key not in index:
                        index[key] = []
                    index[key].append(block)
    
    return index


def export_to_csv(mir_file: str, asm_file: str, output_file: str, filter_function: str | None = None):
    """Export block comparison data to CSV file.
    
    Args:
        mir_file: Path to MIR file
        asm_file: Path to ASM file
        output_file: Path to output CSV file
        filter_function: Optional function name to filter (only export this function)
    """
    # Parse files
    print(f"Parsing MIR file: {mir_file}")
    mir_parser = MIRParser()
    mir_functions_dict = mir_parser.parse(mir_file)
    
    print(f"Parsing ASM file: {asm_file}")
    asm_parser = ASMParser()
    asm_functions_dict = asm_parser.parse(asm_file)
    
    # Convert to lists
    mir_functions = list(mir_functions_dict.values())
    asm_functions = list(asm_functions_dict.values())
    
    # Filter functions if requested
    if filter_function:
        mir_functions = [f for f in mir_functions if filter_function in f.name]
        asm_functions = [f for f in asm_functions if filter_function in f.name]
        print(f"Filtered to function: {filter_function}")
        print(f"  MIR functions found: {len(mir_functions)}")
        print(f"  ASM functions found: {len(asm_functions)}")
    
    # Build indices
    mir_index = build_block_index(mir_functions, extract_trace_bb_id_from_mir_block)
    asm_index = build_block_index(asm_functions, extract_trace_bb_id_from_asm_block)
    
    # Get all keys (function_name, trace_bb_id pairs)
    all_keys = sorted(set(mir_index.keys()) | set(asm_index.keys()))
    
    # Write CSV
    mir_path = Path(mir_file)
    asm_path = Path(asm_file)
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'function_name',
            'bb_id',
            'mir_file',
            'mir_line',
            'mir_bb_raw',
            'mir_real_inst_count',
            'mir_total_inst_count',
            'asm_file',
            'asm_line',
            'asm_bb_raw',
            'asm_real_inst_count',
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        rows_written = 0
        for func_name, trace_id in all_keys:
            mir_blocks = mir_index.get((func_name, trace_id), [])
            asm_blocks = asm_index.get((func_name, trace_id), [])
            
            # Write one row per match (or partial match)
            max_blocks = max(len(mir_blocks), len(asm_blocks))
            
            for i in range(max_blocks):
                mir_block = mir_blocks[i] if i < len(mir_blocks) else None
                asm_block = asm_blocks[i] if i < len(asm_blocks) else None
                
                # Get raw block text
                mir_raw = '\n'.join(line.strip() for line in mir_block.instruction_lines) if mir_block else ''
                asm_raw = '\n'.join(line.strip() for line in asm_block.instruction_lines) if asm_block else ''
                
                row = {
                    'function_name': func_name,
                    'bb_id': trace_id,
                    'mir_file': mir_path.name if mir_block else '',
                    'mir_line': mir_block.start_line if mir_block else '',
                    'mir_bb_raw': mir_raw,
                    'mir_real_inst_count': mir_block.instructions if mir_block else '',
                    'mir_total_inst_count': mir_block.total_instructions if mir_block else '',
                    'asm_file': asm_path.name if asm_block else '',
                    'asm_line': asm_block.start_line if asm_block else '',
                    'asm_bb_raw': asm_raw,
                    'asm_real_inst_count': asm_block.instructions if asm_block else '',
                }
                writer.writerow(row)
                rows_written += 1
    
    print(f"\nExported {rows_written} rows to: {output_file}")
    print(f"  Total matched block pairs: {len(all_keys)}")


def main():
    parser = argparse.ArgumentParser(
        description="Export MIR and ASM block comparisons to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mir yklua.ir.llc.mir --asm yklua.llc.asm --output blocks.csv
  %(prog)s -m data/yklua.ir.llc.mir -a data/yklua.llc.asm -o report.csv -f getobjname
        """
    )

    parser.add_argument(
        '--mir', '-m',
        required=True,
        help='Path to MIR file'
    )

    parser.add_argument(
        '--asm', '-a',
        required=True,
        help='Path to ASM file'
    )

    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Path to output CSV file'
    )

    parser.add_argument(
        '--function', '-f',
        help='Filter to specific function name (optional)'
    )

    args = parser.parse_args()

    # Validate input files exist
    if not Path(args.mir).exists():
        print(f"Error: MIR file not found: {args.mir}", file=sys.stderr)
        sys.exit(1)

    if not Path(args.asm).exists():
        print(f"Error: ASM file not found: {args.asm}", file=sys.stderr)
        sys.exit(1)

    try:
        export_to_csv(args.mir, args.asm, args.output, args.function)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

