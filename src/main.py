import argparse
import sys
from pathlib import Path
from parser import IRParser, MIRParser, ASMParser, list_ir_functions, Function
from export_blocks_csv import export_to_csv

def read_allowed_functions(file_path: str | Path) -> set[str]:
    p = Path(file_path)
    if not p.exists():
        raise SystemExit(f"--functions-file not found: {p}")
    raw = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {ln.strip() for ln in raw if ln.strip() and not ln.lstrip().startswith("#")}

def safe_name(name: str) -> str:
        # Replace path separators and disallowed chars with underscore
        allowed = "-._abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return "".join(ch if ch in allowed else "_" for ch in name)

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

    args = parser.parse_args()

    # Validate input argument based on mode
    if not args.export_csv and not args.input:
        parser.error("the following arguments are required: input (unless using --export-csv)")
    
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

