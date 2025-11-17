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

# 3. Run analyses
./run_analysis.sh "$DB_CONN_STR" summary
./run_analysis.sh "$DB_CONN_STR" distribution
./run_analysis.sh "$DB_CONN_STR" mvir

# 4. Generate all analyses and save to file
./run_analysis.sh "$DB_CONN_STR" all > analysis_results.txt 2>&1
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



