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

## Justfile Recipes

Common tasks are defined in the `Justfile`:

```bash
# Set up environment
just init

# Format code
just fmt

# Lint code
just lint

# Run tests
just test

# Extract IR function names
just extract_ir_defined_functions

# Parse assembly to filesystem
just parse_llc_asm_to_fs

# Parse MIR to filesystem
just parse_mir_to_fs

# Parse both ASM and MIR
just parse_to_fs

# Run CLI with custom args
just run -- --input-format mir --print-analysis ir/yklua.mir

# Clean generated files
just clean
```

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
