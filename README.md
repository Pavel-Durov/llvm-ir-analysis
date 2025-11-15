## LLVM IR/MIR/ASM Analyser

Parses LLVM textual IR, Machine IR (MIR), and assembly dumps to analyse functions, basic blocks, and instructions.

## Quick Commands

```bash
# Analyse IR/MIR/ASM file
uv run python ./src/main.py --input-format mir --print-analysis data/yklua.mir

# Analyse block size distribution (CSV)
uv run python ./src/main.py --analyze-size-distribution db/ir_analysis_basicblocks_fixed.csv

# Analyse block size distribution (ASM)
uv run python ./src/main.py --analyze-asm-size-distribution data/yklua.llc.asm

# Export MIR/ASM comparison to CSV
uv run python ./src/main.py --export-csv \
  --mir-file data/yklua.mir --asm-file data/yklua.asm --csv-output output.csv

# Match blocks across IR/MIR/ASM
uv run python ./src/match_blocks.py --mir data/yklua.mir --asm data/yklua.asm \
  --ir data/yklua.ir --function getobjname --csv output.csv
```

### Features

- **Multi-format support**: IR (.ll/.ir), MIR (.mir), and assembly (.s/.asm)
- **Modular parser architecture**: Separate parsers for each format (IRParser, MIRParser, ASMParser)
- **Size distribution analysis**: Analyse block size distributions from CSV files, showing selection bias between traced and untraced blocks
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

### Analyse block size distribution from CSV

Analyse CSV files exported by the LLVM IR analysis pass to show size distribution and selection bias between traced and untraced blocks.

```bash
# Analyse size distribution from CSV
uv run python ./src/main.py \
  --analyze-size-distribution \
  db/ir_analysis_basicblocks_fixed.csv

# Or use the standalone script in scripts/
./scripts/size_distribution.py db/ir_analysis_basicblocks_fixed.csv
```

**Output includes:**
- Total block counts (traced vs untraced)
- Size distribution table (1-3, 4-6, 7-10, 11-20, 21+ instructions)
- Average instruction counts
- Selection bias statistics
- Key insights about tiny block dominance

**Example output:**
```
SIZE DISTRIBUTION
================================================================================
Size (inst)     Traced          Traced %     Untraced        Untraced %  
--------------------------------------------------------------------------------
1-3             122             7.6%         12,950          63.6%
4-6             492             30.5%        5,092           25.0%
7-10            469             29.1%        1,565           7.7%
11-20           415             25.7%        575             2.8%
21+             114             7.1%         170             0.8%

AVERAGES
Traced blocks:   9.63 instructions/block
Untraced blocks: 3.77 instructions/block
Difference:      5.86 instructions
Ratio:           2.55×
```

**CSV file format required:**
```csv
function_name,basicblock_id,has_tracing_call,number_of_instructions,instructions
```

### Match and display IR/MIR/ASM blocks

The `match_blocks.py` script matches basic blocks across IR, MIR, and ASM representations based on `__yk_trace_basicblock` calls.

```bash
# Match a single function and output to CSV
uv run python ./src/match_blocks.py \
  --mir data/yklua.ir.llc.mir \
  --asm data/yklua.llc.asm \
  --ir data/yklua.ir \
  --function getobjname \
  --csv output.csv

# Match all __yk_opt_ functions
uv run python ./src/match_blocks.py \
  --mir data/yklua.ir.llc.mir \
  --asm data/yklua.llc.asm \
  --ir data/yklua.ir \
  --csv all_matches.csv

# Using Justfile recipes:
just match_function getobjname
just match_all_blocks
```

**CSV Output Columns (tab-separated):**
- `function_name` - Function name (with `__yk_opt_` prefix if applicable)
- `bb_id` - Basic block ID from `__yk_trace_basicblock` call
- `mir_file` - Path to MIR file
- `mir_tbb_line` - MIR traced basic block line number (WITH tracing calls)
- `mir_tbb_raw` - MIR traced basic block raw content (WITH tracing calls)
- `mir_bb_line` - IR basic block line number (WITHOUT tracing calls, from original function)
- `mir_bb_raw` - IR basic block raw content (WITHOUT tracing calls, from original function)
- `asm_bb_raw` - ASM basic block raw content
- `mir_real_inst_count` - Real instruction count in MIR (excluding pseudo-ops)
- `mir_total_inst_count` - Total instruction count in MIR (including pseudo-ops)
- `asm_file` - Path to ASM file
- `asm_line` - ASM basic block line number
- `asm_real_inst_count` - Real instruction count in ASM

**Note:** tbb = traced basic block (with `__yk_trace_basicblock`), bb = basic block (without tracing)

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


## Size Distribution Analysis

### Analyse CSV Block Data

Analyse the distribution of block sizes from a previously exported CSV file:

```bash
# Analyze block size distribution from CSV
uv run python ./src/main.py --analyze-size-distribution db/ir_analysis_basicblocks_fixed.csv
```

**Required CSV Format:**
- Columns: `function_name`, `basicblock_id`, `number_of_instructions`, `instructions`, `has_tracing_call`
- The tool automatically deduplicates based on `(function_name, basicblock_id)`

**Output includes:**
- Total statistics (traced vs untraced blocks)
- Size distribution buckets (1-3, 4-6, 7-10, 11-20, 21+ instructions)
- Average instruction counts
- Key insights about selection bias

### Analyse ASM Block Data

Analyse the distribution of block sizes directly from ASM files (detects `__yk_trace_basicblock` calls):

```bash
# Analyze block size distribution from ASM
uv run python ./src/main.py --analyze-asm-size-distribution data/yklua.llc.asm
```

**Output includes:**
- Total functions and blocks
- Size distribution (traced vs untraced)
- Average instruction counts
- Sample functions with tracing calls
- Key insights about tracing patterns

**Example Output:**
```
================================================================================
ASM BLOCK SIZE DISTRIBUTION ANALYSIS
================================================================================

File: data/yklua.llc.asm
Total functions: 1,218
Total blocks: 11,332
  - Traced blocks: 1,607 (14.2%)
  - Untraced blocks: 9,725 (85.8%)

Size (inst)     Traced          Traced %     Untraced        Untraced %  
--------------------------------------------------------------------------------
1-3             116             7.2        % 2,026           20.8       %
4-6             314             19.5       % 2,111           21.7       %
7-10            492             30.6       % 1,933           19.9       %
11-20           495             30.8       % 2,455           25.2       %
21+             190             11.8       % 1,200           12.3       %
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


## LLC Commands:

```shell
# print mir from .ll
lc -stop-after=machine-cp  ./yklua.ir.ll -o ./yklua.ir.llc.mir
# print asm from .ll
lc ./yklua.ir.ll -o ./yklua.ir.llc.asm
```


\copy basicblocks (function_name, basicblock_id, has_tracing_call, number_of_instructions, instructions) FROM 'ir_analysis_from_sqlite.csv' DELIMITER ',' CSV HEADER