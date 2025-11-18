-- Block Size Distribution Analysis for MIR Basic Blocks
-- Categorises basic blocks by instruction count and tracing status
--
-- Usage:
--   psql "$DB_CONN_STR" -f query_block_size_distribution.sql

WITH size_categories AS (
  SELECT 
    function_name,
    basicblock_id,
    has_tracing_call,
    number_of_instructions,
    CASE 
      WHEN number_of_instructions BETWEEN 1 AND 3 THEN '1-3'
      WHEN number_of_instructions BETWEEN 4 AND 6 THEN '4-6'
      WHEN number_of_instructions BETWEEN 7 AND 10 THEN '7-10'
      WHEN number_of_instructions BETWEEN 11 AND 20 THEN '11-20'
      WHEN number_of_instructions >= 21 THEN '21+'
      ELSE 'unknown'
    END AS size_category
  FROM basicblocks_mir
),
traced_blocks AS (
  SELECT 
    size_category,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
  FROM size_categories
  WHERE has_tracing_call = true
  GROUP BY size_category
),
traced_net AS (
  SELECT 
    CASE 
      WHEN number_of_instructions - 3 BETWEEN 1 AND 3 THEN '1-3'
      WHEN number_of_instructions - 3 BETWEEN 4 AND 6 THEN '4-6'
      WHEN number_of_instructions - 3 BETWEEN 7 AND 10 THEN '7-10'
      WHEN number_of_instructions - 3 BETWEEN 11 AND 20 THEN '11-20'
      WHEN number_of_instructions - 3 >= 21 THEN '21+'
      ELSE 'unknown'
    END AS size_category,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM size_categories WHERE has_tracing_call = true), 1) AS percentage
  FROM size_categories
  WHERE has_tracing_call = true
  GROUP BY
    CASE 
      WHEN number_of_instructions - 3 BETWEEN 1 AND 3 THEN '1-3'
      WHEN number_of_instructions - 3 BETWEEN 4 AND 6 THEN '4-6'
      WHEN number_of_instructions - 3 BETWEEN 7 AND 10 THEN '7-10'
      WHEN number_of_instructions - 3 BETWEEN 11 AND 20 THEN '11-20'
      WHEN number_of_instructions - 3 >= 21 THEN '21+'
      ELSE 'unknown'
    END
),
untraced_blocks AS (
  SELECT 
    size_category,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS percentage
  FROM size_categories
  WHERE has_tracing_call = false
  GROUP BY size_category
)
SELECT 
  COALESCE(t.size_category, tn.size_category, u.size_category) AS "Block Size (instructions)",
  COALESCE(t.count, 0) AS "Traced Count",
  COALESCE(t.percentage, 0.0) || '%' AS "Traced %",
  COALESCE(tn.count, 0) AS "Traced Net Count",
  COALESCE(tn.percentage, 0.0) || '%' AS "Traced Net %",
  COALESCE(u.count, 0) AS "Untraced Count",
  COALESCE(u.percentage, 0.0) || '%' AS "Untraced %"
FROM traced_blocks t
FULL OUTER JOIN traced_net tn USING (size_category)
FULL OUTER JOIN untraced_blocks u USING (size_category)
ORDER BY 
  CASE COALESCE(t.size_category, tn.size_category, u.size_category)
    WHEN '1-3' THEN 1
    WHEN '4-6' THEN 2
    WHEN '7-10' THEN 3
    WHEN '11-20' THEN 4
    WHEN '21+' THEN 5
    ELSE 6
  END;

-- Totals and averages
SELECT 
  'TOTALS' AS "Metric",
  (SELECT COUNT(*) FROM basicblocks_mir WHERE has_tracing_call = true) AS "Traced Total",
  (SELECT COUNT(*) FROM basicblocks_mir WHERE has_tracing_call = true) AS "Traced Net Total",
  (SELECT COUNT(*) FROM basicblocks_mir WHERE has_tracing_call = false) AS "Untraced Total";

SELECT 
  'AVERAGE' AS "Metric",
  ROUND((SELECT AVG(number_of_instructions) FROM basicblocks_mir WHERE has_tracing_call = true)::numeric, 2) || ' instructions' AS "Traced Avg",
  ROUND((SELECT AVG(number_of_instructions - 3) FROM basicblocks_mir WHERE has_tracing_call = true)::numeric, 2) || ' instructions' AS "Traced Net Avg",
  ROUND((SELECT AVG(number_of_instructions) FROM basicblocks_mir WHERE has_tracing_call = false)::numeric, 2) || ' instructions' AS "Untraced Avg";

