#!/usr/bin/env python3
"""Analyze function tracing status from CSV data.

This script analyzes which functions have tracing calls and categorizes them
into optimized clones, outlined functions, and traced functions.
"""

import csv
import sys
from pathlib import Path


def analyze_tracing_status(csv_file: Path) -> None:
    """Analyze function tracing status from CSV file."""
    
    # Categories
    opt_clones = []
    outlined_functions = []
    traced_functions = []
    
    # Read CSV
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            func_name = row['function_name']
            has_tracing = row['has_tracing_calls'].lower() == 'true'
            reason = row.get('reason_for_no_tracing', '')
            
            if has_tracing:
                traced_functions.append(func_name)
            elif func_name.startswith('__yk_opt_'):
                opt_clones.append(func_name)
            elif 'Outlined function' in reason:
                outlined_functions.append(func_name)
            else:
                # Other non-traced functions
                outlined_functions.append(func_name)
    
    # Calculate totals
    total_functions = len(opt_clones) + len(outlined_functions) + len(traced_functions)
    non_traced = len(opt_clones) + len(outlined_functions)
    
    # Print analysis
    print("=" * 70)
    print("Function Tracing Status Analysis")
    print("=" * 70)
    print()
    
    print(f"Total Functions: {total_functions}")
    print()
    
    print("Breakdown by Category:")
    print("-" * 70)
    print()
    
    print(f"1. __yk_opt_ Clones (Optimised, no tracing):")
    print(f"   Count: {len(opt_clones)} ({len(opt_clones)/total_functions*100:.1f}%)")
    print(f"   Reason: Optimised copies with tracing instrumentation removed")
    print()
    
    print(f"2. Outlined Functions (Never traced):")
    print(f"   Count: {len(outlined_functions)} ({len(outlined_functions)/total_functions*100:.1f}%)")
    print(f"   Reason: Cold/unimportant code paths without control points")
    print()
    
    print(f"3. Functions WITH Tracing Calls:")
    print(f"   Count: {len(traced_functions)} ({len(traced_functions)/total_functions*100:.1f}%)")
    print(f"   Reason: Hot functions selected for instrumentation")
    print()
    
    # Show traced functions
    print("   Traced functions:")
    for func in sorted(traced_functions):
        print(f"     - {func}")
    print()
    
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print(f"Non-traced functions: {non_traced} ({non_traced/total_functions*100:.1f}%)")
    print(f"Traced functions:     {len(traced_functions)} ({len(traced_functions)/total_functions*100:.1f}%)")
    print()
    
    ratio = non_traced / len(traced_functions) if traced_functions else 0
    print(f"Non-traced : Traced ratio = {ratio:.1f} : 1")
    print()
    
    print("Key Insight:")
    print(f"Only {len(traced_functions)} hot functions ({len(traced_functions)/total_functions*100:.1f}%) get traced.")
    print(f"Each traced function creates a __yk_opt_ clone, resulting in {len(opt_clones)} clones.")
    print(f"The remaining {len(outlined_functions)} functions were never selected for tracing.")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        csv_file = Path(sys.argv[1])
    else:
        csv_file = Path(__file__).parent / "function_tracing_status.csv"

    if not csv_file.exists():
        print(f"Error: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)
    
    analyze_tracing_status(csv_file)


if __name__ == "__main__":
    main()

