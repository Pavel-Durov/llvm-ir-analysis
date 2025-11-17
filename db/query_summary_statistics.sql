-- Summary Statistics for Basic Blocks
-- Calculates overall metrics for all blocks, traced blocks, and untraced blocks
--
-- Usage:
--   psql "$DB_CONN_STR" -f query_summary_statistics.sql

WITH stats AS (
  SELECT
    'All blocks' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS avg_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks
  
  UNION ALL
  
  SELECT
    'Blocks with tracing calls' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS avg_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks
  WHERE has_tracing_call = true
  
  UNION ALL
  
  SELECT
    'Blocks without tracing calls' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS avg_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks
  WHERE has_tracing_call = false
)
SELECT 
  category AS "Category",
  avg_instr_per_bb AS "Instr/BB",
  TO_CHAR(total_bbs, 'FM999,999,999') AS "Total BBs",
  TO_CHAR(total_instr, 'FM999,999,999') AS "Total Instr"
FROM stats
ORDER BY 
  CASE category
    WHEN 'All blocks' THEN 1
    WHEN 'Blocks with tracing calls' THEN 2
    WHEN 'Blocks without tracing calls' THEN 3
  END;

