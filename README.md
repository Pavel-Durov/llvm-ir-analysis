## LLVM IR/MIR/ASM Analyser

Parses LLVM textual IR, Machine IR (MIR), and assembly dumps to analyse functions, basic blocks, and instructions.

### Features

- **Multi-format support**: IR (.ll/.ir), MIR (.mir), and assembly (.s/.asm)
- **Modular parser architecture**: Separate parsers for each format (IRParser, MIRParser, ASMParser)
- **Function filtering**: Skip by substring or prefix patterns
- **Function type selection**: Analyse defined, declared, or all functions (IR only)
- **Filesystem output**: Export parsed blocks to a directory tree structure
- **Statistical analysis**: Count functions, basic blocks, instructions, and averages
- **MIR pseudo-instruction filtering**: Emulates LLVM's MachineInstr predicates to exclude debug/pseudo/meta instructions

## Installation

```shell
just init
```

## Quick Start

### Analyse IR file

```bash
uv run python ./src/main.py --input-format ir --print-analysis ir/yklua.ir
```

### Analyse MIR file (with pseudo-instruction filtering)

```bash
uv run python ./src/main.py --input-format mir --print-analysis ir/yklua.mir
```

### Analyse assembly file

```bash
uv run python ./src/main.py --input-format llc_asm --print-analysis data/yklua.llc.asm
```

### Parse to filesystem

```bash
uv run python ./src/main.py \
  --input-format llc_asm \
  --output-format fs \
  --output-dir ./temp/analysis \
  data/yklua.llc.asm
```

### Export MIR/ASM block comparison to CSV

```bash
# Export all functions with tracing calls
uv run python ./src/main.py \
  --export-csv \
  --mir-file data/yklua.ir.llc.mir \
  --asm-file data/yklua.llc.asm \
  --csv-output blocks_comparison.csv

# Export specific function only
uv run python ./src/main.py \
  --export-csv \
  --mir-file data/yklua.ir.llc.mir \
  --asm-file data/yklua.llc.asm \
  --csv-output luaG_typeerror.csv \
  --csv-function luaG_typeerror
```

### Match and display MIR/ASM blocks

```bash
# Display matched blocks for a specific function
uv run python ./src/match_blocks.py \
  --mir data/yklua.ir.llc.mir \
  --asm data/yklua.llc.asm \
  --function luaG_typeerror
```

## CLI Options

### Input

- `input` - Path to input file (.ir, .mir, .s, .asm)
- `--input-format {auto,ir,mir,llc_asm}` - Input format (default: auto)

### Filtering

- `--skip-func SUBSTR` - Skip functions containing substring (repeatable)
- `--skip-func-prefix PREFIX` - Skip functions starting with prefix (repeatable)
- `--func-type {defined,declared,all}` - Function type to analyse (default: defined)
- `--functions-file FILE` - File with function names to include (one per line)

### Output

- `--output-format fs` - Write blocks to filesystem tree
- `--output-dir DIR` - Output directory for filesystem mode
- `--output-functions FILE` - Write function names to file
- `--print-analysis` - Print statistics to stdout
- `--print-function-list` - Print function names (requires --print-analysis)

### CSV Export (MIR/ASM Comparison)

Exports block-level comparison data for functions with `__yk_trace_basicblock` calls.

CSV columns: `function_name`, `bb_id`, `mir_file`, `mir_line`, `mir_bb_raw`, `mir_real_inst_count`, `mir_total_inst_count`, `asm_file`, `asm_line`, `asm_bb_raw`, `asm_real_inst_count`

- `--export-csv` - Enable CSV export mode
- `--mir-file FILE` - Path to MIR file for comparison
- `--asm-file FILE` - Path to ASM file for comparison
- `--csv-output FILE` - Path to output CSV file
- `--csv-function FUNC` - Optional: export only specific function


## Testing

Run the test suite:

```shell
just test
```

### Pre-commit Setup

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

What runs:
- Ruff (autofix + format)
- Unit tests via pytest


## LLC Commands:

```shell
# print mir from .ll
lc -stop-after=machine-cp  ./yklua.ir.ll -o ./yklua.ir.llc.mir
# print asm from .ll
lc ./yklua.ir.ll -o ./yklua.ir.llc.asm
```