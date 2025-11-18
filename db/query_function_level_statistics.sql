-- Function-Level Statistics for MIR Basic Blocks
-- Analyses instruction and basic-block counts per function, identifying hot functions
-- and tracing instrumentation density
--
-- Usage:
--   psql "$DB_CONN_STR" -f query_function_level_statistics.sql

-- Overview: Functions with most basic blocks
SELECT 
  function_name AS "Function Name",
  COUNT(*) AS "Total BBs",
  SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) AS "Traced BBs",
  ROUND(100.0 * SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) / COUNT(*), 2) AS "Tracing %",
  SUM(number_of_instructions) AS "Total Instructions",
  ROUND(AVG(number_of_instructions)::numeric, 2) AS "Avg Instr/BB"
FROM basicblocks_mir
GROUP BY function_name
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 20;

-- Functions with highest tracing instrumentation density
SELECT 
  function_name AS "Function Name",
  COUNT(*) AS "Total BBs",
  SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) AS "Traced BBs",
  ROUND(100.0 * SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) / COUNT(*), 2) AS "Tracing %",
  SUM(number_of_instructions) AS "Total Instructions"
FROM basicblocks_mir
GROUP BY function_name
HAVING SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) > 0
ORDER BY "Tracing %" DESC
LIMIT 20;

-- Functions with most instructions (potential optimization targets)
SELECT 
  function_name AS "Function Name",
  COUNT(*) AS "Total BBs",
  SUM(number_of_instructions) AS "Total Instructions",
  ROUND(AVG(number_of_instructions)::numeric, 2) AS "Avg Instr/BB",
  SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) AS "Traced BBs"
FROM basicblocks_mir
GROUP BY function_name
ORDER BY SUM(number_of_instructions) DESC
LIMIT 20;

-- Functions with largest basic blocks (average instructions per block)
SELECT 
  function_name AS "Function Name",
  COUNT(*) AS "Total BBs",
  ROUND(AVG(number_of_instructions)::numeric, 2) AS "Avg Instr/BB",
  MIN(number_of_instructions) AS "Min Instr",
  MAX(number_of_instructions) AS "Max Instr",
  SUM(CASE WHEN has_tracing_call THEN 1 ELSE 0 END) AS "Traced BBs"
FROM basicblocks_mir
GROUP BY function_name
HAVING COUNT(*) >= 5
ORDER BY AVG(number_of_instructions) DESC
LIMIT 20;

