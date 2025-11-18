-- Join MIR and ASM basic blocks
-- Matches blocks across representations by function name and normalised block ID
SELECT *
FROM basicblocks_mir as bb_mir
JOIN basicblocks_asm as bb_asm ON 
    bb_mir.function_name = bb_asm.function_name AND 
    REPLACE(REPLACE(LOWER(bb_mir.basicblock_id), 'bb#', 'bb.'), '_', '.') = 
    REPLACE(REPLACE(LOWER(bb_asm.basicblock_id), 'bb#', 'bb.'), '_', '.')
