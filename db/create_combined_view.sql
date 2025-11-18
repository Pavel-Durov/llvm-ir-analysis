-- Create a view combining MIR (basicblocks_mir) and ASM (basicblocks_asm) data
-- Joined on function_name and basicblock_id
-- Excludes functions starting with __yk_opt

-- Drop view if it already exists
DROP VIEW IF EXISTS basicblocks_combined CASCADE;

-- Create the combined view
CREATE VIEW basicblocks_combined AS
SELECT
    -- Common identifiers
    COALESCE(mir.function_name, asm.function_name) AS function_name,
    COALESCE(mir.basicblock_id, asm.basicblock_id) AS basicblock_id,

    -- MIR data
    mir.number_of_instructions AS mir_instructions_count,
    mir.instructions AS mir_instructions,
    mir.id AS mir_id,

    -- ASM data
    asm.number_of_instructions AS asm_instruction_count,
    asm.instructions AS asm_instructions,
    asm.id AS asm_idm,
    ABS(mir.number_of_instructions - asm.number_of_instructions) AS instruction_diff

FROM basicblocks_mir as mir
JOIN basicblocks_asm asm
    ON mir.function_name = asm.function_name
    AND mir.basicblock_id_num = asm.basicblock_id_num

-- Exclude __yk_opt functions
WHERE COALESCE(mir.function_name, asm.function_name) NOT LIKE '__yk_opt%';
-- AND mir_instructions is not NULL and asm_instructions is not NULL;

-- Display summary statistics
SELECT instruction_diff, *
 FROM basicblocks_combined
 ORDER BY instruction_diff DESC
 LIMIT 100