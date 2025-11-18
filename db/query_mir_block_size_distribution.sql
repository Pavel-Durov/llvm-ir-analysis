-- Block Size Distribution for MIR Basic Blocks
-- Produces statistics for traced, traced (net), and untraced blocks
-- Traced (net) subtracts 3-instruction tracing overhead

WITH block_stats AS (
    SELECT 
        has_tracing_call,
        number_of_instructions,
        -- Net instructions after removing 3-instruction tracing overhead
        CASE 
            WHEN has_tracing_call THEN GREATEST(number_of_instructions - 3, 1)
            ELSE number_of_instructions
        END AS net_instructions
    FROM basicblocks_mir
),

-- Categorise traced blocks by original size
traced_distribution AS (
    SELECT 
        CASE 
            WHEN number_of_instructions BETWEEN 1 AND 3 THEN '1--3'
            WHEN number_of_instructions BETWEEN 4 AND 6 THEN '4--6'
            WHEN number_of_instructions BETWEEN 7 AND 10 THEN '7--10'
            WHEN number_of_instructions BETWEEN 11 AND 20 THEN '11--20'
            WHEN number_of_instructions >= 21 THEN '21+'
        END AS size_range,
        COUNT(*) AS count
    FROM block_stats
    WHERE has_tracing_call = true
    GROUP BY size_range
),

-- Categorise traced blocks by net size (after overhead removal)
traced_net_distribution AS (
    SELECT 
        CASE 
            WHEN net_instructions BETWEEN 1 AND 3 THEN '1--3'
            WHEN net_instructions BETWEEN 4 AND 6 THEN '4--6'
            WHEN net_instructions BETWEEN 7 AND 10 THEN '7--10'
            WHEN net_instructions BETWEEN 11 AND 20 THEN '11--20'
            WHEN net_instructions >= 21 THEN '21+'
        END AS size_range,
        COUNT(*) AS count
    FROM block_stats
    WHERE has_tracing_call = true
    GROUP BY size_range
),

-- Categorise untraced blocks by size
untraced_distribution AS (
    SELECT 
        CASE 
            WHEN number_of_instructions BETWEEN 1 AND 3 THEN '1--3'
            WHEN number_of_instructions BETWEEN 4 AND 6 THEN '4--6'
            WHEN number_of_instructions BETWEEN 7 AND 10 THEN '7--10'
            WHEN number_of_instructions BETWEEN 11 AND 20 THEN '11--20'
            WHEN number_of_instructions >= 21 THEN '21+'
        END AS size_range,
        COUNT(*) AS count
    FROM block_stats
    WHERE has_tracing_call = false
    GROUP BY size_range
),

-- Calculate totals
totals AS (
    SELECT 
        COUNT(*) FILTER (WHERE has_tracing_call = true) AS total_traced,
        COUNT(*) FILTER (WHERE has_tracing_call = false) AS total_untraced,
        ROUND(AVG(number_of_instructions) FILTER (WHERE has_tracing_call = true), 2) AS avg_traced,
        ROUND(AVG(net_instructions) FILTER (WHERE has_tracing_call = true), 2) AS avg_traced_net,
        ROUND(AVG(number_of_instructions) FILTER (WHERE has_tracing_call = false), 2) AS avg_untraced
    FROM block_stats
),

-- All possible size ranges
size_ranges AS (
    SELECT '1--3' AS size_range, 1 AS sort_order
    UNION ALL SELECT '4--6', 2
    UNION ALL SELECT '7--10', 3
    UNION ALL SELECT '11--20', 4
    UNION ALL SELECT '21+', 5
)

-- Final output
SELECT 
    sr.size_range AS "Block Size",
    COALESCE(td.count, 0) AS "Traced Count",
    ROUND(100.0 * COALESCE(td.count, 0) / NULLIF(t.total_traced, 0), 1) AS "Traced %",
    COALESCE(tn.count, 0) AS "Traced (net) Count",
    ROUND(100.0 * COALESCE(tn.count, 0) / NULLIF(t.total_traced, 0), 1) AS "Traced (net) %",
    COALESCE(ud.count, 0) AS "Untraced Count",
    ROUND(100.0 * COALESCE(ud.count, 0) / NULLIF(t.total_untraced, 0), 1) AS "Untraced %"
FROM size_ranges sr
CROSS JOIN totals t
LEFT JOIN traced_distribution td ON sr.size_range = td.size_range
LEFT JOIN traced_net_distribution tn ON sr.size_range = tn.size_range
LEFT JOIN untraced_distribution ud ON sr.size_range = ud.size_range
ORDER BY sr.sort_order;

-- Summary statistics
SELECT 
    'TOTAL' AS "Metric",
    total_traced AS "Traced",
    total_traced AS "Traced (net)",
    total_untraced AS "Untraced"
FROM totals

UNION ALL

SELECT 
    'AVERAGE (instructions)',
    avg_traced,
    avg_traced_net,
    avg_untraced
FROM totals;

