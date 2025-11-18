#!/usr/bin/env python3
"""
Plot basic block characteristics from CSV data using fast chart types.

This script creates multiple types of visualisations optimised for large datasets:
1. Line plot (filled area) showing sorted block sizes
2. Histogram comparing instruction count distributions
3. Cumulative Distribution Function (CDF) plot
4. Box plot comparing the two groups
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def create_line_plot(df_all, df_with_tracing, df_without_tracing, output_file=None):
    """Create line plot showing block sizes sorted by instruction count."""
    plt.figure(figsize=(12, 8))
    
    # Plot as lines (much faster than bars)
    plt.plot(
        df_without_tracing['block_number'],
        df_without_tracing['number_of_instructions'],
        color='blue',
        label='Without tracing call',
        linewidth=0.5,
        alpha=0.7
    )
    
    plt.plot(
        df_with_tracing['block_number'],
        df_with_tracing['number_of_instructions'],
        color='red',
        label='With tracing call',
        linewidth=0.5,
        alpha=0.7
    )
    
    # Add mean and median lines
    mean_val = df_all['number_of_instructions'].mean()
    median_val = df_all['number_of_instructions'].median()
    plt.axhline(y=mean_val, color='black', linestyle='--', linewidth=2, label=f'Mean ({mean_val:.2f})')
    plt.axhline(y=median_val, color='green', linestyle='-.', linewidth=2, label=f'Median ({median_val:.2f})')
    
    plt.xlabel('Block Number (sorted by size, separate per group)', fontsize=12)
    plt.ylabel('Number of Instructions per Block', fontsize=12)
    plt.title('Basic Block Size Distribution (Line Plot)', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Line plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_histogram(df_with_tracing, df_without_tracing, output_file=None):
    """Create histogram comparing instruction count distributions."""
    plt.figure(figsize=(12, 8))
    
    # Determine bins (use log scale if data spans multiple orders of magnitude)
    all_data = pd.concat([
        df_with_tracing['number_of_instructions'],
        df_without_tracing['number_of_instructions']
    ])
    max_val = all_data.max()
    
    # Use appropriate bins
    if max_val > 100:
        bins = np.logspace(0, np.log10(max_val + 1), 50)
        use_log = True
    else:
        bins = 50
        use_log = False
    
    plt.hist(
        df_without_tracing['number_of_instructions'],
        bins=bins,
        color='blue',
        alpha=0.6,
        label='Without tracing call',
        edgecolor='none'
    )
    
    plt.hist(
        df_with_tracing['number_of_instructions'],
        bins=bins,
        color='red',
        alpha=0.6,
        label='With tracing call',
        edgecolor='none'
    )
    
    if use_log:
        plt.xscale('log')
    
    plt.xlabel('Number of Instructions per Block', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Distribution of Block Sizes (Histogram)', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Histogram saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_cdf_plot(df_with_tracing, df_without_tracing, output_file=None):
    """Create Cumulative Distribution Function plot."""
    plt.figure(figsize=(12, 8))
    
    # Calculate CDFs
    without_sorted = np.sort(df_without_tracing['number_of_instructions'])
    without_cdf = np.arange(1, len(without_sorted) + 1) / len(without_sorted)
    
    with_sorted = np.sort(df_with_tracing['number_of_instructions'])
    with_cdf = np.arange(1, len(with_sorted) + 1) / len(with_sorted)
    
    # Plot CDFs
    plt.plot(without_sorted, without_cdf, color='blue', linewidth=2, 
             label='Without tracing call', alpha=0.7)
    plt.plot(with_sorted, with_cdf, color='red', linewidth=2, 
             label='With tracing call', alpha=0.7)
    
    # Add percentile lines
    for percentile in [25, 50, 75]:
        plt.axhline(y=percentile/100, color='gray', linestyle=':', 
                   linewidth=1, alpha=0.5)
        plt.text(plt.xlim()[1], percentile/100, f'{percentile}th', 
                va='center', fontsize=9, color='gray')
    
    plt.xlabel('Number of Instructions per Block', fontsize=12)
    plt.ylabel('Cumulative Probability', fontsize=12)
    plt.title('Cumulative Distribution Function of Block Sizes', fontsize=14)
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"CDF plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_box_plot(df_with_tracing, df_without_tracing, output_file=None):
    """Create box plot comparing the two groups."""
    plt.figure(figsize=(10, 8))
    
    # Prepare data for box plot
    data_to_plot = [
        df_without_tracing['number_of_instructions'],
        df_with_tracing['number_of_instructions']
    ]
    labels = ['Without tracing call', 'With tracing call']
    
    bp = plt.boxplot(data_to_plot, labels=labels, patch_artist=True,
                     showmeans=True, meanline=True)
    
    # Customise colors
    colors = ['blue', 'red']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    plt.ylabel('Number of Instructions per Block', fontsize=12)
    plt.title('Block Size Comparison (Box Plot)', fontsize=14)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    # Print summary statistics
    print("\nBox Plot Summary:")
    for label, data in zip(labels, data_to_plot):
        print(f"\n{label}:")
        print(f"  Min: {data.min():.2f}")
        print(f"  Q1: {data.quantile(0.25):.2f}")
        print(f"  Median: {data.median():.2f}")
        print(f"  Q3: {data.quantile(0.75):.2f}")
        print(f"  Max: {data.max():.2f}")
        print(f"  Mean: {data.mean():.2f}")
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"\nBox plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_violin_plot(df_with_tracing, df_without_tracing, output_file=None):
    """Create violin plot comparing the two groups."""
    plt.figure(figsize=(10, 8))
    
    # Prepare data for violin plot
    data_to_plot = [
        df_without_tracing['number_of_instructions'],
        df_with_tracing['number_of_instructions']
    ]
    labels = ['Without\ntracing call', 'With\ntracing call']
    
    parts = plt.violinplot(data_to_plot, positions=[1, 2], showmeans=True, 
                          showmedians=True, widths=0.7)
    
    # Customise colors
    colors = ['blue', 'red']
    for pc, color in zip(parts['bodies'], colors):
        pc.set_facecolor(color)
        pc.set_alpha(0.6)
    
    plt.xticks([1, 2], labels)
    plt.ylabel('Number of Instructions per Block', fontsize=12)
    plt.title('Block Size Distribution (Violin Plot)', fontsize=14)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Violin plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def calculate_bucket_distribution(df, df_with_tracing, df_without_tracing):
    """
    Calculate distribution of blocks in specific instruction count buckets.
    
    Returns buckets definition and results for all datasets.
    """
    # Define buckets
    buckets = [
        ('1--3', 1, 3),
        ('4--6', 4, 6),
        ('7--10', 7, 10),
        ('11--20', 11, 20),
        ('21+', 21, float('inf'))
    ]
    
    # Calculate distributions for each dataset
    datasets = [
        ('With Tracing', df_with_tracing),
        ('Without Tracing', df_without_tracing),
        ('All Blocks', df)
    ]
    
    results = {}
    for name, data in datasets:
        results[name] = []
        total = len(data)
        for bucket_name, min_val, max_val in buckets:
            if max_val == float('inf'):
                count = len(data[data['number_of_instructions'] >= min_val])
            else:
                count = len(data[(data['number_of_instructions'] >= min_val) & 
                                (data['number_of_instructions'] <= max_val)])
            percentage = (count / total * 100) if total > 0 else 0
            results[name].append((bucket_name, count, percentage))
    
    return buckets, datasets, results


def create_bucket_plot(df, df_with_tracing, df_without_tracing, output_file=None):
    """Create grouped bar chart showing bucket distributions."""
    buckets, datasets, results = calculate_bucket_distribution(df, df_with_tracing, df_without_tracing)
    
    # Prepare data for plotting
    bucket_labels = [b[0] for b in buckets]
    with_tracing_percentages = [results['With Tracing'][i][2] for i in range(len(buckets))]
    without_tracing_percentages = [results['Without Tracing'][i][2] for i in range(len(buckets))]
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    x = np.arange(len(bucket_labels))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, without_tracing_percentages, width, 
                   label='Without tracing call', color='blue', alpha=0.7)
    bars2 = ax.bar(x + width/2, with_tracing_percentages, width, 
                   label='With tracing call', color='red', alpha=0.7)
    
    # Add value labels on bars
    def autolabel(bars):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.1f}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=9)
    
    autolabel(bars1)
    autolabel(bars2)
    
    ax.set_xlabel('Instruction Count Bucket', fontsize=12)
    ax.set_ylabel('Percentage of Blocks', fontsize=12)
    ax.set_title('Block Size Distribution by Bucket', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(bucket_labels)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Bucket distribution plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def print_bucket_distribution(df, df_with_tracing, df_without_tracing):
    """
    Print distribution of blocks in specific instruction count buckets.
    
    Outputs data in LaTeX table format for buckets: 1-3, 4-6, 7-10, 11-20, 21+
    """
    buckets, datasets, results = calculate_bucket_distribution(df, df_with_tracing, df_without_tracing)
    
    print("\n" + "="*80)
    print("BUCKET DISTRIBUTION ANALYSIS")
    print("="*80)
    
    # Print as readable table
    print("\nReadable Format:")
    print("-" * 80)
    header = f"{'Bucket':<10}"
    for name, _ in datasets:
        header += f"{name:<25}"
    print(header)
    print("-" * 80)
    
    for i, (bucket_name, _, _) in enumerate(buckets):
        row = f"{bucket_name:<10}"
        for name, _ in datasets:
            count, percentage = results[name][i][1], results[name][i][2]
            row += f"{count:>8} ({percentage:>5.1f}%)     "
        print(row)
    
    print("-" * 80)
    for name, data in datasets:
        print(f"Total {name}: {len(data)}")
    
    # Print LaTeX table format
    print("\n" + "="*80)
    print("LATEX TABLE FORMAT")
    print("="*80)
    print("\n\\midrule")
    
    for i, (bucket_name, _, _) in enumerate(buckets):
        row_parts = [bucket_name.replace('+', '$+$')]
        
        for name, _ in datasets:
            count, percentage = results[name][i][1], results[name][i][2]
            # Format count with comma thousands separator
            count_str = f"{count:,}".replace(',', '{,}')
            row_parts.append(f"{count_str:<8}")
            row_parts.append(f"{percentage:>4.1f}\\%")
        
        row = " & ".join(row_parts) + " \\\\"
        print(row)
    
    print("\\midrule")
    
    # Print column headers suggestion
    print("\n% Suggested column headers:")
    print("% Bucket & With Tracing & % & Without Tracing & % & All Blocks & % \\\\")
    
    print("\n" + "="*80)


def plot_all(csv_file: Path, output_file: Path = None):
    """
    Create multiple fast visualisations of block characteristics.
    
    Args:
        csv_file: Path to the input CSV file
        output_file: Optional base path to save plots
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
    
    # Print summary statistics
    total_blocks = len(df)
    blocks_with_tracing = len(df_with_tracing)
    blocks_without_tracing = len(df_without_tracing)
    
    print(f"\nSummary Statistics:")
    print(f"  Total blocks: {total_blocks}")
    print(f"  Blocks with tracing call: {blocks_with_tracing} ({100*blocks_with_tracing/total_blocks:.1f}%)")
    print(f"  Blocks without tracing call: {blocks_without_tracing} ({100*blocks_without_tracing/total_blocks:.1f}%)")
    
    # Determine output file names
    if output_file:
        output_path = Path(output_file)
        stem = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent
        
        line_file = parent / f"{stem}_line{suffix}"
        hist_file = parent / f"{stem}_histogram{suffix}"
        cdf_file = parent / f"{stem}_cdf{suffix}"
        box_file = parent / f"{stem}_boxplot{suffix}"
        violin_file = parent / f"{stem}_violin{suffix}"
        bucket_file = parent / f"{stem}_buckets{suffix}"
    else:
        line_file = hist_file = cdf_file = box_file = violin_file = bucket_file = None
    
    # Create all plots
    print("\nGenerating plots...")
    create_line_plot(df, df_with_tracing, df_without_tracing, line_file)
    create_histogram(df_with_tracing, df_without_tracing, hist_file)
    create_cdf_plot(df_with_tracing, df_without_tracing, cdf_file)
    create_box_plot(df_with_tracing, df_without_tracing, box_file)
    create_violin_plot(df_with_tracing, df_without_tracing, violin_file)
    create_bucket_plot(df, df_with_tracing, df_without_tracing, bucket_file)
    
    # Print bucket distribution statistics
    print_bucket_distribution(df, df_with_tracing, df_without_tracing)
    
    print("\nAll plots generated successfully!")


def main():
    """Parse command-line arguments and generate plots."""
    parser = argparse.ArgumentParser(
        description='Create fast visualisations of basic block characteristics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv
  %(prog)s input.csv -o output.png
  %(prog)s data/mir_analysis_basicblocks.csv -o analysis.png

Output:
  Generates 6 different plot types:
    - Line plot: Shows sorted block sizes
    - Histogram: Distribution comparison
    - CDF: Cumulative distribution function
    - Box plot: Statistical comparison
    - Violin plot: Distribution shapes
    - Bucket plot: Distribution by instruction count buckets (1-3, 4-6, 7-10, 11-20, 21+)
  
  Also prints bucket distribution statistics in LaTeX table format.
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
        help='Base path for output plots. Multiple files will be created with different suffixes.'
    )
    
    args = parser.parse_args()
    
    # Generate all plots
    plot_all(args.csv_file, args.output)


if __name__ == '__main__':
    main()

