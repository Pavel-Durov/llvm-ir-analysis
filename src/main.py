import argparse
from pathlib import Path
from parser import IRParser, MIRParser, ASMParser, list_ir_functions, Function

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
    parser.add_argument('input', help='Path to .csv (from analyze_ir.py), textual .ir/.mir, or .s file')
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

    args = parser.parse_args()

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
        parser = ASMParser()
        output_fs = (args.output_format == 'fs')
        if output_fs:
            if not args.output_dir:
                raise SystemExit("--output-dir is required when --output-format fs is used.")
            functions_map = parser.parse(filename, skip_prefixes=(args.skip_func_prefix or []))
            # Apply func-type for ASM:
            if args.func_type == 'declared':
                # No declarations in ASM; empty analysis
                functions_map = {}
            # Apply allow-list filter if provided
            if allowed_functions is not None:
                functions_map = {n: fn for n, fn in functions_map.items() if n in allowed_functions}
            # Compute counts from detailed map
            num_functions = len(functions_map)
            function_names = list(functions_map.keys())
            num_basic_blocks = sum(fn.blocks for fn in functions_map.values())
            num_instructions = sum(fn.total_instructions for fn in functions_map.values())
            write_fs_output(functions_map, Path(args.output_dir), instructions_file=ASM_INSTRUCTIONS_FILE)
            # Write function names if requested
            if args.output_functions:
                names = sorted(functions_map.keys())  # assembly has only defined functions
                # If user asked for declared only in ASM, it's empty
                if args.func_type == 'declared':
                    names = []
                _out = Path(args.output_functions)
                _out.parent.mkdir(parents=True, exist_ok=True)
                _out.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
        else:
            if allowed_functions is not None or args.func_type == 'declared':
                # Need per-function detail to filter or to handle 'declared' (which is empty)
                functions_map = parser.parse(filename, skip_prefixes=(args.skip_func_prefix or []))
                if args.func_type == 'declared':
                    functions_map = {}
                if allowed_functions is not None:
                    functions_map = {n: fn for n, fn in functions_map.items() if n in allowed_functions}
                num_functions = len(functions_map)
                function_names = list(functions_map.keys())
                num_basic_blocks = sum(fn.blocks for fn in functions_map.values())
                num_instructions = sum(fn.total_instructions for fn in functions_map.values())
            else:
                # Fast path: just count without detailed parsing
                functions_map = parser.parse(filename, skip_prefixes=(args.skip_func_prefix or []))
                num_functions = len(functions_map)
                function_names = list(functions_map.keys())
                num_basic_blocks = sum(fn.blocks for fn in functions_map.values())
                num_instructions = sum(fn.total_instructions for fn in functions_map.values())
            # Write function names if requested
            if args.output_functions:
                names = sorted(function_names)
                if args.func_type == 'declared':
                    names = []
                if allowed_functions is not None:
                    names = [n for n in names if n in allowed_functions]
                _out = Path(args.output_functions)
                _out.parent.mkdir(parents=True, exist_ok=True)
                _out.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")

        if args.print_analysis:
            avg_instr_per_block = (num_instructions / num_basic_blocks) if num_basic_blocks > 0 else 0.0
            print(f"Functions: {num_functions}")
            if args.print_function_list and function_names:
                print("Function list:")
                for name in function_names:
                    print(f"  {name}")
            print(f"Basic blocks (in functions): {num_basic_blocks}")
            print(f"Instructions (in basic blocks): {num_instructions}")
            print(f"Average instructions per basic block: {avg_instr_per_block:.2f}")
        return

    # IR/MIR summary path - use appropriate parser
    if args.input_format == 'mir':
        parser = MIRParser()
    else:  # ir
        parser = IRParser()

    functions = parser.parse(filename, skip_patterns=skip_patterns, skip_prefixes=args.skip_func_prefix)
    # Apply func-type selection for IR/MIR
    if args.func_type in ('declared', 'all'):
        defined_names = set(functions.keys())
        _, declared_only = list_ir_functions(filename)
        # declared_only returned by list_ir_functions excludes defined already,
        # but recompute 'declared' set with filters
        declared_set = declared_only
        # Apply substring and prefix filters to declared_set
        def keep_name(name: str) -> bool:
            if any(sub in name for sub in (args.skip_functions or [])):
                return False
            if any(name.startswith(p) for p in (args.skip_func_prefix or [])):
                return False
            return True
        declared_filtered = {n for n in declared_set if keep_name(n)}
        if args.func_type == 'declared':
            # Replace with declared-only map (zero blocks)
            functions = {n: Function(name=n) for n in declared_filtered}
        else:  # all
            # Keep existing defined (already filtered), add declared that are not present
            for n in sorted(declared_filtered):
                if n not in functions:
                    functions[n] = Function(name=n)
    elif args.input_format == 'mir' and args.func_type == 'declared':
        # MIR has only defined functions; declared-only => empty map
        functions = {}
    # Apply allow-list in IR/MIR mode, if provided
    if allowed_functions is not None:
        for fn_name in list(functions.keys()):
            if fn_name not in allowed_functions:
                del functions[fn_name]
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
        write_fs_output(functions, Path(args.output_dir), instructions_file=instr_file)
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
                names = sorted(functions.keys())
        if allowed_functions is not None:
            names = [n for n in names if n in allowed_functions]
        _out = Path(args.output_functions)
        _out.parent.mkdir(parents=True, exist_ok=True)
        _out.write_text("\n".join(names) + ("\n" if names else ""), encoding="utf-8")
    if args.print_analysis:
        num_functions = len(functions)
        num_basic_blocks = sum(fn.blocks for fn in functions.values())
        num_instructions = sum(fn.total_instructions for fn in functions.values())
        function_names = list(functions.keys())
        avg_instr_per_block = (num_instructions / num_basic_blocks) if num_basic_blocks > 0 else 0.0
        
        print(f"Functions: {num_functions}")
        if args.print_function_list and function_names:
            print("Function list:")
            for name in sorted(function_names):
                print(f"  {name}")
        print(f"Basic blocks (in functions): {num_basic_blocks}")
        print(f"Instructions (in basic blocks): {num_instructions}")
        print(f"Average instructions per basic block: {avg_instr_per_block:.2f}")


if __name__ == '__main__':
    main()

