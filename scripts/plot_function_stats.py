#!/usr/bin/env python3
"""
Plot function statistics from CSV data.

This script reads a CSV file containing function information and creates
visualisations showing the distribution of boolean flags across functions.
Each boolean flag (is_optimised, is_unoptimised, is_address_taken, is_outlined)
is represented with a different colour.
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def create_bar_chart(df, output_file=None):
    """Create bar chart showing counts for each boolean flag."""
    plt.figure(figsize=(12, 8))
    
    # Count True values for each boolean column
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    counts = [df[col].sum() for col in bool_columns]
    labels = ['Optimised', 'Unoptimised', 'Address Taken', 'Outlined']
    colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12']
    
    bars = plt.bar(labels, counts, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count)}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    plt.xlabel('Function Property', fontsize=12)
    plt.ylabel('Number of Functions', fontsize=12)
    plt.title('yklua IR Function Distribution by Type (Call-Routing MVIR)', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Bar chart saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_pie_charts(df, output_file=None):
    """Create pie charts for each boolean flag."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Function Property Distributions', fontsize=16, fontweight='bold')
    
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    titles = ['Optimised Functions', 'Unoptimised Functions', 
              'Address Taken Functions', 'Outlined Functions']
    colors_list = [
        ['#2ecc71', '#ecf0f1'],
        ['#e74c3c', '#ecf0f1'],
        ['#3498db', '#ecf0f1'],
        ['#f39c12', '#ecf0f1']
    ]
    
    for ax, col, title, colors in zip(axes.flat, bool_columns, titles, colors_list):
        true_count = df[col].sum()
        false_count = len(df) - true_count
        
        wedges, texts, autotexts = ax.pie(
            [true_count, false_count],
            labels=['True', 'False'],
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            explode=(0.05, 0)
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(11)
            autotext.set_fontweight('bold')
        
        ax.set_title(f'{title}\n(Total: {true_count} / {len(df)})', 
                    fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Pie charts saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_stacked_bar(df, output_file=None):
    """Create stacked bar chart showing overlapping properties."""
    plt.figure(figsize=(14, 8))
    
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    labels = ['Optimised', 'Unoptimised', 'Address Taken', 'Outlined']
    colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12']
    
    true_counts = [df[col].sum() for col in bool_columns]
    false_counts = [len(df) - count for count in true_counts]
    
    x = np.arange(len(labels))
    width = 0.6
    
    bars1 = plt.bar(x, true_counts, width, label='True', color=colors, alpha=0.8)
    bars2 = plt.bar(x, false_counts, width, bottom=true_counts, 
                   label='False', color='#ecf0f1', alpha=0.6)
    
    # Add value labels
    for i, (bar1, bar2, true_c, false_c) in enumerate(zip(bars1, bars2, true_counts, false_counts)):
        # Label for True portion
        plt.text(bar1.get_x() + bar1.get_width()/2., true_c/2,
                f'{int(true_c)}',
                ha='center', va='center', fontsize=11, fontweight='bold', color='white')
        # Label for False portion
        plt.text(bar2.get_x() + bar2.get_width()/2., true_c + false_c/2,
                f'{int(false_c)}',
                ha='center', va='center', fontsize=10, color='#7f8c8d')
    
    plt.xlabel('Function Property', fontsize=12)
    plt.ylabel('Number of Functions', fontsize=12)
    plt.title('Function Properties: True vs False', fontsize=14, fontweight='bold')
    plt.xticks(x, labels)
    plt.legend(loc='upper right', fontsize=11)
    plt.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Stacked bar chart saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_function_index_plot(df, output_file=None):
    """Create scatter plot showing function properties across function indices."""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    labels = ['Optimised', 'Unoptimised', 'Address Taken', 'Outlined']
    colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12']
    markers = ['o', 's', '^', 'D']
    
    for col, label, color, marker in zip(bool_columns, labels, colors, markers):
        df_true = df[df[col] == True]
        if not df_true.empty:
            ax.scatter(df_true['function_index'], 
                      [label] * len(df_true),
                      c=color, 
                      s=50, 
                      alpha=0.6,
                      marker=marker,
                      label=label,
                      edgecolors='black',
                      linewidth=0.5)
    
    ax.set_xlabel('Function Index', fontsize=12)
    ax.set_ylabel('Property', fontsize=12)
    ax.set_title('Function Properties Distribution Across Function Indices', 
                fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--', axis='x')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Function index plot saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def create_combination_heatmap(df, output_file=None):
    """Create heatmap showing property combinations."""
    plt.figure(figsize=(10, 8))
    
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    
    # Create correlation matrix
    corr_matrix = df[bool_columns].astype(int).corr()
    
    # Create heatmap
    im = plt.imshow(corr_matrix, cmap='RdYlGn', aspect='auto', vmin=-1, vmax=1)
    
    # Set ticks and labels
    labels = ['Optimised', 'Unoptimised', 'Address\nTaken', 'Outlined']
    plt.xticks(range(len(labels)), labels, fontsize=11)
    plt.yticks(range(len(labels)), labels, fontsize=11)
    
    # Add colorbar
    cbar = plt.colorbar(im, fraction=0.046, pad=0.04)
    cbar.set_label('Correlation', fontsize=11)
    
    # Add text annotations
    for i in range(len(bool_columns)):
        for j in range(len(bool_columns)):
            text = plt.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}',
                          ha="center", va="center", color="black", fontsize=11, fontweight='bold')
    
    plt.title('Property Correlation Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Heatmap saved to: {output_file}")
    else:
        plt.show()
    
    plt.close()


def print_statistics(df):
    """Print summary statistics."""
    print("\n" + "="*80)
    print("FUNCTION STATISTICS SUMMARY")
    print("="*80)
    
    print(f"\nTotal Functions: {len(df)}")
    
    bool_columns = ['is_optimised', 'is_unoptimised', 'is_address_taken', 'is_outlined']
    labels = ['Optimised', 'Unoptimised', 'Address Taken', 'Outlined']
    
    print("\nProperty Counts:")
    print("-" * 80)
    for col, label in zip(bool_columns, labels):
        count = df[col].sum()
        percentage = (count / len(df)) * 100
        print(f"  {label:<20}: {count:>6} ({percentage:>5.1f}%)")
    
    # Check for combinations
    print("\nProperty Combinations:")
    print("-" * 80)
    
    # Optimised AND address taken
    opt_addr = df[df['is_optimised'] & df['is_address_taken']].shape[0]
    print(f"  Optimised + Address Taken: {opt_addr}")
    
    # Unoptimised AND address taken
    unopt_addr = df[df['is_unoptimised'] & df['is_address_taken']].shape[0]
    print(f"  Unoptimised + Address Taken: {unopt_addr}")
    
    # Outlined functions
    outlined_opt = df[df['is_outlined'] & df['is_optimised']].shape[0]
    outlined_unopt = df[df['is_outlined'] & df['is_unoptimised']].shape[0]
    print(f"  Outlined + Optimised: {outlined_opt}")
    print(f"  Outlined + Unoptimised: {outlined_unopt}")
    
    # Both optimised and unoptimised (should be rare/none)
    both = df[df['is_optimised'] & df['is_unoptimised']].shape[0]
    print(f"  Both Optimised AND Unoptimised: {both}")
    
    # Neither optimised nor unoptimised
    neither = df[~df['is_optimised'] & ~df['is_unoptimised']].shape[0]
    print(f"  Neither Optimised nor Unoptimised: {neither}")
    
    print("\n" + "="*80)


def plot_all(csv_file: Path, output_file: Path = None):
    """
    Create multiple visualisations of function statistics.
    
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
    required_columns = ['function_name', 'function_index', 'is_optimised', 
                       'is_unoptimised', 'is_address_taken', 'is_outlined']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Missing required columns: {missing_columns}", file=sys.stderr)
        print(f"Available columns: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)
    
    # Print statistics
    print_statistics(df)
    
    # Create bar chart
    print("\nGenerating bar chart...")
    create_bar_chart(df, output_file)
    
    print("\nBar chart generated successfully!")


def main():
    """Parse command-line arguments and generate plots."""
    parser = argparse.ArgumentParser(
        description='Create visualisations of function statistics.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.csv
  %(prog)s input.csv -o output.png
  %(prog)s data/2025_12_10_ir_analysis_function_stats.csv -o func_analysis.png

Output:
  Generates a bar chart showing the count of functions with each property.
  Also prints detailed statistics to console.
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

