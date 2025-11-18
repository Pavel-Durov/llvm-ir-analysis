#!/usr/bin/env python3
"""
Validate the basicblocks data in PostgreSQL database.

This script checks:
1. Data integrity (nulls, empty fields)
2. Function distribution (original vs __yk_opt)
3. Tracing call validation (__yk_opt functions should have no tracing calls)
4. Matching between original and optimized functions
5. Statistics and summary

Usage:
    python3 validate_data.py <postgres_connection_string>

Example:
    python3 validate_data.py 'postgresql://user:password@host/db'
"""

import sys
import psycopg2
from psycopg2.extras import RealDictCursor


def print_header(title):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def print_subheader(title):
    """Print a formatted subsection header."""
    print(f"\n{title}")
    print("-" * len(title))


def run_query(cursor, query, description=None):
    """Execute a query and return results."""
    if description:
        print(f"\n{description}")
    cursor.execute(query)
    return cursor.fetchall()


def validate_database(conn_str):
    """Run all validation checks on the database."""
    
    print_header("PostgreSQL Database Validation")
    print(f"Connection: {conn_str.split('@')[1] if '@' in conn_str else 'localhost'}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # =================================================================
        # 1. BASIC STATISTICS
        # =================================================================
        print_header("1. Basic Statistics")
        
        # Total rows
        result = run_query(cursor, 
            "SELECT COUNT(*) as total FROM basicblocks;",
            "→ Total rows:")
        print(f"  {result[0]['total']:,} rows")
        
        # Function count
        result = run_query(cursor,
            "SELECT COUNT(DISTINCT function_name) as count FROM basicblocks;",
            "\n→ Unique functions:")
        print(f"  {result[0]['count']:,} functions")
        
        # Original vs optimised
        result = run_query(cursor, """
            SELECT 
                COUNT(DISTINCT CASE WHEN function_name LIKE '__yk_opt_%' 
                    THEN function_name END) as opt_functions,
                COUNT(DISTINCT CASE WHEN function_name NOT LIKE '__yk_opt_%' 
                    THEN function_name END) as orig_functions
            FROM basicblocks;
        """, "\n→ Function breakdown:")
        print(f"  Original functions:  {result[0]['orig_functions']:,}")
        print(f"  Optimised functions: {result[0]['opt_functions']:,}")
        
        # =================================================================
        # 2. DATA INTEGRITY CHECKS
        # =================================================================
        print_header("2. Data Integrity Checks")
        
        # Check for NULL values
        result = run_query(cursor, """
            SELECT 
                COUNT(*) FILTER (WHERE function_name IS NULL) as null_function,
                COUNT(*) FILTER (WHERE basicblock_id IS NULL) as null_bb_id,
                COUNT(*) FILTER (WHERE has_tracing_call IS NULL) as null_tracing,
                COUNT(*) FILTER (WHERE number_of_instructions IS NULL) as null_inst_count,
                COUNT(*) FILTER (WHERE instructions IS NULL) as null_instructions
            FROM basicblocks;
        """, "→ NULL value check:")
        
        issues = []
        for col, val in result[0].items():
            if val > 0:
                issues.append(f"  ✗ {col}: {val} NULL values")
        
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("  ✓ No NULL values found")
        
        # Check for empty strings
        result = run_query(cursor, """
            SELECT 
                COUNT(*) FILTER (WHERE function_name = '') as empty_function,
                COUNT(*) FILTER (WHERE basicblock_id = '') as empty_bb_id,
                COUNT(*) FILTER (WHERE instructions = '') as empty_instructions
            FROM basicblocks;
        """, "\n→ Empty string check:")
        
        issues = []
        for col, val in result[0].items():
            if val > 0:
                issues.append(f"  ✗ {col}: {val} empty strings")
        
        if issues:
            for issue in issues:
                print(issue)
        else:
            print("  ✓ No empty strings found")
        
        # =================================================================
        # 3. TRACING CALL VALIDATION
        # =================================================================
        print_header("3. Tracing Call Validation")
        
        # Overall tracing statistics
        result = run_query(cursor, """
            SELECT 
                COUNT(*) FILTER (WHERE has_tracing_call = true) as with_tracing,
                COUNT(*) FILTER (WHERE has_tracing_call = false) as without_tracing
            FROM basicblocks;
        """, "→ Overall tracing statistics:")
        print(f"  With tracing call:    {result[0]['with_tracing']:,} blocks")
        print(f"  Without tracing call: {result[0]['without_tracing']:,} blocks")
        
        # Check __yk_opt functions (should have NO tracing calls)
        result = run_query(cursor, """
            SELECT COUNT(*) as count
            FROM basicblocks
            WHERE function_name LIKE '__yk_opt_%'
                AND has_tracing_call = true;
        """, "\n→ Checking __yk_opt functions for tracing calls:")
        
        if result[0]['count'] > 0:
            print(f"  ✗ VALIDATION FAILED: {result[0]['count']} __yk_opt blocks have tracing calls!")
            print("    (Expected: 0, as optimised functions should not have tracing)")
        else:
            print("  ✓ PASSED: No __yk_opt functions have tracing calls")
        
        # Check original functions (should have some tracing calls)
        result = run_query(cursor, """
            SELECT 
                COUNT(DISTINCT function_name) as total_orig_funcs,
                COUNT(DISTINCT CASE WHEN has_tracing_call = true 
                    THEN function_name END) as funcs_with_tracing
            FROM basicblocks
            WHERE function_name NOT LIKE '__yk_opt_%';
        """, "\n→ Original functions with tracing calls:")
        print(f"  Total original functions:          {result[0]['total_orig_funcs']:,}")
        print(f"  Original functions with tracing:   {result[0]['funcs_with_tracing']:,}")
        
        # =================================================================
        # 4. FUNCTION MATCHING VALIDATION
        # =================================================================
        print_header("4. Function Matching (Original ↔ Optimised)")
        
        # Find original functions with matching optimised versions
        result = run_query(cursor, """
            SELECT 
                COUNT(DISTINCT orig.function_name) as orig_with_opt
            FROM basicblocks orig
            WHERE orig.function_name NOT LIKE '__yk_opt_%'
                AND EXISTS (
                    SELECT 1 FROM basicblocks opt
                    WHERE opt.function_name = '__yk_opt_' || orig.function_name
                );
        """, "→ Original functions with optimised versions:")
        orig_with_opt = result[0]['orig_with_opt']
        print(f"  {orig_with_opt:,} functions")
        
        # Find optimised functions with matching original versions
        result = run_query(cursor, """
            SELECT 
                COUNT(DISTINCT opt.function_name) as opt_with_orig
            FROM basicblocks opt
            WHERE opt.function_name LIKE '__yk_opt_%'
                AND EXISTS (
                    SELECT 1 FROM basicblocks orig
                    WHERE orig.function_name = SUBSTRING(opt.function_name FROM 10)
                );
        """, "\n→ Optimised functions with original versions:")
        opt_with_orig = result[0]['opt_with_orig']
        print(f"  {opt_with_orig:,} functions")
        
        # Find orphaned optimised functions (no original)
        result = run_query(cursor, """
            SELECT 
                opt.function_name
            FROM basicblocks opt
            WHERE opt.function_name LIKE '__yk_opt_%'
                AND NOT EXISTS (
                    SELECT 1 FROM basicblocks orig
                    WHERE orig.function_name = SUBSTRING(opt.function_name FROM 10)
                )
            GROUP BY opt.function_name
            ORDER BY opt.function_name
            LIMIT 10;
        """, "\n→ Orphaned optimised functions (no original):")
        
        if result:
            print(f"  ⚠ Found {len(result)} orphaned optimised functions (showing first 10):")
            for row in result:
                print(f"    - {row['function_name']}")
        else:
            print("  ✓ All optimised functions have matching originals")
        
        # =================================================================
        # 5. INSTRUCTION COUNT STATISTICS
        # =================================================================
        print_header("5. Instruction Count Statistics")
        
        # Overall statistics
        result = run_query(cursor, """
            SELECT 
                MIN(number_of_instructions) as min_inst,
                MAX(number_of_instructions) as max_inst,
                ROUND(AVG(number_of_instructions), 2) as avg_inst,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY number_of_instructions) as median_inst
            FROM basicblocks;
        """, "→ Overall instruction counts:")
        print(f"  Min:    {result[0]['min_inst']}")
        print(f"  Max:    {result[0]['max_inst']}")
        print(f"  Mean:   {result[0]['avg_inst']}")
        print(f"  Median: {result[0]['median_inst']}")
        
        # Compare original vs optimised
        result = run_query(cursor, """
            SELECT 
                ROUND(AVG(CASE WHEN function_name NOT LIKE '__yk_opt_%' 
                    THEN number_of_instructions END), 2) as avg_orig,
                ROUND(AVG(CASE WHEN function_name LIKE '__yk_opt_%' 
                    THEN number_of_instructions END), 2) as avg_opt
            FROM basicblocks;
        """, "\n→ Average instructions (Original vs Optimised):")
        print(f"  Original functions:  {result[0]['avg_orig']} instructions/block")
        print(f"  Optimised functions: {result[0]['avg_opt']} instructions/block")
        
        if result[0]['avg_orig'] and result[0]['avg_opt']:
            reduction = ((result[0]['avg_orig'] - result[0]['avg_opt']) / 
                        result[0]['avg_orig'] * 100)
            print(f"  Average reduction:   {reduction:.2f}%")
        
        # =================================================================
        # 6. MATCHING BLOCK STATISTICS
        # =================================================================
        print_header("6. Matching Block Statistics")
        
        result = run_query(cursor, """
            SELECT 
                COUNT(*) as matched_blocks,
                ROUND(AVG(orig.number_of_instructions), 2) as avg_orig_inst,
                ROUND(AVG(opt.number_of_instructions), 2) as avg_opt_inst,
                ROUND(AVG(orig.number_of_instructions - opt.number_of_instructions), 2) as avg_reduction
            FROM basicblocks orig
            INNER JOIN basicblocks opt
                ON orig.basicblock_id = opt.basicblock_id
                AND opt.function_name = '__yk_opt_' || orig.function_name
            WHERE orig.function_name NOT LIKE '__yk_opt_%';
        """, "→ Blocks with matching original and optimised versions:")
        
        if result[0]['matched_blocks']:
            print(f"  Matched blocks:      {result[0]['matched_blocks']:,}")
            print(f"  Avg original insts:  {result[0]['avg_orig_inst']}")
            print(f"  Avg optimised insts: {result[0]['avg_opt_inst']}")
            print(f"  Avg reduction:       {result[0]['avg_reduction']} instructions")
        else:
            print("  ⚠ No matching blocks found")
        
        # Top 5 functions with most blocks
        result = run_query(cursor, """
            SELECT 
                function_name,
                COUNT(*) as block_count,
                SUM(number_of_instructions) as total_instructions
            FROM basicblocks
            WHERE function_name NOT LIKE '__yk_opt_%'
            GROUP BY function_name
            ORDER BY block_count DESC
            LIMIT 5;
        """, "\n→ Top 5 functions by block count (original only):")
        
        for i, row in enumerate(result, 1):
            print(f"  {i}. {row['function_name']}: "
                  f"{row['block_count']} blocks, "
                  f"{row['total_instructions']} total instructions")
        
        # =================================================================
        # 7. VALIDATION SUMMARY
        # =================================================================
        print_header("Validation Summary")
        
        # Count issues
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE function_name IS NULL OR basicblock_id IS NULL) as critical_nulls,
                COUNT(*) FILTER (WHERE function_name LIKE '__yk_opt_%' AND has_tracing_call = true) as opt_with_tracing
            FROM basicblocks;
        """)
        issues = cursor.fetchone()
        
        total_issues = sum(issues.values())
        
        if total_issues == 0:
            print("\n✓ ALL VALIDATION CHECKS PASSED")
            print("\nThe database contains valid data with:")
            print(f"  • {orig_with_opt:,} matched function pairs (original ↔ optimised)")
            print("  • No critical data integrity issues")
            print("  • Correct tracing call distribution")
        else:
            print("\n✗ VALIDATION ISSUES DETECTED")
            if issues['critical_nulls'] > 0:
                print(f"  • {issues['critical_nulls']} rows with NULL in critical fields")
            if issues['opt_with_tracing'] > 0:
                print(f"  • {issues['opt_with_tracing']} __yk_opt blocks incorrectly have tracing calls")
        
        print()
        
        cursor.close()
        conn.close()
        
        return total_issues == 0
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_data.py <postgres_connection_string>")
        print("")
        print("Example:")
        print("  python3 validate_data.py 'postgresql://user:password@host/db'")
        print("")
        sys.exit(1)
    
    conn_str = sys.argv[1]
    success = validate_database(conn_str)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

