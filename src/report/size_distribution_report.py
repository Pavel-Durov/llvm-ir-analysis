"""Reporting utilities for block size distribution analysis."""

from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from size_analysis import BlockSizeAnalysis


def print_size_analysis(analysis: BlockSizeAnalysis, traced_funcs: dict[str, int], 
                        title: str, file_path: Path, num_functions: int) -> None:
    """Print complete size distribution analysis to stdout.
    
    Args:
        analysis: BlockSizeAnalysis results
        traced_funcs: Dictionary mapping function names to traced block counts
        title: Title for the report
        file_path: Path to the analysed file
        num_functions: Total number of functions in the file
    """
    print("="*80)
    print(title)
    print("="*80)
    print()
    
    print(f"File: {file_path}")
    print(f"Total functions: {num_functions:,}")
    print(f"Total blocks: {analysis.total_blocks:,}")
    print(f"  - Traced blocks: {analysis.traced_count:,} ({analysis.traced_percentage:.1f}%)")
    print(f"  - Untraced blocks: {analysis.untraced_count:,} ({analysis.untraced_percentage:.1f}%)")
    print()
    
    print("="*80)
    print("SIZE DISTRIBUTION")
    print("="*80)
    print()
    print(f"{'Size (inst)':<15} {'Traced':<15} {'Traced %':<12} {'Untraced':<15} {'Untraced %':<12}")
    print("-"*80)
    
    for size_label, t_count in analysis.traced_dist.items():
        # Find corresponding untraced count
        u_count = dict(analysis.untraced_dist.items())[size_label]
        t_pct = analysis.traced_dist.get_percentage(t_count)
        u_pct = analysis.untraced_dist.get_percentage(u_count)
        
        print(f"{size_label:<15} {t_count:<15,} {t_pct:<11.1f}% {u_count:<15,} {u_pct:<11.1f}%")
    
    print("-"*80)
    print(f"{'Total':<15} {analysis.traced_count:<15,} {'100.0%':<12} {analysis.untraced_count:<15,} {'100.0%':<12}")
    print()
    
    print("="*80)
    print("AVERAGES")
    print("="*80)
    print()
    print(f"Traced blocks:   {analysis.traced_avg:.2f} instructions/block")
    print(f"Untraced blocks: {analysis.untraced_avg:.2f} instructions/block")
    print(f"Difference:      {analysis.difference:.2f} instructions")
    if analysis.untraced_avg > 0:
        print(f"Ratio:           {analysis.ratio:.2f}×")
    print()
    
    print("="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print()
    
    tiny_traced_pct = analysis.traced_dist.get_percentage(analysis.traced_dist.tiny)
    tiny_untraced_pct = analysis.untraced_dist.get_percentage(analysis.untraced_dist.tiny)
    
    print(f"• {tiny_traced_pct:.1f}% of traced blocks are tiny (1-3 inst)")
    print(f"• {tiny_untraced_pct:.1f}% of untraced blocks are tiny (1-3 inst)")
    print(f"• Untraced population: {analysis.untraced_dist.tiny:,} tiny blocks")
    print(f"• Selection pattern: Only {analysis.traced_percentage:.1f}% of blocks have tracing")
    print()
    
    # Show sample functions with traced blocks
    if traced_funcs:
        print("="*80)
        print("SAMPLE FUNCTIONS WITH TRACING (top 10)")
        print("="*80)
        print()
        for i, (func, count) in enumerate(sorted(traced_funcs.items(), key=lambda x: x[1], reverse=True)[:10], 1):
            print(f"{i:2d}. {func}: {count} traced blocks")
        print()


def print_adjusted_analysis(original: BlockSizeAnalysis, traced_blocks_data: list[dict], 
                           overhead: int = 3) -> None:
    """Print adjusted size distribution analysis (with tracing overhead subtracted).
    
    Args:
        original: Original BlockSizeAnalysis before adjustment
        traced_blocks_data: List of traced block dictionaries with 'num_instructions'
        overhead: Number of instructions to subtract (default: 3)
    """
    from size_analysis import create_adjusted_analysis
    
    adjusted = create_adjusted_analysis(original, traced_blocks_data, overhead)
    
    print("="*80)
    print(f"ADJUSTED SIZE DISTRIBUTION (Tracing Overhead -{overhead} instructions)")
    print("="*80)
    print()
    print(f"{'Size (inst)':<15} {'Traced':<15} {'Traced %':<12} {'Untraced':<15} {'Untraced %':<12}")
    print("-"*80)
    
    for size_label, t_count in adjusted.traced_dist.items():
        # Find corresponding untraced count (unchanged)
        u_count = dict(adjusted.untraced_dist.items())[size_label]
        t_pct = adjusted.traced_dist.get_percentage(t_count)
        u_pct = adjusted.untraced_dist.get_percentage(u_count)
        
        print(f"{size_label:<15} {t_count:<15,} {t_pct:<11.1f}% {u_count:<15,} {u_pct:<11.1f}%")
    
    print("-"*80)
    print(f"{'Total':<15} {adjusted.traced_count:<15,} {'100.0%':<12} {adjusted.untraced_count:<15,} {'100.0%':<12}")
    print()
    
    print("="*80)
    print("ADJUSTED AVERAGES")
    print("="*80)
    print()
    print(f"Traced blocks (adjusted):   {adjusted.traced_avg:.2f} instructions/block")
    print(f"Untraced blocks:            {adjusted.untraced_avg:.2f} instructions/block")
    print(f"Difference:                 {adjusted.difference:.2f} instructions")
    if adjusted.untraced_avg > 0:
        print(f"Ratio:                      {adjusted.ratio:.2f}×")
    print()
    
    print("="*80)
    print("KEY INSIGHTS (ADJUSTED)")
    print("="*80)
    print()
    
    # Calculate percentage changes
    orig_diff = original.difference
    adj_diff = adjusted.difference
    reduction = orig_diff - adj_diff
    reduction_pct = (reduction / orig_diff * 100) if orig_diff > 0 else 0
    
    print(f"• Original difference: {orig_diff:.2f} instructions")
    print(f"• Adjusted difference: {adj_diff:.2f} instructions")
    print(f"• Reduction:          {reduction:.2f} instructions ({reduction_pct:.1f}%)")
    print()
    
    tiny_traced_pct = adjusted.traced_dist.get_percentage(adjusted.traced_dist.tiny)
    print(f"• After removing {overhead}-instruction overhead:")
    print(f"  - {tiny_traced_pct:.1f}% of traced blocks would be tiny (1-3 inst)")
    print(f"  - {adjusted.traced_dist.tiny:,} traced blocks moved to tiny category")
    print()

