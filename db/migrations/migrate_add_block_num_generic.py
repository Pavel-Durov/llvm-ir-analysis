#!/usr/bin/env python3
"""
Database migration: Add basicblock_id_num column to any table

This script adds a new column 'basicblock_id_num' to a specified table
and populates it by parsing the integer from 'basicblock_id' (e.g., "BB#23" -> 23).

Usage:
    python3 migrate_add_block_num_generic.py <postgres_connection_string> <table_name>

Example:
    python3 migrate_add_block_num_generic.py 'postgresql://user:password@host/db' basicblocks
    python3 migrate_add_block_num_generic.py 'postgresql://user:password@host/db' basicblocks_asm
"""

import sys
import re
import psycopg2
from psycopg2.extras import RealDictCursor


def extract_block_number(basicblock_id):
    """
    Extract the numeric portion from a basicblock_id string.
    
    Examples:
        "BB#0" -> 0
        "BB#23" -> 23
        "bb123" -> 123
        "block_45" -> 45
        "entry" -> None
    """
    # Try various patterns
    patterns = [
        r'BB#(\d+)',           # BB#23
        r'bb#?(\d+)',          # bb23 or bb#23
        r'block[_#]?(\d+)',    # block_23 or block#23
        r'(\d+)',              # Any number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, basicblock_id, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return None


def migrate_database(conn_str, table_name, dry_run=False):
    """Run the migration on the database."""
    
    print("="*80)
    print(f"  Database Migration: Add basicblock_id_num Column to '{table_name}'")
    print("="*80)
    print(f"Connection: {conn_str.split('@')[1] if '@' in conn_str else 'localhost'}")
    print(f"Table: {table_name}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    try:
        # Connect to database
        conn = psycopg2.connect(conn_str)
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # =================================================================
        # Step 0: Check if table exists
        # =================================================================
        print("→ Step 0: Checking if table exists...")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_name = %s;
        """, (table_name,))
        result = cursor.fetchone()
        
        if result['count'] == 0:
            print(f"  ✗ Table '{table_name}' does not exist!")
            cursor.close()
            conn.close()
            return False
        
        print(f"  ✓ Table '{table_name}' exists")
        
        # Check if basicblock_id column exists
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = 'basicblock_id';
        """, (table_name,))
        result = cursor.fetchone()
        
        if result['count'] == 0:
            print(f"  ✗ Table '{table_name}' does not have a 'basicblock_id' column!")
            cursor.close()
            conn.close()
            return False
        
        print("  ✓ Column 'basicblock_id' exists")
        
        # =================================================================
        # Step 1: Check if column already exists
        # =================================================================
        print("\n→ Step 1: Checking if 'basicblock_id_num' column already exists...")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = 'basicblock_id_num';
        """, (table_name,))
        result = cursor.fetchone()
        
        if result['count'] > 0:
            print("  ⚠ Column 'basicblock_id_num' already exists!")
            print("  Use --force to drop and recreate it.")
            cursor.close()
            conn.close()
            return False
        
        print("  ✓ Column does not exist, proceeding with migration")
        
        # =================================================================
        # Step 2: Add the new column
        # =================================================================
        print("\n→ Step 2: Adding 'basicblock_id_num' column...")
        cursor.execute(f"""
            ALTER TABLE {table_name}
            ADD COLUMN basicblock_id_num INTEGER;
        """)
        print("  ✓ Column added")
        
        # =================================================================
        # Step 3: Sample the data to understand formats
        # =================================================================
        print("\n→ Step 3: Sampling basicblock_id formats...")
        cursor.execute(f"""
            SELECT DISTINCT basicblock_id
            FROM {table_name}
            ORDER BY basicblock_id
            LIMIT 20;
        """)
        samples = cursor.fetchall()
        
        print(f"  Found {len(samples)} unique formats (showing first 20):")
        for sample in samples[:10]:
            bb_id = sample['basicblock_id']
            num = extract_block_number(bb_id)
            print(f"    '{bb_id}' -> {num}")
        
        # =================================================================
        # Step 4: Parse and populate the column
        # =================================================================
        print("\n→ Step 4: Parsing and populating basicblock_id_num...")
        
        # Get all unique basicblock_ids
        cursor.execute(f"""
            SELECT DISTINCT basicblock_id
            FROM {table_name};
        """)
        all_ids = cursor.fetchall()
        
        print(f"  Processing {len(all_ids)} unique basicblock_id values...")
        
        # Parse each ID and build update mapping
        successful = 0
        failed = 0
        failed_ids = []
        
        for row in all_ids:
            bb_id = row['basicblock_id']
            num = extract_block_number(bb_id)
            
            if num is not None:
                successful += 1
            else:
                failed += 1
                failed_ids.append(bb_id)
        
        print(f"  Successfully parsed: {successful}")
        print(f"  Failed to parse:     {failed}")
        
        if failed_ids:
            print(f"\n  ⚠ Could not parse the following IDs:")
            for fail_id in failed_ids[:10]:
                print(f"    - '{fail_id}'")
            if len(failed_ids) > 10:
                print(f"    ... and {len(failed_ids) - 10} more")
        
        # Update the database using regex-based SQL update
        print("\n  Updating database...")
        
        # Pattern 1: BB#<num>
        cursor.execute(f"""
            UPDATE {table_name}
            SET basicblock_id_num = CAST(
                substring(basicblock_id FROM '[Bb][Bb]#?(\\d+)') AS INTEGER
            )
            WHERE basicblock_id ~* '[Bb][Bb]#?\\d+';
        """)
        updated = cursor.rowcount
        print(f"  ✓ Updated {updated:,} rows with BB# format")
        
        # Pattern 2: block_<num>
        cursor.execute(f"""
            UPDATE {table_name}
            SET basicblock_id_num = CAST(
                substring(basicblock_id FROM 'block[_#]?(\\d+)') AS INTEGER
            )
            WHERE basicblock_id_num IS NULL
              AND basicblock_id ~* 'block[_#]?\\d+';
        """)
        updated2 = cursor.rowcount
        if updated2 > 0:
            print(f"  ✓ Updated {updated2:,} rows with 'block' format")
        
        # Pattern 3: Any number
        cursor.execute(f"""
            UPDATE {table_name}
            SET basicblock_id_num = CAST(
                substring(basicblock_id FROM '(\\d+)') AS INTEGER
            )
            WHERE basicblock_id_num IS NULL
              AND basicblock_id ~ '\\d+';
        """)
        updated3 = cursor.rowcount
        if updated3 > 0:
            print(f"  ✓ Updated {updated3:,} rows with generic number extraction")
        
        # =================================================================
        # Step 5: Create index for performance
        # =================================================================
        print("\n→ Step 5: Creating index on basicblock_id_num...")
        index_name = f"idx_{table_name}_id_num"
        cursor.execute(f"""
            CREATE INDEX {index_name}
            ON {table_name}(basicblock_id_num);
        """)
        print(f"  ✓ Index '{index_name}' created")
        
        # =================================================================
        # Step 6: Validate the migration
        # =================================================================
        print("\n→ Step 6: Validating migration...")
        
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_rows,
                COUNT(basicblock_id_num) as rows_with_num,
                COUNT(*) - COUNT(basicblock_id_num) as rows_without_num,
                MIN(basicblock_id_num) as min_num,
                MAX(basicblock_id_num) as max_num
            FROM {table_name};
        """)
        stats = cursor.fetchone()
        
        print(f"  Total rows:           {stats['total_rows']:,}")
        print(f"  Rows with number:     {stats['rows_with_num']:,}")
        print(f"  Rows without number:  {stats['rows_without_num']:,}")
        if stats['min_num'] is not None:
            print(f"  Number range:         {stats['min_num']} - {stats['max_num']}")
        
        coverage = (stats['rows_with_num'] / stats['total_rows'] * 100) if stats['total_rows'] > 0 else 0
        print(f"  Coverage:             {coverage:.2f}%")
        
        # Show examples of rows without numbers
        if stats['rows_without_num'] > 0:
            print("\n  Examples of rows without parsed numbers:")
            cursor.execute(f"""
                SELECT function_name, basicblock_id
                FROM {table_name}
                WHERE basicblock_id_num IS NULL
                LIMIT 5;
            """)
            examples = cursor.fetchall()
            for ex in examples:
                print(f"    {ex['function_name']}: '{ex['basicblock_id']}'")
        
        # =================================================================
        # Step 7: Commit or rollback
        # =================================================================
        print("\n→ Step 7: Finalizing migration...")
        
        if dry_run:
            print("  ⚠ DRY RUN: Rolling back changes")
            conn.rollback()
        else:
            print("  ✓ Committing changes...")
            conn.commit()
            print("  ✓ Migration complete!")
        
        # =================================================================
        # Step 8: Show summary
        # =================================================================
        print("\n" + "="*80)
        print("  Migration Summary")
        print("="*80)
        
        if coverage == 100:
            print("\n✓ SUCCESS: All rows have parsed block numbers")
        elif coverage >= 95:
            print(f"\n✓ SUCCESS: {coverage:.2f}% of rows have parsed block numbers")
            print(f"  ({stats['rows_without_num']:,} rows could not be parsed)")
        else:
            print(f"\n⚠ WARNING: Only {coverage:.2f}% of rows have parsed block numbers")
            print(f"  ({stats['rows_without_num']:,} rows could not be parsed)")
            print("\n  You may need to manually handle these rows or update the parsing logic.")
        
        print()
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
            conn.close()
        return False


def force_migrate(conn_str, table_name):
    """Drop the column and run migration again."""
    print("="*80)
    print("  FORCE MODE: Dropping existing column")
    print("="*80)
    print()
    
    try:
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()
        
        print(f"→ Dropping 'basicblock_id_num' column from '{table_name}'...")
        cursor.execute(f"""
            ALTER TABLE {table_name}
            DROP COLUMN IF EXISTS basicblock_id_num;
        """)
        
        # Drop index if exists
        index_name = f"idx_{table_name}_id_num"
        cursor.execute(f"""
            DROP INDEX IF EXISTS {index_name};
        """)
        
        conn.commit()
        print("  ✓ Column dropped")
        print()
        
        cursor.close()
        conn.close()
        
        # Now run normal migration
        return migrate_database(conn_str, table_name)
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 migrate_add_block_num_generic.py <postgres_connection_string> <table_name> [--dry-run] [--force]")
        print("")
        print("Options:")
        print("  --dry-run   Run migration without committing changes")
        print("  --force     Drop existing column and recreate")
        print("")
        print("Examples:")
        print("  python3 migrate_add_block_num_generic.py 'postgresql://user:password@host/db' basicblocks")
        print("  python3 migrate_add_block_num_generic.py 'postgresql://user:password@host/db' basicblocks_asm")
        print("  python3 migrate_add_block_num_generic.py 'postgresql://user:password@host/db' basicblocks_asm --dry-run")
        print("")
        sys.exit(1)
    
    conn_str = sys.argv[1]
    table_name = sys.argv[2]
    dry_run = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    
    if force:
        success = force_migrate(conn_str, table_name)
    else:
        success = migrate_database(conn_str, table_name, dry_run)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

