#!/bin/env bash

# LLVM IR/MIR/ASM Analysis Justfile
# ==================================
# Common tasks for analysing LLVM IR, Machine IR, and assembly files.
#
# Usage:
#   just <recipe>        - Run a specific recipe
#   just --list          - List all available recipes
#   just run -- <args>   - Run CLI with custom arguments

# Default recipe - show help
default:
	@just --list

# ============================================================================
# Analysis Workflows
# ============================================================================

# Extract defined function names from IR (skips __yk_opt functions)
extract_ir_defined_functions:
	@echo "→ Extracting defined functions from IR..."
	uv run python ./src/main.py \
		--input-format ir \
		--skip-func __yk_opt \
		--func-type defined \
		--output-functions ./temp/ir_defined_funcs.txt \
		--print-analysis \
		ir/yklua.ir

# Parse assembly to filesystem (requires extracted IR functions)
parse_llc_asm_to_fs: extract_ir_defined_functions
	@echo "→ Parsing assembly to filesystem..."
	uv run python ./src/main.py \
		--functions-file ./temp/ir_defined_funcs.txt \
		--input-format llc_asm \
		--output-format fs \
		--output-dir ./temp/analysis \
		--print-analysis \
		data/yklua.llc.asm

# Analyse assembly without filesystem output
llc_asm_analysis:
	@echo "→ Analysing assembly statistics..."
	uv run python ./src/main.py \
		--input-format llc_asm \
		--print-analysis \
		data/yklua.llc.asm

# Parse MIR to filesystem (requires extracted IR functions, filters pseudo-instructions)
parse_mir_to_fs: extract_ir_defined_functions
	@echo "→ Parsing MIR to filesystem..."
	uv run python ./src/main.py \
		--functions-file ./temp/ir_defined_funcs.txt \
		--input-format mir \
		--output-format fs \
		--output-dir ./temp/analysis \
		--print-analysis \
		data/yklua.mir

# Analyse MIR without filesystem output (filters debug/pseudo/meta instructions)
mir_analysis:
	@echo "→ Analysing MIR statistics..."
	uv run python ./src/main.py \
		--input-format mir \
		--print-analysis \
		data/yklua.mir

# Print statistics for both MIR and assembly
print_analysis: mir_analysis llc_asm_analysis

# Parse both assembly and MIR to filesystem
parse_to_fs: parse_llc_asm_to_fs parse_mir_to_fs


compile_llc_asm:
	@echo "→ Compiling LLVM assembly..."
	llc ./data/yklua.ir -o ./data/yklua.ll


dump_func_stats:
	@echo "→ Dumping function statistics..."
	uv run python ./src/main.py --input-format llc_asm --print-analysis --print-function-list ./data/yklua.llc.asm  > reports/func.llc_asm
	uv run python ./src/main.py --input-format mir --print-analysis --print-function-list ./data/yklua.mir > reports/func.mir
	uv run python ./src/main.py --input-format ir --print-analysis --print-function-list ./data/yklua.ir > reports/func.ir

func_stats:
	@echo "asm stats:"
	uv run python ./src/main.py --input-format llc_asm --print-analysis ./data/yklua.llc.asm
	@echo "mir stats:"
	uv run python ./src/main.py --input-format mir --print-analysis ./data/yklua.mir
	@echo "ir stats:"
	uv run python ./src/main.py --input-format ir --print-analysis ./data/yklua.ir

compare_blocks:
	uv run python src/match_blocks.py   --mir data/yklua.ir.llc.mir   --asm data/yklua.llc.asm   --function getobjname
# ============================================================================
# Development & Maintenance
# ============================================================================

# Set up local environment with dev tools
init:
	@echo "→ Setting up development environment..."
	uv sync --extra dev

# Format code with ruff
fmt:
	@echo "→ Formatting code..."
	uv run ruff format .

# Lint code with ruff
lint:
	@echo "→ Linting code..."
	uv run ruff check .

# Run test suite
test:
	@echo "→ Running tests..."
	uv run pytest -q

# Run the CLI with custom arguments
# Example: just run -- --input-format ir --func-type defined ir/yklua.ir
run *ARGS:
	uv run python ./src/main.py {{ARGS}}

# Clean generated artifacts and caches
clean:
	@echo "→ Cleaning generated files..."
	rm -rf ./temp .pytest_cache
	find ./src -name __pycache__ -type d -exec rm -rf {} +
	@echo "✓ Cleaned"