-- Summary Statistics for MIR Basic Blocks
-- Calculates overall metrics for all blocks, traced blocks, and untraced blocks
--
-- Usage:
--   psql "$DB_CONN_STR" -f query_summary_statistics.sql

WITH stats AS (
  SELECT
    'All blocks' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS mean_instr_per_bb,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY number_of_instructions)::numeric, 2) AS median_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks_mir
  
  UNION ALL

  SELECT
    'Blocks with tracing calls' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS mean_instr_per_bb,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY number_of_instructions)::numeric, 2) AS median_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks_mir
  WHERE has_tracing_call = true
  
  UNION ALL

  SELECT
    'Blocks with tracing calls (net)' AS category,
    ROUND(AVG(number_of_instructions - 3)::numeric, 2) AS mean_instr_per_bb,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY number_of_instructions - 3)::numeric, 2) AS median_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions - 3) AS total_instr
  FROM basicblocks_mir
  WHERE has_tracing_call = true
  
  UNION ALL
  
  SELECT
    'Blocks without tracing calls' AS category,
    ROUND(AVG(number_of_instructions)::numeric, 2) AS mean_instr_per_bb,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY number_of_instructions)::numeric, 2) AS median_instr_per_bb,
    COUNT(*) AS total_bbs,
    SUM(number_of_instructions) AS total_instr
  FROM basicblocks_mir
  WHERE has_tracing_call = false
)
SELECT 
  category AS "Category",
  mean_instr_per_bb AS "Mean Instr/BB",
  median_instr_per_bb AS "Median Instr/BB",
  TO_CHAR(total_bbs, 'FM999,999,999') AS "Total BBs",
  TO_CHAR(total_instr, 'FM999,999,999') AS "Total Instr"
FROM stats
ORDER BY 
  CASE category
    WHEN 'All blocks' THEN 1
    WHEN 'Blocks with tracing calls' THEN 2
    WHEN 'Blocks with tracing calls (net)' THEN 3
    WHEN 'Blocks without tracing calls' THEN 4
  END;

