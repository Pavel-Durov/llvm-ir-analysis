SELECT *
FROM basicblocks as bb
JOIN basicblocks_asm as bb_asm ON 
    bb.function_name = bb_asm.function_name AND 
    REPLACE(REPLACE(LOWER(bb.basicblock_id), 'bb#', 'bb.'), '_', '.') = 
    REPLACE(REPLACE(LOWER(bb_asm.basicblock_id), 'bb#', 'bb.'), '_', '.')
