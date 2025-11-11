#!/usr/bin/env python3
"""
CLI utility to match MIR and ASM basic blocks for a given function.

Matches blocks based on the __yk_trace_basicblock call parameters:
- Extracts the basic block ID (second parameter) from trace calls
- Matches MIR blocks with corresponding ASM blocks
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from parser import MIRParser, ASMParser, YK_TRACE_BASICBLOCK_FUNC
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


def match_blocks(mir_file: str, asm_file: str, function_name: str, verbose: bool = False) -> None:
    """Match MIR and ASM blocks for a given function and print results."""

    print(f"Matching blocks for function: {function_name}")
    print(f"MIR file: {mir_file}")
    print(f"ASM file: {asm_file}")
    print()
    
    # Parse MIR
    mir_parser = MIRParser(allowed_functions={function_name})
    mir_parser.parse(mir_file)
    
    if function_name not in mir_parser.functions:
        print(f"ERROR: Function '{function_name}' not found in MIR file")
        sys.exit(1)
    
    # Parse ASM
    asm_parser = ASMParser(allowed_functions={function_name})
    asm_parser.parse(asm_file)
    
    if function_name not in asm_parser.functions:
        print(f"ERROR: Function '{function_name}' not found in ASM file")
        sys.exit(1)
    
    mir_func = mir_parser.functions[function_name]
    asm_func = asm_parser.functions[function_name]
    
    # Build mapping of trace BB ID -> blocks
    mir_blocks_by_trace_id: Dict[int, List[Block]] = {}
    asm_blocks_by_trace_id: Dict[int, List[Block]] = {}
    
    # Extract trace IDs from MIR blocks
    for block in mir_func.blocks_detail:
        trace_id = extract_trace_bb_id_from_mir_block(block)
        if trace_id is not None:
            if trace_id not in mir_blocks_by_trace_id:
                mir_blocks_by_trace_id[trace_id] = []
            mir_blocks_by_trace_id[trace_id].append(block)
    
    # Extract trace IDs from ASM blocks
    for block in asm_func.blocks_detail:
        trace_id = extract_trace_bb_id_from_asm_block(block)
        if trace_id is not None:
            if trace_id not in asm_blocks_by_trace_id:
                asm_blocks_by_trace_id[trace_id] = []
            asm_blocks_by_trace_id[trace_id].append(block)
    
    # Print summary
    print(f"MIR function: {mir_func.blocks} blocks, {mir_func.total_instructions} instructions")
    print(f"  Blocks with trace calls: {len(mir_blocks_by_trace_id)}")
    print(f"ASM function: {asm_func.blocks} blocks, {asm_func.total_instructions} instructions")
    print(f"  Blocks with trace calls: {len(asm_blocks_by_trace_id)}")
    print()
    
    # Find all trace IDs (union of both)
    all_trace_ids = sorted(set(mir_blocks_by_trace_id.keys()) | set(asm_blocks_by_trace_id.keys()))
    
    if not all_trace_ids:
        print("No blocks with __yk_trace_basicblock calls found")
        return
    
    print("Matched blocks (by trace BB ID):")
    print("=" * 80)
    
    for trace_id in all_trace_ids:
        mir_blocks = mir_blocks_by_trace_id.get(trace_id, [])
        asm_blocks = asm_blocks_by_trace_id.get(trace_id, [])
        
        print(f"\nTrace BB ID: {trace_id}")
        print("-" * 80)
        
        if mir_blocks:
            print(f"MIR blocks ({len(mir_blocks)}):")
            for block in mir_blocks:
                print(f"  Block: {block.block} (line {block.start_line})")
                print(f"    Real Instructions: {block.instructions} (excluding pseudo-ops)")
                print(f"    Total Instructions: {block.total_instructions} (including pseudo-ops)")
                print(f"    Lines: {len(block.instruction_lines)}")
                print("    Content:")
                for line in block.instruction_lines:
                    print(f"      {line.strip()}")
        else:
            print("  MIR: (no matching block)")
        
        if asm_blocks:
            print(f"ASM blocks ({len(asm_blocks)}):")
            for block in asm_blocks:
                print(f"  Block: {block.block} (line {block.start_line})")
                print(f"    Instructions: {block.instructions}")
                print(f"    Lines: {len(block.instruction_lines)}")
                print("    Content:")
                for line in block.instruction_lines:
                    print(f"      {line.strip()}")
        else:
            print("  ASM: (no matching block)")


def main():
    parser = argparse.ArgumentParser(
        description="Match MIR and ASM basic blocks based on __yk_trace_basicblock calls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mir yklua.ir.llc.mir --asm yklua.llc.asm --function getobjname
  %(prog)s -m data/yklua.ir.llc.mir -a data/yklua.llc.asm -f luaG_typeerror
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
        '--function', '-f',
        required=True,
        help='Function name to match'
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
    
    try:
        match_blocks(args.mir, args.asm, args.function, verbose=args.verbose)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

