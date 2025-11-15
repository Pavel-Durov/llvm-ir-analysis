#!/usr/bin/env python3
"""
CLI utility to match IR, MIR and ASM basic blocks for a given function.

Matches blocks based on the __yk_trace_basicblock call parameters:
- Extracts the basic block ID (second parameter) from trace calls
- Matches IR, MIR blocks with corresponding ASM blocks
- Outputs statistics to CSV format
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from parser import IRParser, MIRParser, ASMParser, YK_TRACE_BASICBLOCK_FUNC
from parser.model import Block


def extract_trace_bb_id_from_mir_block(block: Block) -> int | None:
    """Extract BB ID from MIR block's __yk_trace_basicblock call.
    
    Looks for: CALL64pcrel32 target-flags(x86-plt) @__yk_trace_basicblock, ...
    with parameters set by $edi = MOV32ri <func_id> and $esi = MOV32ri <bb_id>
    or $esi = MOV32r0 (which means bb_id = 0)
    """
    import re
    lines = block.instruction_lines
    for i in range(len(lines) - 1):
        # Check if next line is a trace call
        if YK_TRACE_BASICBLOCK_FUNC in lines[i + 1]:
            # Look at current line for the second parameter (bb_id)
            line = lines[i].strip()
            # Pattern: $esi = MOV32ri <bb_id>
            match = re.search(r'\$esi\s*=\s*MOV32ri\s+(\d+)', line)
            if match:
                return int(match.group(1))
            # Pattern: $esi = MOV32r0 (means bb_id = 0)
            if 'MOV32r0' in line and '$esi' in line:
                return 0
            # Pattern: $esi = COPY <reg> - need to look further back
            # For now, skip these complex cases
    return None


def extract_trace_bb_id_from_asm_block(block: Block) -> int | None:
    """Extract BB ID from ASM block's __yk_trace_basicblock call.

    Looks for the pattern:
        movl $<bb_id>, %esi
        callq __yk_trace_basicblock@PLT
    """
    import re
    lines = block.instruction_lines
    for i in range(len(lines) - 1):
        # Check if next line is a trace call
        if YK_TRACE_BASICBLOCK_FUNC in lines[i + 1]:
            # Look at current line for the second parameter (bb_id)
            line = lines[i].strip()
            # Pattern: movl $<bb_id>, %esi
            match = re.match(r'movl\s+\$(\d+),\s+%esi', line)
            if match:
                return int(match.group(1))
            # Pattern: xorl %esi, %esi (means bb_id = 0)
            if 'xorl' in line and '%esi' in line:
                return 0
    return None


def extract_trace_bb_id_from_ir_block(block: Block) -> int | None:
    """Extract BB ID from IR block's __yk_trace_basicblock call.

    Looks for the pattern:
        call void @__yk_trace_basicblock(i32 <func_id>, i32 <bb_id>)
    """
    import re
    lines = block.instruction_lines
    for line in lines:
        if YK_TRACE_BASICBLOCK_FUNC in line:
            # Pattern: call void @__yk_trace_basicblock(i32 <func_id>, i32 <bb_id>)
            match = re.search(r'@__yk_trace_basicblock\s*\(\s*i32\s+\d+\s*,\s*i32\s+(\d+)\s*\)', line)
            if match:
                return int(match.group(1))
    return None


def match_blocks(
    mir_file: str,
    asm_file: str,
    ir_file: Optional[str],
    function_name: Optional[str],
    csv_output: Optional[str],
    verbose: bool = False
) -> None:
    """Match IR, MIR and ASM blocks for given function(s) and output results."""

    # Determine which functions to process
    if function_name:
        functions_to_process = {function_name}
        print(f"Matching blocks for function: {function_name}")
    else:
        # Process all __yk_opt_ functions
        print("Processing all functions with __yk_opt_ prefix")
        functions_to_process = set()

    print(f"MIR file: {mir_file}")
    print(f"ASM file: {asm_file}")
    if ir_file:
        print(f"IR file: {ir_file}")
    print()

    # Parse MIR
    mir_parser = MIRParser(allowed_functions=functions_to_process if functions_to_process else None)
    mir_parser.parse(mir_file)

    # If no specific function, find all __yk_opt_ functions in MIR
    if not function_name:
        functions_to_process = {fn for fn in mir_parser.functions.keys() if fn.startswith('__yk_opt_')}
        print(f"Found {len(functions_to_process)} functions with __yk_opt_ prefix")

    # Parse ASM
    asm_parser = ASMParser(allowed_functions=functions_to_process if functions_to_process else None)
    asm_parser.parse(asm_file)

    # Parse IR if provided
    ir_parser = None
    if ir_file:
        # For IR, we need to find the original function names (without __yk_opt_ prefix)
        original_function_names = set()
        for fn in functions_to_process:
            if fn.startswith('__yk_opt_'):
                original_fn = fn.replace('__yk_opt_', '', 1)
                original_function_names.add(original_fn)
            else:
                original_function_names.add(fn)

        ir_parser = IRParser(allowed_functions=original_function_names if original_function_names else None)
        ir_parser.parse(ir_file)

    # Collect all matched blocks
    all_matches = []

    for fn_name in sorted(functions_to_process):
        if fn_name not in mir_parser.functions:
            continue

        mir_func = mir_parser.functions[fn_name]
        asm_func = asm_parser.functions.get(fn_name)

        # Find original IR function
        ir_func = None
        original_fn_name = None
        if ir_parser:
            if fn_name.startswith('__yk_opt_'):
                original_fn_name = fn_name.replace('__yk_opt_', '', 1)
            else:
                original_fn_name = fn_name
            ir_func = ir_parser.functions.get(original_fn_name)
        
        # Build mapping of trace BB ID -> blocks
        mir_blocks_by_trace_id: Dict[int, List[Block]] = {}
        asm_blocks_by_trace_id: Dict[int, List[Block]] = {}
        ir_blocks_by_trace_id: Dict[int, List[Block]] = {}
        
        # Extract trace IDs from MIR blocks
        for block in mir_func.blocks_detail:
            trace_id = extract_trace_bb_id_from_mir_block(block)
            if trace_id is not None:
                if trace_id not in mir_blocks_by_trace_id:
                    mir_blocks_by_trace_id[trace_id] = []
                mir_blocks_by_trace_id[trace_id].append(block)
        
        # Extract trace IDs from ASM blocks
        if asm_func:
            for block in asm_func.blocks_detail:
                trace_id = extract_trace_bb_id_from_asm_block(block)
                if trace_id is not None:
                    if trace_id not in asm_blocks_by_trace_id:
                        asm_blocks_by_trace_id[trace_id] = []
                    asm_blocks_by_trace_id[trace_id].append(block)
        
        # Extract trace IDs from IR blocks
        if ir_func:
            for block in ir_func.blocks_detail:
                trace_id = extract_trace_bb_id_from_ir_block(block)
                if trace_id is not None:
                    if trace_id not in ir_blocks_by_trace_id:
                        ir_blocks_by_trace_id[trace_id] = []
                    ir_blocks_by_trace_id[trace_id].append(block)
        
        # Print summary for this function
        if verbose or function_name:
            print(f"\nFunction: {fn_name}")
            print("-" * 80)
            print(f"MIR: {mir_func.blocks} blocks, {mir_func.total_instructions} instructions")
            print(f"  Blocks with trace calls: {len(mir_blocks_by_trace_id)}")
            if asm_func:
                print(f"ASM: {asm_func.blocks} blocks, {asm_func.total_instructions} instructions")
                print(f"  Blocks with trace calls: {len(asm_blocks_by_trace_id)}")
            if ir_func:
                print(f"IR ({original_fn_name}): {ir_func.blocks} blocks, {ir_func.total_instructions} instructions")
                print(f"  Blocks with trace calls: {len(ir_blocks_by_trace_id)}")
        
        # Find all trace IDs (union of all)
        all_trace_ids = set(mir_blocks_by_trace_id.keys())
        all_trace_ids |= set(asm_blocks_by_trace_id.keys())
        all_trace_ids |= set(ir_blocks_by_trace_id.keys())
        
        # Collect matches for CSV output
        for trace_id in sorted(all_trace_ids):
            mir_blocks = mir_blocks_by_trace_id.get(trace_id, [])
            asm_blocks = asm_blocks_by_trace_id.get(trace_id, [])
            ir_blocks = ir_blocks_by_trace_id.get(trace_id, [])
            
            # For each combination, create a row
            max_blocks = max(len(mir_blocks), len(asm_blocks), len(ir_blocks))
            for i in range(max_blocks):
                mir_block = mir_blocks[i] if i < len(mir_blocks) else None
                asm_block = asm_blocks[i] if i < len(asm_blocks) else None
                ir_block = ir_blocks[i] if i < len(ir_blocks) else None
                
                # Get raw block content
                mir_tbb_raw = '\n'.join(mir_block.instruction_lines) if mir_block else ''
                ir_bb_raw = '\n'.join(ir_block.instruction_lines) if ir_block else ''
                asm_bb_raw = '\n'.join(asm_block.instruction_lines) if asm_block else ''
                
                match = {
                    'function_name': fn_name,
                    'bb_id': trace_id,
                    'mir_file': mir_file,
                    'mir_tbb_line': mir_block.start_line if mir_block else 0,
                    'mir_tbb_raw': mir_tbb_raw,
                    'mir_bb_line': ir_block.start_line if ir_block else 0,
                    'mir_bb_raw': ir_bb_raw,
                    'asm_bb_raw': asm_bb_raw,
                    'mir_real_inst_count': mir_block.instructions if mir_block else 0,
                    'mir_total_inst_count': mir_block.total_instructions if mir_block else 0,
                    'asm_file': asm_file,
                    'asm_line': asm_block.start_line if asm_block else 0,
                    'asm_real_inst_count': asm_block.instructions if asm_block else 0,
                }
                all_matches.append(match)
                
                # Print detailed output if verbose
                if verbose:
                    print(f"\nTrace BB ID: {trace_id}")
                    if ir_block:
                        print(f"  IR: {ir_block.block} - {ir_block.instructions} instructions")
                    if mir_block:
                        print(f"  MIR: {mir_block.block} - {mir_block.instructions}/{mir_block.total_instructions} instructions")
                    if asm_block:
                        print(f"  ASM: {asm_block.block} - {asm_block.instructions} instructions")
    
    # Output to CSV
    if csv_output and all_matches:
        with open(csv_output, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'function_name', 'bb_id', 
                'mir_file', 'mir_tbb_line', 'mir_tbb_raw', 
                'mir_bb_line', 'mir_bb_raw', 
                'asm_bb_raw', 
                'mir_real_inst_count', 'mir_total_inst_count', 
                'asm_file', 'asm_line', 'asm_real_inst_count'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            writer.writerows(all_matches)
        
        print(f"\nWrote {len(all_matches)} matched blocks to {csv_output}")
    elif all_matches:
        print(f"\nFound {len(all_matches)} matched blocks (use --csv to output to file)")
    else:
        print("\nNo blocks with __yk_trace_basicblock calls found")


def main():
    parser = argparse.ArgumentParser(
        description="Match IR, MIR and ASM basic blocks based on __yk_trace_basicblock calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Match single function with IR, MIR and ASM:
  %(prog)s --mir yklua.ir.llc.mir --asm yklua.llc.asm --ir yklua.ir --function getobjname --csv output.csv
  
  # Match all __yk_opt_ functions:
  %(prog)s --mir data/yklua.ir.llc.mir --asm data/yklua.llc.asm --ir data/yklua.ir --csv all_matches.csv
  
  # Just MIR and ASM (no IR):
  %(prog)s -m data/yklua.ir.llc.mir -a data/yklua.llc.asm -f __yk_opt_main
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
        '--ir', '-i',
        help='Path to original IR file (optional)'
    )
    
    parser.add_argument(
        '--function', '-f',
        help='Function name to match (if not provided, processes all __yk_opt_ functions)'
    )
    
    parser.add_argument(
        '--csv', '-c',
        help='Output CSV file path'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed block contents'
    )
    
    args = parser.parse_args()
    
    # Validate files exist
    mir_path = Path(args.mir)
    asm_path = Path(args.asm)
    
    if not mir_path.exists():
        print(f"ERROR: MIR file not found: {args.mir}", file=sys.stderr)
        sys.exit(1)
    
    if not asm_path.exists():
        print(f"ERROR: ASM file not found: {args.asm}", file=sys.stderr)
        sys.exit(1)
    
    ir_path = None
    if args.ir:
        ir_path = Path(args.ir)
        if not ir_path.exists():
            print(f"ERROR: IR file not found: {args.ir}", file=sys.stderr)
            sys.exit(1)
    
    try:
        match_blocks(
            args.mir, 
            args.asm, 
            args.ir, 
            args.function, 
            args.csv,
            verbose=args.verbose
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

