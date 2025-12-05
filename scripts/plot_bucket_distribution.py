#!/usr/bin/env python3
"""
Plot block distribution by instruction count buckets.

Creates a grouped bar chart showing the distribution of basic blocks
across instruction count ranges, with separate bars for:
- Without tracing (optimised)
- With tracing (unoptimised)
- With tracing net (minus 3-instruction overhead)
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Configuration constants
LEGEND_FONTSIZE = 13
STATS_BOX_FONTSIZE = 13
BAR_LABEL_FONTSIZE = 9


def calculate_bucket_counts(df_with_tracing, df_without_tracing):
    """
    Calculate block counts in specific instruction count buckets.
    
    Returns bucket labels and counts for each category.
    """
    # Define buckets matching the target format
    buckets = [
        ('1--3', 1, 3),
        ('4--7', 4, 7),
        ('8--12', 8, 12),
        ('13--21', 13, 21),
        ('21+', 22, float('inf'))
    ]
    
    bucket_labels = [b[0] for b in buckets]
    without_tracing_counts = []
    with_tracing_counts = []
    with_tracing_net_counts = []
    
    # Calculate net instructions for blocks with tracing
    if not df_with_tracing.empty:
        df_with_tracing_net = df_with_tracing.copy()
        df_with_tracing_net['number_of_instructions'] = df_with_tracing_net['number_of_instructions'] - 3
    else:
        df_with_tracing_net = df_with_tracing.copy()
    
    # Calculate counts for each bucket
    for bucket_name, min_val, max_val in buckets:
        # Without tracing (optimised)
        if max_val == float('inf'):
            count_without = len(df_without_tracing[df_without_tracing['number_of_instructions'] >= min_val])
        else:
            count_without = len(df_without_tracing[
                (df_without_tracing['number_of_instructions'] >= min_val) & 
                (df_without_tracing['number_of_instructions'] <= max_val)
            ])
        without_tracing_counts.append(count_without)
        
        # With tracing (unoptimised)
        if max_val == float('inf'):
            count_with = len(df_with_tracing[df_with_tracing['number_of_instructions'] >= min_val])
        else:
            count_with = len(df_with_tracing[
                (df_with_tracing['number_of_instructions'] >= min_val) & 
                (df_with_tracing['number_of_instructions'] <= max_val)
            ])
        with_tracing_counts.append(count_with)
        
        # With tracing net (minus overhead)
        if not df_with_tracing_net.empty:
            if max_val == float('inf'):
                count_net = len(df_with_tracing_net[df_with_tracing_net['number_of_instructions'] >= min_val])
            else:
                count_net = len(df_with_tracing_net[
                    (df_with_tracing_net['number_of_instructions'] >= min_val) & 
                    (df_with_tracing_net['number_of_instructions'] <= max_val)
                ])
        else:
            count_net = 0
        with_tracing_net_counts.append(count_net)
    
    return bucket_labels, without_tracing_counts, with_tracing_counts, with_tracing_net_counts


def plot_bucket_distribution(csv_file: Path, output_file: Path = None):
    """
    Create grouped bar chart showing bucket distribution with absolute counts.
    
    Args:
        csv_file: Path to the input CSV file
        output_file: Optional path to save the plot
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
    required_columns = ['has_tracing_call', 'number_of_instructions']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Missing required columns: {missing_columns}", file=sys.stderr)
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)
    
    # Separate data by tracing call presence
    df_with_tracing = df[df['has_tracing_call'] == True].copy()
    df_without_tracing = df[df['has_tracing_call'] == False].copy()
    
    # Calculate bucket counts
    bucket_labels, without_counts, with_counts, with_net_counts = calculate_bucket_counts(
        df_with_tracing, df_without_tracing
    )
    
    # Print summary
    total_blocks = len(df)
    total_with_tracing = len(df_with_tracing)
    total_without_tracing = len(df_without_tracing)
    
    # Calculate instruction totals
    total_instructions = df['number_of_instructions'].sum()
    total_instr_with_tracing = df_with_tracing['number_of_instructions'].sum()
    total_instr_without_tracing = df_without_tracing['number_of_instructions'].sum()
    total_net_instr_with_tracing = total_instr_with_tracing - (3 * total_with_tracing)
    
    print(f"\nBucket Distribution Summary:")
    print(f"  Total blocks: {total_blocks:,}")
    print(f"  Total blocks with tracing: {total_with_tracing:,}")
    print(f"  Total blocks without tracing: {total_without_tracing:,}")
    print(f"\n  Total instructions: {total_instructions:,}")
    print(f"  Total instructions in blocks with tracing: {total_instr_with_tracing:,}")
    print(f"  Total net instructions in blocks with tracing: {total_net_instr_with_tracing:,}")
    print(f"  Total instructions in blocks without tracing: {total_instr_without_tracing:,}")
    print(f"\nBucket counts:")
    for i, label in enumerate(bucket_labels):
        print(f"  {label:>6}: Without={without_counts[i]:>6}, With={with_counts[i]:>6}, Net={with_net_counts[i]:>6}")

    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    x = np.arange(len(bucket_labels))
    width = 0.25  # Width of bars (3 bars per group)
    
    # Create bars
    bars1 = ax.bar(x - width, without_counts, width, 
                   label='Without SWT tracing (opt)', 
                   color='blue', alpha=0.8, edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x, with_counts, width, 
                   label='With SWT tracing (unopt)', 
                   color='orangered', alpha=0.8, edgecolor='black', linewidth=0.5)
    bars3 = ax.bar(x + width, with_net_counts, width, 
                   label='With SWT tracing (net, -3 instr)', 
                   color='orange', alpha=0.8, edgecolor='black', linewidth=0.5)
    
    # Add value labels on bars
    def add_labels(bars):
        for bar in bars:
            height = bar.get_height()
            if height > 0:  # Only label non-zero bars
                ax.annotate(f'{int(height):,}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom',
                           fontsize=BAR_LABEL_FONTSIZE, fontweight='bold')
    
    add_labels(bars1)
    add_labels(bars2)
    add_labels(bars3)
    
    # Customise plot
    ax.set_xlabel('Number of Instructions per Block', fontsize=12)
    ax.set_ylabel('Number of Blocks', fontsize=12)
    ax.set_title('Block Distribution by Instruction Count Buckets', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(bucket_labels)

    # Add bar legend at the top
    legend = ax.legend(loc='upper right', fontsize=12, bbox_to_anchor=(0.95, 0.98), framealpha=0.9)
    
    # Add blocks statistics text box
    blocks_text = (
        f'Total blocks: {total_blocks:,}\n'
        f'Total blocks with tracing: {total_with_tracing:,}\n'
        f'Total blocks without tracing: {total_without_tracing:,}'
    )
    ax.text(0.55, 0.73, blocks_text,
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment='top',
            horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, edgecolor='black', linewidth=0.5, pad=0.5))
    
    # Add instructions statistics text box
    instructions_text = (
        f'Total instructions: {total_instructions:,}\n'
        f'Total instructions in blocks with tracing: {total_instr_with_tracing:,}\n'
        f'Total net instructions in blocks with tracing: {total_net_instr_with_tracing:,}\n'
        f'Total instructions in blocks without tracing: {total_instr_without_tracing:,}'
    )
    ax.text(0.55, 0.50, instructions_text,
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment='top',
            horizontalalignment='left',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, edgecolor='black', linewidth=0.5, pad=0.5))
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')

    # Set y-axis to start at 0
    ax.set_ylim(bottom=0)
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"\nBucket distribution plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def main():
    """Parse command-line arguments and generate the plot."""
    parser = argparse.ArgumentParser(
        description='Plot block distribution by instruction count buckets.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv
  %(prog)s input.csv -o bucket_distribution.png
  %(prog)s db/data/mir_analysis_basicblocks.csv -o bucket_plot.pdf
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
        help='Path to save the plot (if not specified, displays interactively)'
    )
    
    args = parser.parse_args()
    
    # Generate the plot
    plot_bucket_distribution(args.csv_file, args.output)


if __name__ == '__main__':
    main()

