#!/bin/bash
# Setup database table and upload ASM/MIR blocks data
# Usage: ./setup_and_upload.sh <postgres_connection_string> <input_csv> [table_name]

set -e

CONN_STR="${1:-}"
INPUT_CSV="${2:-basicblocks.csv}"
TABLE_NAME="${3:-basicblocks_asm}"

if [ -z "$CONN_STR" ]; then
    echo "Usage: $0 <postgres_connection_string> <input_csv> [table_name]"
    echo ""
    echo "Example:"
    echo "  $0 'postgresql://user:password@host/db' asm_blocks.csv"
    echo "  $0 'postgresql://user:password@host/db' mir_blocks.csv basicblock_mir"
    echo ""
    echo "This script will:"
    echo "  1. Create the table (if it doesn't exist)"
    echo "  2. Validate the CSV header format"
    echo "  3. Upload the data"
    echo ""
    echo "Default table name: basicblock_asm"
    echo ""
    exit 1
fi

if [ ! -f "$INPUT_CSV" ]; then
    echo "Error: Input file '$INPUT_CSV' not found!"
    exit 1
fi

FULL_PATH="$(cd "$(dirname "$INPUT_CSV")" && pwd)/$(basename "$INPUT_CSV")"

echo ""
echo "==================================================================="
echo "DATABASE SETUP AND UPLOAD"
echo "==================================================================="
echo ""
echo "→ Database connection: ${CONN_STR%%@*}@***"
echo "→ Input file: $INPUT_CSV"
echo "→ Target table: $TABLE_NAME"
echo ""

# Validate CSV header (strip trailing whitespace and line endings)
EXPECTED_HEADER="function_name,basicblock_id,has_tracing_call,number_of_instructions,instructions"
ACTUAL_HEADER=$(head -n 1 "$INPUT_CSV" | tr -d '\r\n\t' | sed 's/[[:space:]]*$//')

if [ "$ACTUAL_HEADER" != "$EXPECTED_HEADER" ]; then
    echo "✗ Error: CSV header does not match expected format!"
    echo ""
    echo "Expected: $EXPECTED_HEADER"
    echo "Actual:   $ACTUAL_HEADER"
    echo ""
    echo "Debug (char by char):"
    echo "  Expected bytes: $(echo -n "$EXPECTED_HEADER" | od -An -tx1c)"
    echo "  Actual bytes:   $(head -n 1 "$INPUT_CSV" | od -An -tx1c)"
    echo ""
    exit 1
fi

echo "✓ CSV header validated"
echo ""

# Create table and upload data
echo "→ Creating table and uploading data..."
echo ""

psql "${CONN_STR}" << SQL
-- Create the table if it doesn't exist
CREATE TABLE IF NOT EXISTS ${TABLE_NAME} (
    id SERIAL PRIMARY KEY,
    function_name TEXT NOT NULL,
    basicblock_id TEXT NOT NULL,
    has_tracing_call BOOLEAN NOT NULL,
    number_of_instructions INTEGER NOT NULL,
    instructions TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ${TABLE_NAME}_unique_function_block UNIQUE (function_name, basicblock_id)
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_function_name ON ${TABLE_NAME}(function_name);
CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_has_tracing ON ${TABLE_NAME}(has_tracing_call);
CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_num_instructions ON ${TABLE_NAME}(number_of_instructions);
CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_function_bb ON ${TABLE_NAME}(function_name, basicblock_id);
CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_tracing_instructions ON ${TABLE_NAME}(has_tracing_call, number_of_instructions);

-- Add table comment
COMMENT ON TABLE ${TABLE_NAME} IS 'Stores basic block information with tracing metadata';

-- Display table info
\d ${TABLE_NAME}

-- Clear existing data (optional - comment out if you want to append)
TRUNCATE ${TABLE_NAME} RESTART IDENTITY;

-- Import CSV data
\copy ${TABLE_NAME} (function_name, basicblock_id, has_tracing_call, number_of_instructions, instructions) FROM '${FULL_PATH}' DELIMITER ',' CSV HEADER

-- Display statistics
SELECT 
    'Upload Summary' AS "Report",
    COUNT(*) AS "Total Rows",
    COUNT(DISTINCT function_name) AS "Unique Functions",
    SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) AS "Traced Blocks",
    SUM(CASE WHEN NOT has_tracing_call THEN 1 ELSE 0 END) AS "Untraced Blocks",
    SUM(number_of_instructions) AS "Total Instructions",
    ROUND(AVG(number_of_instructions)::numeric, 2) AS "Avg Instr/Block"
FROM ${TABLE_NAME};

-- Show sample of uploaded data
SELECT
    function_name,
    basicblock_id,
    has_tracing_call,
    number_of_instructions,
    LEFT(instructions, 50) || '...' AS instructions_preview
FROM ${TABLE_NAME}
ORDER BY id
LIMIT 5;
SQL



echo ""
echo "→ Uploading to database..."
psql "${CONN_STR}" << SQL
TRUNCATE ${TABLE_NAME} RESTART IDENTITY;
\copy ${TABLE_NAME} (function_name, basicblock_id, has_tracing_call, number_of_instructions, instructions) FROM '${FULL_PATH}' DELIMITER ',' CSV HEADER
SELECT COUNT(*) AS total_rows FROM ${TABLE_NAME};
SQL
