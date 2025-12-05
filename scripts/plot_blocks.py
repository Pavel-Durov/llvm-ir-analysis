#!/usr/bin/env python3
"""
Plot basic block characteristics from CSV data.

This script reads a CSV file containing basic block information and creates
scatter plots showing the relationship between block numbers and the number of
instructions, with different colours for blocks with and without tracing calls.
Blocks are sorted by size independently within each group (with/without tracing).
Optimised for large datasets using rasterisation.
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_blocks(csv_file: Path, output_file: Path = None):
    """
    Create scatter plots of block numbers vs number of instructions.
    
    Generates three plots:
    1. Combined plot with both colours
    2. Plot with only blocks with tracing calls
    3. Plot with only blocks without tracing calls
    
    Blocks are sorted by instruction count independently within each group.
    Uses rasterisation for better performance with large datasets.

    Args:
        csv_file: Path to the input CSV file
        output_file: Optional path to save the plots (if None, displays interactively)
    """
    # Read the CSV file
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: File '{csv_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"Error: File '{csv_file}' is empty.", file=sys.stderr)
        sys.exit(1)

    # Validate required columns
    required_columns = ['basicblock_id', 'has_tracing_call', 'number_of_instructions']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Missing required columns: {missing_columns}", file=sys.stderr)
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    # Separate data by tracing call presence first
    df_with_tracing = df[df['has_tracing_call'] == True].copy()
    df_without_tracing = df[df['has_tracing_call'] == False].copy()
    
    # Sort each group independently by instruction count and assign block numbers
    df_with_tracing = df_with_tracing.sort_values('number_of_instructions').reset_index(drop=True)
    df_with_tracing['block_number'] = df_with_tracing.index + 1
    
    df_without_tracing = df_without_tracing.sort_values('number_of_instructions').reset_index(drop=True)
    df_without_tracing['block_number'] = df_without_tracing.index + 1

    # Calculate net instructions (subtract tracing overhead)
    if not df_with_tracing.empty:
        df_with_tracing['net_instructions'] = df_with_tracing['number_of_instructions'] - 3
    
    # Print summary statistics
    total_blocks = len(df)
    blocks_with_tracing = len(df_with_tracing)
    blocks_without_tracing = len(df_without_tracing)
    
    print(f"\nSummary Statistics:")
    print(f"  Total blocks: {total_blocks}")
    print(f"  Blocks with tracing call: {blocks_with_tracing} ({100*blocks_with_tracing/total_blocks:.1f}%)")
    print(f"  Blocks without tracing call: {blocks_without_tracing} ({100*blocks_without_tracing/total_blocks:.1f}%)")
    print(f"\n  Instructions per block (with tracing):")
    if not df_with_tracing.empty:
        print(f"    Mean: {df_with_tracing['number_of_instructions'].mean():.2f}")
        print(f"    Median: {df_with_tracing['number_of_instructions'].median():.2f}")
    print(f"\n  Net instructions per block (with tracing, minus 3 overhead):")
    if not df_with_tracing.empty:
        print(f"    Mean: {df_with_tracing['net_instructions'].mean():.2f}")
        print(f"    Median: {df_with_tracing['net_instructions'].median():.2f}")
    print(f"\n  Instructions per block (without tracing):")
    if not df_without_tracing.empty:
        print(f"    Mean: {df_without_tracing['number_of_instructions'].mean():.2f}")
        print(f"    Median: {df_without_tracing['number_of_instructions'].median():.2f}")

    # Determine output file names
    if output_file:
        output_path = Path(output_file)
        stem = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent
        
        combined_file = parent / f"{stem}_combined{suffix}"
        with_tracing_file = parent / f"{stem}_with_tracing{suffix}"
        without_tracing_file = parent / f"{stem}_without_tracing{suffix}"
    else:
        combined_file = None
        with_tracing_file = None
        without_tracing_file = None

    # Plot 1: Combined plot with both colors
    plt.figure(figsize=(12, 8))
    
    # Plot blocks without tracing calls (using scatter for better performance with large datasets)
    plt.scatter(
        df_without_tracing['block_number'],
        df_without_tracing['number_of_instructions'],
        c='blue',
        label='Without tracing call',
        alpha=0.6,
        s=1,
        rasterized=True
    )
    
    # Plot blocks with tracing calls (using scatter for better performance with large datasets)
    plt.scatter(
        df_with_tracing['block_number'],
        df_with_tracing['number_of_instructions'],
        c='red',
        label='With tracing call',
        alpha=0.6,
        s=1,
        rasterized=True
    )

    # Add mean and median lines
    mean_val = df['number_of_instructions'].mean()
    median_val = df['number_of_instructions'].median()
    plt.axhline(y=mean_val, color='black', linestyle='--', linewidth=2, label=f'Mean ({mean_val:.2f})')
    plt.axhline(y=median_val, color='green', linestyle='-.', linewidth=2, label=f'Median ({median_val:.2f})')

    plt.xlabel('Block Number (sorted by size, separate per group)', fontsize=12)
    plt.ylabel('Number of Instructions per Block', fontsize=12)
    plt.title('Basic Block Characteristics (Combined)', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()

    if combined_file:
        plt.savefig(combined_file, dpi=600, bbox_inches='tight')
        print(f"\nCombined plot saved to: {combined_file}")
    else:
        plt.show()
    
    plt.close()

    # Plot 2: Only blocks with tracing calls
    if not df_with_tracing.empty:
        plt.figure(figsize=(12, 8))

        plt.scatter(
            df_with_tracing['block_number'],
            df_with_tracing['number_of_instructions'],
            c='red',
            label='With tracing call',
            alpha=0.6,
            s=1,
            rasterized=True
        )

        # Add mean and median lines
        mean_with = df_with_tracing['number_of_instructions'].mean()
        median_with = df_with_tracing['number_of_instructions'].median()
        plt.axhline(y=mean_with, color='black', linestyle='--', linewidth=2, label=f'Mean ({mean_with:.2f})')
        plt.axhline(y=median_with, color='green', linestyle='-.', linewidth=2, label=f'Median ({median_with:.2f})')

        plt.xlabel('Block Number (sorted by size)', fontsize=12)
        plt.ylabel('Number of Instructions per Block', fontsize=12)
        plt.title('Basic Block Characteristics (With Tracing Call)', fontsize=14)
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3, linestyle='--', axis='y')
        plt.tight_layout()

        if with_tracing_file:
            plt.savefig(with_tracing_file, dpi=600, bbox_inches='tight')
            print(f"With tracing plot saved to: {with_tracing_file}")
        else:
            plt.show()
        
        plt.close()

    # Plot 3: Only blocks without tracing calls
    if not df_without_tracing.empty:
        plt.figure(figsize=(12, 8))
        
        plt.scatter(
            df_without_tracing['block_number'],
            df_without_tracing['number_of_instructions'],
            c='blue',
            label='Without tracing call',
            alpha=0.6,
            s=1,
            rasterized=True
        )

        # Add mean and median lines
        mean_without = df_without_tracing['number_of_instructions'].mean()
        median_without = df_without_tracing['number_of_instructions'].median()
        plt.axhline(y=mean_without, color='black', linestyle='--', linewidth=2, label=f'Mean ({mean_without:.2f})')
        plt.axhline(y=median_without, color='green', linestyle='-.', linewidth=2, label=f'Median ({median_without:.2f})')

        plt.xlabel('Block Number (sorted by size)', fontsize=12)
        plt.ylabel('Number of Instructions per Block', fontsize=12)
        plt.title('Basic Block Characteristics (Without Tracing Call)', fontsize=14)
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3, linestyle='--', axis='y')
        plt.tight_layout()

        if without_tracing_file:
            plt.savefig(without_tracing_file, dpi=600, bbox_inches='tight')
            print(f"Without tracing plot saved to: {without_tracing_file}")
        else:
            plt.show()
        
        plt.close()


def main():
    """Parse command-line arguments and generate the plots."""
    parser = argparse.ArgumentParser(
        description='Plot basic block characteristics from CSV data. Generates three plots: combined, with tracing, and without tracing.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv
  %(prog)s input.csv -o output.png
  %(prog)s data/mir_analysis_basicblocks.csv -o block_plot.pdf
  
Output:
  When specifying -o output.png, generates:
    - output_combined.png
    - output_with_tracing.png
    - output_without_tracing.png
        """
    )
    
    parser.add_argument(
        'csv_file',
        type=Path,
        help='Path to the input CSV file'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Base path for output plots (e.g., plot.png, plot.pdf). Three files will be created with suffixes. If not specified, displays interactively.'
    )

    args = parser.parse_args()

    # Generate the plots
    plot_blocks(args.csv_file, args.output)


if __name__ == '__main__':
    main()

