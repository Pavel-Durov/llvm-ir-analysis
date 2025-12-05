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

# Match IR, MIR, and ASM blocks for all __yk_opt_ functions and output to CSV
match_all_blocks:
	uv run python src/match_blocks.py \
		--mir data/yklua.ir.llc.mir \
		--asm data/yklua.llc.asm \
		--ir data/yklua.ir \
		--csv reports/matched_blocks.csv

# Match IR, MIR, and ASM blocks for a specific function
match_function FUNC:
	uv run python src/match_blocks.py \
		--mir data/yklua.ir.llc.mir \
		--asm data/yklua.llc.asm \
		--ir data/yklua.ir \
		--function {{FUNC}} \
		--csv reports/matched_{{FUNC}}.csv \
		--verbose

# ============================================================================
# Size Distribution Analysis
# ============================================================================

# Analyze block size distribution from CSV file
analyze_csv_size:
	@echo "→ Analysing block size distribution from CSV..."
	uv run python ./src/main.py --analyze-size-distribution db/ir_analysis_basicblocks_fixed.csv

# Analyze block size distribution from ASM file
analyze_asm_size:
	@echo "→ Analysing block size distribution from ASM..."
	uv run python ./src/main.py --analyze-asm-size-distribution data/yklua.llc.asm

# Analyze block size distribution from specific CSV file
analyze_csv_size_file CSV:
	@echo "→ Analysing block size distribution from {{CSV}}..."
	uv run python ./src/main.py --analyze-size-distribution {{CSV}}

# Analyze block size distribution from specific ASM file
analyze_asm_size_file ASM:
	@echo "→ Analysing block size distribution from {{ASM}}..."
	uv run python ./src/main.py --analyze-asm-size-distribution {{ASM}}

# Analyze block size distribution from MIR file
analyze_mir_size:
	@echo "→ Analysing block size distribution from MIR..."
	uv run python ./src/main.py --analyze-mir-size-distribution data/yklua.ir.llc.mir

# Analyze block size distribution from specific MIR file
analyze_mir_size_file MIR:
	@echo "→ Analysing block size distribution from {{MIR}}..."
	uv run python ./src/main.py --analyze-mir-size-distribution {{MIR}}

# ============================================================================
# CSV Generation
# ============================================================================

# Generate ASM blocks CSV with fixed parser (eliminates duplicates)
generate_asm_csv:
	@echo "→ Generating ASM blocks CSV with fixed parser..."
	@echo "  Backing up existing CSV..."
	@if [ -f db/data/asm_blocks.csv ]; then cp db/data/asm_blocks.csv db/data/asm_blocks.csv.backup; fi
	@echo "  Parsing ASM file and generating CSV..."
	uv run python src/main.py data/yklua.llc.asm --export-asm-csv --export-output db/data/asm_blocks.csv
	@echo "  Verifying no duplicates..."
	@DUPLICATES=$$(cut -d',' -f1,2 db/data/asm_blocks.csv | sort | uniq -d | wc -l); \
	if [ $$DUPLICATES -eq 0 ]; then \
		echo "✓ CSV generated successfully with no duplicates"; \
	else \
		echo "⚠ Warning: $$DUPLICATES duplicate function_name,basicblock_id combinations found"; \
	fi

# Generate MIR blocks CSV
generate_mir_csv:
	@echo "→ Generating MIR blocks CSV..."
	@if [ -f db/data/mir_blocks.csv ]; then cp db/data/mir_blocks.csv db/data/mir_blocks.csv.backup; fi
	uv run python src/main.py data/yklua.ir.llc.mir --export-mir-csv --export-output db/data/mir_blocks.csv
	@echo "✓ MIR CSV generated successfully"

# Generate both ASM and MIR CSVs
generate_all_csvs: generate_asm_csv generate_mir_csv
	@echo "✓ All CSV files generated successfully"

# ============================================================================
# Database Setup (PostgreSQL)
# ============================================================================

# Set up PostgreSQL database in Docker and import CSV data
setup_db:
	@echo "→ Setting up PostgreSQL database in Docker..."
	cd db && bash ./setup_postgres.sh

# Start PostgreSQL container
db_start:
	@echo "→ Starting PostgreSQL container..."
	@docker start ir_analysis_postgres 2>/dev/null || docker run -d \
		--name ir_analysis_postgres \
		-e POSTGRES_USER=test \
		-e POSTGRES_PASSWORD=test \
		-e POSTGRES_DB=ir_analysis \
		-p 5432:5432 \
		-v ir_analysis_pgdata:/var/lib/postgresql/data \
		-v $(PWD)/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro \
		postgres:16-alpine
	@echo "✓ Container started. Waiting for PostgreSQL..."
	@sleep 3
	@echo "✓ PostgreSQL is ready!"

# Stop PostgreSQL container
db_stop:
	@echo "→ Stopping PostgreSQL container..."
	@docker stop ir_analysis_postgres
	@echo "✓ Container stopped"

# Restart PostgreSQL container
db_restart:
	@echo "→ Restarting PostgreSQL container..."
	@docker restart ir_analysis_postgres
	@echo "✓ Container restarted"

# Remove PostgreSQL container and data
db_clean:
	@echo "→ Removing PostgreSQL container and data..."
	@docker stop ir_analysis_postgres 2>/dev/null || true
	@docker rm ir_analysis_postgres 2>/dev/null || true
	@docker volume rm ir_analysis_pgdata 2>/dev/null || true
	@echo "✓ Container and data removed"

# Query the database - Functions with most basic blocks
db_top_functions:
	@echo "→ Functions with most basic blocks:"
	@docker exec -it ir_analysis_postgres psql -U test -d ir_analysis -c "SELECT function_name, COUNT(*) as bb_count FROM basicblocks GROUP BY function_name ORDER BY bb_count DESC LIMIT 15;"

# Query the database - Largest basic blocks
db_largest_blocks:
	@echo "→ Largest basic blocks (>50 instructions):"
	@docker exec -it ir_analysis_postgres psql -U test -d ir_analysis -c "SELECT function_name, basicblock_id, number_of_instructions FROM basicblocks WHERE number_of_instructions > 50 ORDER BY number_of_instructions DESC LIMIT 15;"

# Query the database - Database statistics
db_stats:
	@echo "→ Database statistics:"
	@docker exec -it ir_analysis_postgres psql -U test -d ir_analysis -c "SELECT 'Total rows' as metric, COUNT(*) as value FROM basicblocks UNION ALL SELECT 'Unique functions', COUNT(DISTINCT function_name) FROM basicblocks UNION ALL SELECT 'Avg instructions/block', ROUND(AVG(number_of_instructions), 2) FROM basicblocks UNION ALL SELECT 'Max instructions/block', MAX(number_of_instructions) FROM basicblocks;"

# Open database in interactive mode (psql)
db_interactive:
	@echo "→ Opening PostgreSQL interactive shell..."
	@echo "  Tip: Try \\dt, \\d basicblocks, SELECT * FROM basicblocks LIMIT 5;"
	@docker exec -it ir_analysis_postgres psql -U test -d ir_analysis

# View database logs
db_logs:
	@echo "→ PostgreSQL container logs:"
	@docker logs ir_analysis_postgres --tail 50 --follow

gen_plots:
	just gen_bb_plot ./db/data/mir_analysis_basicblocks.csv ./block_analysis.png
	just gen_bb_plot_fast ./db/data/mir_analysis_basicblocks.csv ./block_analysis_fast.png
	just gen_bucket_plot ./db/data/mir_analysis_basicblocks.csv ./bucket_distribution.png

gen_bb_plot CSV OUTPUT_IMAGE:
	uv run python ./scripts/plot_blocks.py {{CSV}} -o {{OUTPUT_IMAGE}}

gen_bb_plot_fast CSV OUTPUT_IMAGE:
	uv run python ./scripts/plot_blocks_fast.py {{CSV}} -o {{OUTPUT_IMAGE}}

gen_bucket_plot CSV OUTPUT_IMAGE:
	uv run python ./scripts/plot_bucket_distribution.py {{CSV}} -o {{OUTPUT_IMAGE}}
# ============================================================================
# Complete Workflow Automation
# ============================================================================

# Run complete analysis pipeline (all steps)
run_all: match_all_blocks setup_db db_stats
	@echo ""
	@echo "✓ Complete analysis pipeline finished!"
	@echo "  - IR/MIR/ASM blocks matched: reports/matched_blocks.csv"
	@echo "  - Database created: db/ir_analysis.db"


run_asm_etl:
	uv run python src/main.py data/yklua.llc.asm --export-asm-csv --export-output db/data/asm_blocks.csv
	bash db/upload_asm_blocks.sh $DB_CONN_STR ./db/data/asm_blocks.csv 
	uv run python ./db/migrations/migrate_add_block_num_generic.py "$DB_CONN_STR" basicblocks_asm --force
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