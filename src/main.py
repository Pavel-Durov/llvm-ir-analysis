import argparse
import sys
from pathlib import Path
from parser import IRParser, MIRParser, ASMParser, list_ir_functions, Function
from export_blocks_csv import export_to_csv
from size_analysis import analyze_csv_blocks, analyze_asm_blocks, analyze_mir_blocks
from utils import safe_name, read_allowed_functions

def analyze_size_distribution(csv_file: Path) -> None:
    """Analyze and print block size distribution from CSV file."""
    
    # Perform analysis
    try:
        analysis = analyze_csv_blocks(csv_file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print results
    print("="*80)
    print("BLOCK SIZE DISTRIBUTION ANALYSIS")
    print("="*80)
    print()
    
    print(f"Total unique blocks: {analysis.total_blocks:,}")
    print(f"  - Traced blocks: {analysis.traced_count:,} ({analysis.traced_percentage:.1f}%)")
    print(f"  - Untraced blocks: {analysis.untraced_count:,} ({analysis.untraced_percentage:.1f}%)")
    print()
    
    print("="*80)
    print("SIZE DISTRIBUTION")
    print("="*80)
    print()
    print(f"{'Size (inst)':<15} {'Traced':<15} {'Traced %':<12} {'Untraced':<15} {'Untraced %':<12}")
    print("-"*80)
    
    for size_label, t_count in analysis.traced_dist.items():
        # Find corresponding untraced count
        u_count = dict(analysis.untraced_dist.items())[size_label]
        t_pct = analysis.traced_dist.get_percentage(t_count)
        u_pct = analysis.untraced_dist.get_percentage(u_count)
        
        print(f"{size_label:<15} {t_count:<15,} {t_pct:<11.1f}% {u_count:<15,} {u_pct:<11.1f}%")
    
    print("-"*80)
    print(f"{'Total':<15} {analysis.traced_count:<15,} {'100.0%':<12} {analysis.untraced_count:<15,} {'100.0%':<12}")
    print()
    
    print("="*80)
    print("AVERAGES")
    print("="*80)
    print()
    print(f"Traced blocks:   {analysis.traced_avg:.2f} instructions/block")
    print(f"Untraced blocks: {analysis.untraced_avg:.2f} instructions/block")
    print(f"Difference:      {analysis.difference:.2f} instructions")
    if analysis.untraced_avg > 0:
        print(f"Ratio:           {analysis.ratio:.2f}×")
    print()
    
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()
    
    tiny_traced_pct = analysis.traced_dist.get_percentage(analysis.traced_dist.tiny)
    tiny_untraced_pct = analysis.untraced_dist.get_percentage(analysis.untraced_dist.tiny)
    
    print(f"• {tiny_traced_pct:.1f}% of traced blocks are tiny (1-3 inst)")
    print(f"• {tiny_untraced_pct:.1f}% of untraced blocks are tiny (1-3 inst)")
    print(f"• Untraced population dominated by {analysis.untraced_dist.tiny:,} tiny blocks")
    print(f"• Selection bias: Only {analysis.traced_percentage:.1f}% of blocks are traced")
    print()

def _print_size_analysis(analysis: 'BlockSizeAnalysis', traced_funcs: dict[str, int], 
                         title: str, file_path: Path, num_functions: int) -> None:
    """Helper function to print size distribution analysis results."""
    print("="*80)
    print(title)
    print("="*80)
    print()
    
    print(f"File: {file_path}")
    print(f"Total functions: {num_functions:,}")
    print(f"Total blocks: {analysis.total_blocks:,}")
    print(f"  - Traced blocks: {analysis.traced_count:,} ({analysis.traced_percentage:.1f}%)")
    print(f"  - Untraced blocks: {analysis.untraced_count:,} ({analysis.untraced_percentage:.1f}%)")
    print()
    
    print("="*80)
    print("SIZE DISTRIBUTION")
    print("="*80)
    print()
    print(f"{'Size (inst)':<15} {'Traced':<15} {'Traced %':<12} {'Untraced':<15} {'Untraced %':<12}")
    print("-"*80)
    
    for size_label, t_count in analysis.traced_dist.items():
        # Find corresponding untraced count
        u_count = dict(analysis.untraced_dist.items())[size_label]
        t_pct = analysis.traced_dist.get_percentage(t_count)
        u_pct = analysis.untraced_dist.get_percentage(u_count)
        
        print(f"{size_label:<15} {t_count:<15,} {t_pct:<11.1f}% {u_count:<15,} {u_pct:<11.1f}%")
    
    print("-"*80)
    print(f"{'Total':<15} {analysis.traced_count:<15,} {'100.0%':<12} {analysis.untraced_count:<15,} {'100.0%':<12}")
    print()
    
    print("="*80)
    print("AVERAGES")
    print("="*80)
    print()
    print(f"Traced blocks:   {analysis.traced_avg:.2f} instructions/block")
    print(f"Untraced blocks: {analysis.untraced_avg:.2f} instructions/block")
    print(f"Difference:      {analysis.difference:.2f} instructions")
    if analysis.untraced_avg > 0:
        print(f"Ratio:           {analysis.ratio:.2f}×")
    print()
    
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()
    
    tiny_traced_pct = analysis.traced_dist.get_percentage(analysis.traced_dist.tiny)
    tiny_untraced_pct = analysis.untraced_dist.get_percentage(analysis.untraced_dist.tiny)
    
    print(f"• {tiny_traced_pct:.1f}% of traced blocks are tiny (1-3 inst)")
    print(f"• {tiny_untraced_pct:.1f}% of untraced blocks are tiny (1-3 inst)")
    print(f"• Untraced population: {analysis.untraced_dist.tiny:,} tiny blocks")
    print(f"• Selection pattern: Only {analysis.traced_percentage:.1f}% of blocks have tracing")
    print()
    
    # Show sample functions with traced blocks
    if traced_funcs:
        print("="*80)
        print("SAMPLE FUNCTIONS WITH TRACING (top 10)")
        print("="*80)
        print()
        for i, (func, count) in enumerate(sorted(traced_funcs.items(), key=lambda x: x[1], reverse=True)[:10], 1):
            print(f"{i:2d}. {func}: {count} traced blocks")
        print()

def analyze_asm_size_distribution(asm_file: Path) -> None:
    """Analyze and print block size distribution from ASM file."""
    
    # Perform analysis
    analysis, traced_funcs = analyze_asm_blocks(asm_file)
    
    # Count unique functions (we need to reparse to get this)
    from parser import ASMParser
    parser = ASMParser()
    parser.parse(str(asm_file), skip_prefixes=[])
    num_functions = len(parser.get_functions())
    
    _print_size_analysis(analysis, traced_funcs, "ASM BLOCK SIZE DISTRIBUTION ANALYSIS", 
                        asm_file, num_functions)

def analyze_mir_size_distribution(mir_file: Path) -> None:
    """Analyze and print block size distribution from MIR file."""
    
    # Perform analysis
    analysis, traced_funcs = analyze_mir_blocks(mir_file)
    
    # Count unique functions (we need to reparse to get this)
    from parser import MIRParser
    parser = MIRParser()
    parser.parse(str(mir_file), skip_patterns=[], skip_prefixes=[])
    num_functions = len(parser.get_functions())
    
    _print_size_analysis(analysis, traced_funcs, "MIR BLOCK SIZE DISTRIBUTION ANALYSIS", 
                        mir_file, num_functions)

ASM_INSTRUCTIONS_FILE = "instructions.s"
IR_INSTRUCTIONS_FILE = "instructions.ll"
MIR_INSTRUCTIONS_FILE = "instructions.mir"

def write_fs_output(functions_map: dict[str, Function], out_dir: Path, instructions_file: str = ASM_INSTRUCTIONS_FILE) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for fn in functions_map.values():
        fn_dir = out_dir / safe_name(fn.name or "function")
        fn_dir.mkdir(parents=True, exist_ok=True)
        for idx, blk in enumerate(fn.blocks_detail):
            blk_name = blk.block or f"block_{idx}"
            blk_dir = fn_dir / safe_name(blk_name)
            blk_dir.mkdir(parents=True, exist_ok=True)
            # Write instruction lines
            (blk_dir / instructions_file).write_text(
                "\n".join(blk.instruction_lines) + ("\n" if blk.instruction_lines else ""),
                encoding="utf-8"
            )

def main():
    parser = argparse.ArgumentParser(
        prog='summarize_ir',
        description='Analyze IR CSV or parse textual LLVM IR/MIR to summarize basic blocks and instructions, '
                    'or compute assembly stats from LLVM-style .s files. Use --input-format to select parser.'
    )
    parser.add_argument('input', nargs='?', help='Path to .csv (from analyze_ir.py), textual .ir/.mir, or .s file (not required for --export-csv)')
    parser.add_argument(
        '--skip-func', dest='skip_functions', metavar='SUBSTR', action='append', default=None,
        help='Skip functions whose name contains SUBSTR. Can be repeated; defaults to __yk_trace_basicblock'
    )
    # Backwards-compat alias for the previous misspelt flag (hidden)
    parser.add_argument(
        '--skip-funcitons', dest='skip_functions', metavar='SUBSTR', action='append', default=None,
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        '--input-format',
        dest='input_format',
        choices=['auto', 'ir', 'mir', 'llc_asm'],
        default='auto',
        help='Select input format: auto-detect, IR (.ll/.ir), MIR (text), or LLVM asm (llc_asm).'
    )
    # Backwards-compat: old flag implies llc_asm (hidden)
    parser.add_argument(
        '--asm-stats',
        dest='asm_stats',
        action='store_true',
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        '--skip-func-prefix',
        dest='skip_func_prefix',
        metavar='PFX',
        action='append',
        default=None,
        help='Skip functions whose name starts with PFX. Can be repeated.'
    )
    parser.add_argument(
        '--output-format',
        dest='output_format',
        choices=['fs'],
        help='If set to "fs", writes parsed output to a filesystem tree.'
    )
    parser.add_argument(
        '--output-dir',
        dest='output_dir',
        help='Output directory for --output-format fs.'
    )
    # Accept common misspelling as alias for convenience
    parser.add_argument(
        '--outuput-dir',
        dest='output_dir',
        help=argparse.SUPPRESS
    )
    parser.add_argument(
        '--output-functions',
        dest='output_functions',
        metavar='FILE',
        help='Write all parsed function names to FILE (one per line). Applies to IR and --asm-stats.'
    )
    parser.add_argument(
        '--func-type',
        dest='func_type',
        choices=['defined', 'declared', 'all'],
        default='defined',
        help='Select which functions to consider for function listing: defined, declared, or all (IR only).'
    )
    parser.add_argument(
        '--print-analysis',
        dest='print_analysis',
        action='store_true',
        default=False,
        help='Print analysis summary to stdout. If omitted, no console output is printed.'
    )
    parser.add_argument(
        '--print-function-list',
        dest='print_function_list',
        action='store_true',
        default=False,
        help='Print the list of function names when --print-analysis is used.'
    )
    parser.add_argument(
        '--functions-file',
        dest='functions_file',
        help='Optional path to a file containing function names to include (one per line).'
    )
    parser.add_argument(
        '--export-csv',
        dest='export_csv',
        action='store_true',
        default=False,
        help='Export block comparison to CSV format (requires --mir-file, --asm-file, and --csv-output).'
    )
    parser.add_argument(
        '--mir-file',
        dest='mir_file',
        help='Path to MIR file for CSV export.'
    )
    parser.add_argument(
        '--asm-file',
        dest='asm_file',
        help='Path to ASM file for CSV export.'
    )
    parser.add_argument(
        '--csv-output',
        dest='csv_output',
        help='Path to output CSV file for block comparison.'
    )
    parser.add_argument(
        '--csv-function',
        dest='csv_function',
        help='Optional function name filter for CSV export (export only this function).'
    )
    parser.add_argument(
        '--analyze-size-distribution',
        dest='analyze_size_dist',
        action='store_true',
        default=False,
        help='Analyze block size distribution from CSV file (requires CSV input with has_tracing_call column).'
    )
    parser.add_argument(
        '--analyze-asm-size-distribution',
        dest='analyze_asm_size_dist',
        action='store_true',
        default=False,
        help='Analyze block size distribution from ASM file (detects __yk_trace_basicblock calls).'
    )

    args = parser.parse_args()

    # Validate input argument based on mode
    if not args.export_csv and not args.analyze_size_dist and not args.analyze_asm_size_dist and not args.input:
        parser.error("the following arguments are required: input (unless using --export-csv, --analyze-size-distribution, or --analyze-asm-size-distribution)")
    
    # Handle ASM size distribution analysis mode (early exit)
    if args.analyze_asm_size_dist:
        if not args.input:
            print("Error: --analyze-asm-size-distribution requires input ASM file", file=sys.stderr)
            sys.exit(1)
        
        asm_path = Path(args.input)
        if not asm_path.exists():
            print(f"Error: ASM file not found: {asm_path}", file=sys.stderr)
            sys.exit(1)
        
        try:
            analyze_asm_size_distribution(asm_path)
            return
        except Exception as e:
            print(f"Error during ASM size distribution analysis: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Handle size distribution analysis mode (early exit)
    if args.analyze_size_dist:
        if not args.input:
            print("Error: --analyze-size-distribution requires input CSV file", file=sys.stderr)
            sys.exit(1)
        
        csv_path = Path(args.input)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
            sys.exit(1)
        
        try:
            analyze_size_distribution(csv_path)
            return
        except Exception as e:
            print(f"Error during size distribution analysis: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Handle CSV export mode (early exit, doesn't need input file)
    if args.export_csv:
        if not args.mir_file:
            print("Error: --export-csv requires --mir-file to be specified", file=sys.stderr)
            sys.exit(1)
        if not args.asm_file:
            print("Error: --export-csv requires --asm-file to be specified", file=sys.stderr)
            sys.exit(1)
        if not args.csv_output:
            print("Error: --export-csv requires --csv-output to be specified", file=sys.stderr)
            sys.exit(1)
        
        # Validate files exist
        if not Path(args.mir_file).exists():
            print(f"Error: MIR file not found: {args.mir_file}", file=sys.stderr)
            sys.exit(1)
        if not Path(args.asm_file).exists():
            print(f"Error: ASM file not found: {args.asm_file}", file=sys.stderr)
            sys.exit(1)
        
        # Perform CSV export
        try:
            export_to_csv(args.mir_file, args.asm_file, args.csv_output, args.csv_function)
            return
        except Exception as e:
            print(f"Error during CSV export: {e}", file=sys.stderr)
            sys.exit(1)

    # Regular mode (non-CSV export)
    filename = args.input
    skip_patterns = args.skip_functions or ['__yk_trace_basicblock']

    # Back-compat mapping: --asm-stats forces llc_asm if not explicitly set
    if args.asm_stats and args.input_format == 'auto':
        args.input_format = 'llc_asm'

    # Auto-detect input format if requested
    if args.input_format == 'auto':
        lower = filename.lower()
        if lower.endswith(('.s', '.asm')):
            args.input_format = 'llc_asm'
        elif lower.endswith(('.mir',)):
            args.input_format = 'mir'
        else:
            # default to IR for other textual LLVM IR (.ll/.ir)
            args.input_format = 'ir'

    # Optional allow-list of function names
    allowed_functions: set[str] | None = None
    if args.functions_file:
        allowed_functions = read_allowed_functions(args.functions_file)

    if args.input_format == 'llc_asm':
        # Use ASMParser
        parser = ASMParser(allowed_functions=allowed_functions)
        # Parse the file
        parser.parse(filename, skip_prefixes=(args.skip_func_prefix or []))

        # Apply func-type filtering
        parser.apply_func_type_filter(filename, args.func_type, skip_patterns, args.skip_func_prefix)
        # Handle filesystem output
        if args.output_format == 'fs':
            if not args.output_dir:
                raise SystemExit("--output-dir is required when --output-format fs is used.")
            write_fs_output(parser.get_functions(), Path(args.output_dir), instructions_file=ASM_INSTRUCTIONS_FILE)

        # Write function names if requested
        if args.output_functions:
            names = sorted(parser.get_functions().keys())  # assembly has only defined functions
            # If user asked for declared only in ASM, it's empty
            if args.func_type == 'declared':
                names = []
            if allowed_functions is not None:
                names = [n for n in names if n in allowed_functions]
            _out = Path(args.output_functions)
            _out.parent.mkdir(parents=True, exist_ok=True)
            _out.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")

        if args.print_analysis:
            report = parser.create_summary_report()
            report.print_to_console(print_function_list=args.print_function_list)
        return

    # IR/MIR summary path - use appropriate parser
    if args.input_format == 'mir':
        parser = MIRParser(allowed_functions=allowed_functions)
    else:  # ir
        parser = IRParser(allowed_functions=allowed_functions)

    parser.parse(filename, skip_patterns=skip_patterns, skip_prefixes=args.skip_func_prefix)
    
    # Apply func-type filtering
    parser.apply_func_type_filter(filename, args.func_type, skip_patterns, args.skip_func_prefix)

    if args.output_format == 'fs':
        if not args.output_dir:
            raise SystemExit("--output-dir is required when --output-format fs is used.")
        # Choose the appropriate instructions file extension based on input format
        if args.input_format == 'mir':
            instr_file = MIR_INSTRUCTIONS_FILE
        elif args.input_format == 'ir':
            instr_file = IR_INSTRUCTIONS_FILE
        else:
            instr_file = IR_INSTRUCTIONS_FILE  # fallback
        write_fs_output(parser.get_functions(), Path(args.output_dir), instructions_file=instr_file)

    # Write function names if requested (IR/MIR path)
    if args.output_functions:
        if args.input_format == 'ir':
            defined, declared = list_ir_functions(filename)
            # Apply substring skip and prefix skip filters
            def keep(name: str) -> bool:
                if any(sub in name for sub in (args.skip_functions or [])):
                    return False
                if any(name.startswith(p) for p in (args.skip_func_prefix or [])):
                    return False
                return True
            if args.func_type == 'defined':
                names = sorted(n for n in defined if keep(n))
            elif args.func_type == 'declared':
                names = sorted(n for n in declared if keep(n))
            else:  # all
                names = sorted(n for n in (defined | declared) if keep(n))
        else:
            # MIR path: only defined functions available from parsed map
            if args.func_type == 'declared':
                names = []
            else:
                names = sorted(parser.functions.keys())
        if allowed_functions is not None:
            names = [n for n in names if n in allowed_functions]
        _out = Path(args.output_functions)
        _out.parent.mkdir(parents=True, exist_ok=True)
        _out.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")

    if args.print_analysis:
        report = parser.create_summary_report()
        report.print_to_console(print_function_list=args.print_function_list)


if __name__ == '__main__':
    main()

