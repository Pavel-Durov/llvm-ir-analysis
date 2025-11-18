# Database Setup and Analysis

This directory contains scripts for setting up a PostgreSQL database to analyse LLVM IR/MIR/ASM basic blocks with tracing metadata.

## Prerequisites

- PostgreSQL database server
- `psql` command-line tool
- Connection string to your database

## Quick Start

### Option 1: Setup and Upload in One Step

```bash
# Create table and upload data in one command
./setup_and_upload.sh "$DB_CONN_STR" asm_blocks.csv
```

### Option 2: Manual Steps

```bash
# Step 1: Create the table
psql "$DB_CONN_STR" -f create_table.sql

# Step 2: Upload data
./upload_to_db.sh "$DB_CONN_STR" asm_blocks.csv

# Step 3: Run analysis
./run_analysis.sh "$DB_CONN_STR" summary
```

## Database Schema

```sql
CREATE TABLE basicblocks (
    id SERIAL PRIMARY KEY,
    function_name TEXT NOT NULL,
    basicblock_id TEXT NOT NULL,
    has_tracing_call BOOLEAN NOT NULL,
    number_of_instructions INTEGER NOT NULL,
    instructions TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_function_block UNIQUE (function_name, basicblock_id)
);
```

### Indices

The following indices are created for optimal query performance:

- `idx_basicblocks_function_name` — Function lookups
- `idx_basicblocks_has_tracing` — Filtering by tracing status
- `idx_basicblocks_num_instructions` — Instruction count queries
- `idx_basicblocks_function_bb` — Function + block lookups
- `idx_basicblocks_tracing_instructions` — Common query patterns

## Scripts

### `validate_data.py`

**Comprehensive data validation for uploaded basicblocks**

```bash
python3 validate_data.py "$DB_CONN_STR"
```

This script performs extensive validation checks on the database:

**1. Basic Statistics**
- Total row count
- Unique function count
- Original vs optimised function breakdown

**2. Data Integrity Checks**
- NULL value detection in critical fields
- Empty string detection
- Data type validation

**3. Tracing Call Validation**
- Verifies `__yk_opt_` functions have **no tracing calls** (critical!)
- Checks tracing call distribution in original functions
- Reports any violations

**4. Function Matching**
- Identifies original ↔ optimised function pairs
- Detects orphaned optimised functions (no original)
- Shows matching statistics

**5. Instruction Count Statistics**
- Min/max/mean/median instruction counts
- Comparison between original and optimised functions
- Average reduction percentages

**6. Matching Block Statistics**
- Statistics for blocks present in both original and optimised
- Average instruction reduction per block
- Top functions by block count

**7. Validation Summary**
- Overall pass/fail status
- List of detected issues
- Data quality score

**Key Validation Rules:**
- ✓ `__yk_opt_*` functions must have `has_tracing_call = false`
- ✓ No NULL values in critical fields
- ✓ Function pairs should match (original ↔ optimised)
- ✓ Instruction counts should be positive

**Example Output:**
```
================================================================================
  Validation Summary
================================================================================

✓ ALL VALIDATION CHECKS PASSED

The database contains valid data with:
  • 2,847 matched function pairs (original ↔ optimised)
  • No critical data integrity issues
  • Correct tracing call distribution
```

### Combined View (MIR + ASM)

#### `basicblocks_combined` — Unified view of MIR and ASM data

**Combine basicblocks (MIR) and basicblocks_asm (ASM) data**

This view joins MIR and ASM data on `function_name` and `basicblock_id`, excluding `__yk_opt_*` functions.

```bash
# Create the view
./manage_combined_view.sh "$DB_CONN_STR" create

# Or manually
psql "$DB_CONN_STR" -f create_combined_view.sql

# Run analysis queries
./manage_combined_view.sh "$DB_CONN_STR" query

# Refresh materialized view (after data changes)
./manage_combined_view.sh "$DB_CONN_STR" refresh

# Quick statistics
./manage_combined_view.sh "$DB_CONN_STR" stats

# Drop the view
./manage_combined_view.sh "$DB_CONN_STR" drop
```

**View columns:**
- `function_name` — Function name
- `basicblock_id` — Block identifier (e.g., "BB#23")
- `mir_instructions_count` — Number of MIR instructions
- `mir_instructions` — Full MIR instruction text
- `mir_id` — Row ID from basicblocks table (NULL if no MIR data)
- `asm_instruction_count` — Number of ASM instructions
- `asm_instructions` — Full ASM instruction text
- `asm_id` — Row ID from basicblocks_asm table (NULL if no ASM data)

**Key features:**
- FULL OUTER JOIN ensures all blocks appear (even if only in MIR or ASM)
- Excludes `__yk_opt_*` functions automatically
- Check `mir_id IS NOT NULL` and `asm_id IS NOT NULL` to filter matched blocks

**Example queries:**
```sql
-- Blocks with both MIR and ASM data
SELECT *
FROM basicblocks_combined
WHERE mir_id IS NOT NULL AND asm_id IS NOT NULL;

-- Largest instruction differences
SELECT
    function_name,
    basicblock_id,
    mir_instructions_count,
    asm_instruction_count,
    (mir_instructions_count - asm_instruction_count) AS diff
FROM basicblocks_combined
WHERE mir_id IS NOT NULL AND asm_id IS NOT NULL
ORDER BY ABS(mir_instructions_count - asm_instruction_count) DESC
LIMIT 20;

-- Function-level statistics
SELECT
    function_name,
    COUNT(*) as num_blocks,
    SUM(mir_instructions_count) as total_mir,
    SUM(asm_instruction_count) as total_asm,
    SUM(mir_instructions_count - asm_instruction_count) as total_reduction
FROM basicblocks_combined
WHERE mir_id IS NOT NULL AND asm_id IS NOT NULL
GROUP BY function_name
ORDER BY total_reduction DESC;
```

**Query tips:**
- Use `mir_id IS NOT NULL AND asm_id IS NOT NULL` to filter matched blocks
- Use `mir_id IS NOT NULL AND asm_id IS NULL` for MIR-only blocks
- Use `asm_id IS NOT NULL AND mir_id IS NULL` for ASM-only blocks

### Database Migrations

#### `migrate_add_block_num` — Add numeric block ID column

**Add `basicblock_id_num` column with parsed block numbers**

This migration adds a new `INTEGER` column that extracts the numeric portion from `basicblock_id` strings.

```bash
# Option 1: Migrate all tables at once (basicblocks + basicblocks_asm)
./migrate_all_tables.sh "$DB_CONN_STR"

# Option 2: Migrate specific tables
./migrate_basicblocks.sh "$DB_CONN_STR"
./migrate_basicblocks_asm.sh "$DB_CONN_STR"

# Option 3: Generic version for any table
python3 migrate_add_block_num_generic.py "$DB_CONN_STR" basicblocks_asm

# Option 4: Legacy - basicblocks only (Python with detailed output)
python3 migrate_add_block_num.py "$DB_CONN_STR"

# Option 5: Legacy - basicblocks only (Pure SQL)
psql "$DB_CONN_STR" -f migrate_add_block_num.sql
```

**What it does:**
- Adds `basicblock_id_num INTEGER` column
- Parses block IDs: `"BB#23"` → `23`, `"block_45"` → `45`
- Creates index on the new column
- Validates the migration

**Parsing patterns:**
- `BB#<num>` or `bb#<num>` → extracts `<num>`
- `block_<num>` or `block#<num>` → extracts `<num>`
- Any string with digits → extracts first number

**Options:**
```bash
# Dry run (rollback after showing results)
python3 migrate_add_block_num.py "$DB_CONN_STR" --dry-run

# Force re-run (drop and recreate column)
python3 migrate_add_block_num.py "$DB_CONN_STR" --force

# Rollback migration
psql "$DB_CONN_STR" -f rollback_add_block_num.sql
# or
./run_migration.sh "$DB_CONN_STR" --rollback
```

**Example output:**
```
================================================================================
  Migration Summary
================================================================================

✓ SUCCESS: All rows have parsed block numbers

  Total rows:           37,859
  Rows with number:     37,859
  Rows without number:  0
  Number range:         0 - 1,234
  Coverage:             100.00%
```

**After migration, the schema becomes:**
```sql
CREATE TABLE basicblocks (
    ...
    basicblock_id TEXT NOT NULL,
    basicblock_id_num INTEGER,  -- NEW!
    ...
);
```

**Use cases:**
- Numeric sorting of blocks: `ORDER BY basicblock_id_num`
- Range queries: `WHERE basicblock_id_num BETWEEN 10 AND 50`
- Aggregations: `AVG(number_of_instructions) ... GROUP BY basicblock_id_num`

### `setup_and_upload.sh`

**Complete setup in one command**

```bash
./setup_and_upload.sh "$DB_CONN_STR" <csv_file>
```

Features:
- ✓ Creates table if it doesn't exist
- ✓ Validates CSV header format
- ✓ Creates performance indices
- ✓ Uploads data
- ✓ Shows upload statistics
- ✓ Displays sample data

**Example:**
```bash
./setup_and_upload.sh "postgresql://user:pass@localhost/analysis" asm_blocks.csv
```

### `create_table.sql`

**Create the database table manually**

```bash
psql "$DB_CONN_STR" -f create_table.sql
```

Features:
- Creates `basicblocks` table
- Creates performance indices
- Adds table and column comments
- Shows table structure and size

### `upload_to_db.sh`

**Upload CSV data to existing table**

```bash
./upload_to_db.sh "$DB_CONN_STR" <csv_file>
```

Features:
- Validates CSV header
- Truncates existing data
- Imports CSV with proper escaping
- Shows row count

**Example:**
```bash
./upload_to_db.sh "$DB_CONN_STR" mir_blocks.csv
```

### `run_analysis.sh`

**Run SQL analysis queries**

```bash
./run_analysis.sh "$DB_CONN_STR" [query_type]
```

Query types:
- `distribution` — Block size distribution (default)
- `summary` — Summary statistics
- `function` — Function-level statistics
- `tracing` — Tracing coverage analysis
- `optimization` — Optimization impact
- `hotpath` — Hot path identification
- `overhead` — Detailed overhead analysis
- `mvir` — MVIR v2 analysis
- `all` — Run all queries

**Examples:**
```bash
./run_analysis.sh "$DB_CONN_STR" summary
./run_analysis.sh "$DB_CONN_STR" distribution
./run_analysis.sh "$DB_CONN_STR" all
```

## Generating CSV Data

Use the main Python script to export ASM or MIR blocks to CSV:

### Export ASM Blocks

```bash
uv run python ../src/main.py ../data/yklua.llc.asm \
  --export-asm-csv \
  --export-output asm_blocks.csv
```

### Export MIR Blocks

```bash
uv run python ../src/main.py ../data/yklua.ir.llc.mir \
  --export-mir-csv \
  --export-output mir_blocks.csv
```

### Export Specific Function

```bash
uv run python ../src/main.py ../data/yklua.llc.asm \
  --export-asm-csv \
  --export-output luaV_execute.csv \
  --export-function luaV_execute
```

## Complete Workflow Example

```bash
# 1. Generate CSV from ASM file
cd /path/to/llvm-ir-analysis
uv run python src/main.py data/yklua.llc.asm \
  --export-asm-csv \
  --export-output db/asm_blocks.csv

# 2. Setup database and upload
cd db
./setup_and_upload.sh "$DB_CONN_STR" asm_blocks.csv

# 3. Validate uploaded data
python3 validate_data.py "$DB_CONN_STR"

# 4. Run analyses (if validation passed)
./run_analysis.sh "$DB_CONN_STR" summary
./run_analysis.sh "$DB_CONN_STR" distribution
./run_analysis.sh "$DB_CONN_STR" mvir

# 5. Generate all analyses and save to file
./run_analysis.sh "$DB_CONN_STR" all > analysis_results.txt 2>&1
```

### Quick Validation Workflow

```bash
# Upload data and validate in one go
./setup_and_upload.sh "$DB_CONN_STR" asm_blocks.csv && \
  python3 validate_data.py "$DB_CONN_STR"
```

## CSV Format

All CSV files must have this exact header:

```csv
function_name,basicblock_id,has_tracing_call,number_of_instructions,instructions
```

Example rows:

```csv
main,BB#0,true,8,"movl $131, %edi; movl $0, %esi; callq __yk_trace_basicblock@PLT; ..."
luaV_execute,BB#23,false,5,"movq %rax, %rdi; callq free@PLT; ..."
```

## Troubleshooting

### CSV Header Mismatch

```
Error: CSV header does not match expected format!
```

**Solution:** Regenerate the CSV using the export commands above.

### Connection Refused

```
psql: error: could not connect to server
```

**Solution:** Check your connection string and PostgreSQL server status.

### Permission Denied

```
ERROR: permission denied for table basicblocks
```

**Solution:** Ensure your database user has CREATE and INSERT permissions.

### Duplicate Key Error

```
ERROR: duplicate key value violates unique constraint "unique_function_block"
```

**Solution:** The script truncates the table by default. If you're appending data, you may need to handle duplicates differently.

## Performance Tips

1. **Batch uploads** — Upload larger CSV files instead of many small ones
2. **Analyze after upload** — Run `ANALYZE basicblocks;` after large uploads
3. **Vacuum regularly** — Run `VACUUM ANALYZE basicblocks;` periodically
4. **Monitor index usage** — Check index usage with query plans

## Database Maintenance

```bash
# Connect to database
psql "$DB_CONN_STR"

# Analyze table statistics
ANALYZE basicblocks;

# Vacuum and analyze
VACUUM ANALYZE basicblocks;

# Check table size
SELECT pg_size_pretty(pg_total_relation_size('basicblocks'));

# Check index sizes
SELECT
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_indexes
WHERE tablename = 'basicblocks';

# View active connections
SELECT * FROM pg_stat_activity WHERE datname = current_database();
```

## Environment Variables

You can set the connection string as an environment variable:

```bash
# In your shell profile (.bashrc, .zshrc, etc.)
export DB_CONN_STR="postgresql://user:password@localhost:5432/analysis"

# Then use scripts without specifying connection string each time
./setup_and_upload.sh "$DB_CONN_STR" asm_blocks.csv
./run_analysis.sh "$DB_CONN_STR" summary
```

## Security Notes

- **Never commit connection strings** with passwords to version control
- Use environment variables or `.envrc` files (add to `.gitignore`)
- Consider using PostgreSQL `.pgpass` file for password management
- Use SSL connections for remote databases

## Support

For issues or questions about:
- **CSV generation:** See `../src/main.py` and `../src/export_blocks_csv.py`
- **SQL queries:** See `query_*.sql` files in this directory
- **Database schema:** See `create_table.sql`



