-- Create basicblocks table for LLVM IR/MIR/ASM analysis
-- This table stores basic block information with tracing metadata
--
-- Usage:
--   psql "$DB_CONN_STR" -f create_table.sql

-- Drop existing table (WARNING: This will delete all data!)
-- Uncomment the next line if you want to recreate the table from scratch
-- DROP TABLE IF EXISTS basicblocks CASCADE;

-- Create the basicblocks table
CREATE TABLE IF NOT EXISTS basicblocks (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Basic block identification
    function_name TEXT NOT NULL,
    basicblock_id TEXT NOT NULL,
    
    -- Tracing metadata
    has_tracing_call BOOLEAN NOT NULL,
    
    -- Instruction metrics
    number_of_instructions INTEGER NOT NULL CHECK (number_of_instructions >= 0),
    
    -- Raw instruction data
    instructions TEXT NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint on function + block combination
    CONSTRAINT unique_function_block UNIQUE (function_name, basicblock_id)
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_basicblocks_function_name 
    ON basicblocks(function_name);

CREATE INDEX IF NOT EXISTS idx_basicblocks_has_tracing 
    ON basicblocks(has_tracing_call);

CREATE INDEX IF NOT EXISTS idx_basicblocks_num_instructions 
    ON basicblocks(number_of_instructions);

CREATE INDEX IF NOT EXISTS idx_basicblocks_function_bb 
    ON basicblocks(function_name, basicblock_id);

-- Create a composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_basicblocks_tracing_instructions 
    ON basicblocks(has_tracing_call, number_of_instructions);

-- Add table comment
COMMENT ON TABLE basicblocks IS 
    'Stores LLVM IR/MIR/ASM basic block information with tracing metadata for analysis';

COMMENT ON COLUMN basicblocks.function_name IS 
    'Name of the function containing this basic block';

COMMENT ON COLUMN basicblocks.basicblock_id IS 
    'Identifier for the basic block (e.g., BB#0, bb.1)';

COMMENT ON COLUMN basicblocks.has_tracing_call IS 
    'Whether this block contains __yk_trace_basicblock call';

COMMENT ON COLUMN basicblocks.number_of_instructions IS 
    'Number of real instructions in the block (excluding pseudo-ops for MIR)';

COMMENT ON COLUMN basicblocks.instructions IS 
    'Raw instruction text, semicolon-separated';

-- Display table structure
\d basicblocks

-- Display table info
SELECT 
    schemaname AS schema,
    tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE tablename = 'basicblocks';

-- Display index info
SELECT
    indexname AS index_name,
    indexdef AS definition,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_indexes
WHERE tablename = 'basicblocks'
ORDER BY indexname;

\echo ''
\echo '===================================================================='
\echo 'Creating ASM-specific table: basicblocks_asm'
\echo '===================================================================='
\echo ''

-- Create the basicblocks_asm table (for ASM analysis)
-- DROP TABLE IF EXISTS basicblocks_asm CASCADE;
CREATE TABLE IF NOT EXISTS basicblocks_asm (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Basic block identification
    function_name TEXT NOT NULL,
    basicblock_id TEXT NOT NULL,
    
    -- Tracing metadata
    has_tracing_call BOOLEAN NOT NULL,
    
    -- Instruction metrics
    number_of_instructions INTEGER NOT NULL CHECK (number_of_instructions >= 0),
    
    -- Raw instruction data (ASM instructions)
    instructions TEXT NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint on function + block combination
    CONSTRAINT basicblocks_asm_unique_function_block UNIQUE (function_name, basicblock_id)
);

-- Create indices for better query performance
CREATE INDEX IF NOT EXISTS idx_basicblocks_asm_function_name 
    ON basicblocks_asm(function_name);

CREATE INDEX IF NOT EXISTS idx_basicblocks_asm_has_tracing 
    ON basicblocks_asm(has_tracing_call);

CREATE INDEX IF NOT EXISTS idx_basicblocks_asm_num_instructions 
    ON basicblocks_asm(number_of_instructions);

CREATE INDEX IF NOT EXISTS idx_basicblocks_asm_function_bb 
    ON basicblocks_asm(function_name, basicblock_id);

-- Create a composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_basicblocks_asm_tracing_instructions 
    ON basicblocks_asm(has_tracing_call, number_of_instructions);

-- Add table comment
COMMENT ON TABLE basicblocks_asm IS 
    'Stores LLVM ASM basic block information with tracing metadata for analysis';

COMMENT ON COLUMN basicblocks_asm.function_name IS 
    'Name of the function containing this basic block';

COMMENT ON COLUMN basicblocks_asm.basicblock_id IS 
    'Identifier for the basic block (e.g., .LBB0_1)';

COMMENT ON COLUMN basicblocks_asm.has_tracing_call IS 
    'Whether this block contains __yk_trace_basicblock call';

COMMENT ON COLUMN basicblocks_asm.number_of_instructions IS 
    'Number of real ASM instructions in the block';

COMMENT ON COLUMN basicblocks_asm.instructions IS 
    'Raw ASM instruction text, semicolon-separated';

-- Display table structure
\d basicblocks_asm

-- Display ASM table info
SELECT 
    schemaname AS schema,
    tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE tablename = 'basicblocks_asm';

-- Display ASM index info
SELECT
    indexname AS index_name,
    indexdef AS definition,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_indexes
WHERE tablename = 'basicblocks_asm'
ORDER BY indexname;

\echo ''
\echo '===================================================================='
\echo 'Tables created successfully!'
\echo '===================================================================='
\echo ''
\echo 'Created tables:'
\echo '  • basicblocks     - For LLVM IR/MIR data'
\echo '  • basicblocks_asm - For LLVM ASM data'
\echo ''
\echo 'Next steps:'
\echo '  1. Upload IR/MIR data: ./upload_to_db.sh "$DB_CONN_STR" ir_data.csv basicblocks'
\echo '  2. Upload ASM data:    ./upload_asm_blocks.sh "$DB_CONN_STR" asm_data.csv'
\echo ''


