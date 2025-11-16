"""Tests for size distribution analysis module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
import tempfile
import csv
from size_analysis import (
    SizeDistribution,
    BlockSizeAnalysis,
    categorize_by_size,
    create_distribution,
    analyze_csv_blocks,
    create_adjusted_analysis,
)


class TestSizeDistribution:
    """Tests for SizeDistribution dataclass."""

    def test_size_distribution_initialization(self):
        """Test SizeDistribution can be initialised with defaults."""
        dist = SizeDistribution()
        assert dist.tiny == 0
        assert dist.small == 0
        assert dist.medium == 0
        assert dist.large == 0
        assert dist.xlarge == 0

    def test_size_distribution_with_values(self):
        """Test SizeDistribution initialisation with custom values."""
        dist = SizeDistribution(tiny=10, small=20, medium=30, large=40, xlarge=50)
        assert dist.tiny == 10
        assert dist.small == 20
        assert dist.medium == 30
        assert dist.large == 40
        assert dist.xlarge == 50

    def test_size_distribution_total(self):
        """Test total() method returns correct sum."""
        dist = SizeDistribution(tiny=5, small=10, medium=15, large=20, xlarge=25)
        assert dist.total() == 75

    def test_size_distribution_total_empty(self):
        """Test total() returns zero for empty distribution."""
        dist = SizeDistribution()
        assert dist.total() == 0

    def test_size_distribution_get_percentage(self):
        """Test percentage calculation."""
        dist = SizeDistribution(tiny=25, small=25, medium=25, large=25, xlarge=0)
        assert dist.get_percentage(25) == 25.0
        assert dist.get_percentage(50) == 50.0

    def test_size_distribution_get_percentage_zero_total(self):
        """Test percentage returns 0 when total is zero."""
        dist = SizeDistribution()
        assert dist.get_percentage(0) == 0.0

    def test_size_distribution_items(self):
        """Test items() returns correct label-count pairs."""
        dist = SizeDistribution(tiny=1, small=2, medium=3, large=4, xlarge=5)
        items = list(dist.items())

        assert len(items) == 5
        assert items[0] == ('1-3', 1)
        assert items[1] == ('4-6', 2)
        assert items[2] == ('7-10', 3)
        assert items[3] == ('11-20', 4)
        assert items[4] == ('21+', 5)


class TestBlockSizeAnalysis:
    """Tests for BlockSizeAnalysis dataclass."""
    
    def test_block_size_analysis_properties(self):
        """Test BlockSizeAnalysis computed properties."""
        traced_dist = SizeDistribution(tiny=10, small=20, medium=30, large=40, xlarge=50)
        untraced_dist = SizeDistribution(tiny=100, small=200, medium=300, large=400, xlarge=500)
        
        analysis = BlockSizeAnalysis(
            total_blocks=1650,
            traced_count=150,
            untraced_count=1500,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=15.5,
            untraced_avg=8.2,
        )
        
        assert analysis.difference == pytest.approx(7.3)
        assert analysis.ratio == pytest.approx(15.5 / 8.2)
        assert analysis.traced_percentage == pytest.approx(150 / 1650 * 100)
        assert analysis.untraced_percentage == pytest.approx(1500 / 1650 * 100)
    
    def test_block_size_analysis_ratio_zero_untraced(self):
        """Test ratio returns 0 when untraced_avg is zero."""
        analysis = BlockSizeAnalysis(
            total_blocks=100,
            traced_count=100,
            untraced_count=0,
            traced_dist=SizeDistribution(),
            untraced_dist=SizeDistribution(),
            traced_avg=10.0,
            untraced_avg=0.0,
        )
        
        assert analysis.ratio == 0.0


class TestCategorizeBySize:
    """Tests for categorize_by_size function."""
    
    @pytest.mark.parametrize("size,expected", [
        (1, 'tiny'),
        (2, 'tiny'),
        (3, 'tiny'),
        (4, 'small'),
        (5, 'small'),
        (6, 'small'),
        (7, 'medium'),
        (8, 'medium'),
        (9, 'medium'),
        (10, 'medium'),
        (11, 'large'),
        (15, 'large'),
        (20, 'large'),
        (21, 'xlarge'),
        (50, 'xlarge'),
        (100, 'xlarge'),
    ])
    def test_categorize_by_size(self, size, expected):
        """Test instruction count categorisation."""
        assert categorize_by_size(size) == expected


class TestCreateDistribution:
    """Tests for create_distribution function."""
    
    def test_create_distribution_empty(self):
        """Test distribution creation with empty blocks list."""
        dist = create_distribution([])
        assert dist.total() == 0
    
    def test_create_distribution_single_category(self):
        """Test distribution with blocks in single category."""
        blocks = [
            {'num_instructions': 1},
            {'num_instructions': 2},
            {'num_instructions': 3},
        ]
        dist = create_distribution(blocks)
        
        assert dist.tiny == 3
        assert dist.small == 0
        assert dist.medium == 0
        assert dist.large == 0
        assert dist.xlarge == 0
    
    def test_create_distribution_multiple_categories(self):
        """Test distribution with blocks across multiple categories."""
        blocks = [
            {'num_instructions': 1},   # tiny
            {'num_instructions': 3},   # tiny
            {'num_instructions': 5},   # small
            {'num_instructions': 6},   # small
            {'num_instructions': 8},   # medium
            {'num_instructions': 10},  # medium
            {'num_instructions': 15},  # large
            {'num_instructions': 20},  # large
            {'num_instructions': 25},  # xlarge
            {'num_instructions': 100}, # xlarge
        ]
        dist = create_distribution(blocks)
        
        assert dist.tiny == 2
        assert dist.small == 2
        assert dist.medium == 2
        assert dist.large == 2
        assert dist.xlarge == 2


class TestAnalyzeCSVBlocks:
    """Tests for analyze_csv_blocks function."""
    
    def create_test_csv(self, rows):
        """Helper to create a temporary CSV file."""
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        writer = csv.writer(tmp)
        writer.writerow(['function_name', 'basicblock_id', 'has_tracing_call', 
                        'number_of_instructions', 'instructions'])
        writer.writerows(rows)
        tmp.close()
        return Path(tmp.name)
    
    def test_analyze_csv_blocks_basic(self):
        """Test basic CSV analysis."""
        rows = [
            ['func1', 'bb0', 'true', '5', 'inst1;inst2;inst3;inst4;inst5'],
            ['func1', 'bb1', 'false', '2', 'inst1;inst2'],
            ['func2', 'bb0', 'false', '8', 'inst1;inst2;inst3;inst4;inst5;inst6;inst7;inst8'],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            assert analysis.total_blocks == 3
            assert analysis.traced_count == 1
            assert analysis.untraced_count == 2
            assert analysis.traced_avg == 5.0
            assert analysis.untraced_avg == 5.0  # (2 + 8) / 2
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_deduplication(self):
        """Test that duplicate blocks are handled correctly."""
        rows = [
            ['func1', 'bb0', 'false', '3', 'inst1;inst2;inst3'],
            ['func1', 'bb0', 'true', '5', 'inst1;inst2;inst3;inst4;inst5'],  # Duplicate, traced
            ['func1', 'bb1', 'false', '2', 'inst1;inst2'],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # Should keep the traced version of bb0
            assert analysis.total_blocks == 2
            assert analysis.traced_count == 1
            assert analysis.untraced_count == 1
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_distribution(self):
        """Test size distribution calculation."""
        rows = [
            # Traced blocks
            ['func1', 'bb0', 'true', '2', ''],   # tiny
            ['func1', 'bb1', 'true', '5', ''],   # small
            ['func1', 'bb2', 'true', '8', ''],   # medium
            ['func1', 'bb3', 'true', '15', ''],  # large
            ['func1', 'bb4', 'true', '25', ''],  # xlarge

            # Untraced blocks
            ['func2', 'bb0', 'false', '1', ''],  # tiny
            ['func2', 'bb1', 'false', '1', ''],  # tiny
            ['func2', 'bb2', 'false', '4', ''],  # small
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # Check traced distribution
            assert analysis.traced_dist.tiny == 1
            assert analysis.traced_dist.small == 1
            assert analysis.traced_dist.medium == 1
            assert analysis.traced_dist.large == 1
            assert analysis.traced_dist.xlarge == 1
            
            # Check untraced distribution
            assert analysis.untraced_dist.tiny == 2
            assert analysis.untraced_dist.small == 1
            assert analysis.untraced_dist.medium == 0
            assert analysis.untraced_dist.large == 0
            assert analysis.untraced_dist.xlarge == 0
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_invalid_format(self):
        """Test that invalid CSV format raises ValueError."""
        # CSV without has_tracing_call column
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        writer = csv.writer(tmp)
        writer.writerow(['function_name', 'basicblock_id', 'number_of_instructions'])
        writer.writerow(['func1', 'bb0', '5'])
        tmp.close()
        csv_file = Path(tmp.name)
        
        try:
            with pytest.raises(ValueError, match="has_tracing_call"):
                analyze_csv_blocks(csv_file)
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_empty_blocks(self):
        """Test analysis with only header row."""
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        writer = csv.writer(tmp)
        writer.writerow(['function_name', 'basicblock_id', 'has_tracing_call', 
                        'number_of_instructions', 'instructions'])
        tmp.close()
        csv_file = Path(tmp.name)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            assert analysis.total_blocks == 0
            assert analysis.traced_count == 0
            assert analysis.untraced_count == 0
            assert analysis.traced_avg == 0.0
            assert analysis.untraced_avg == 0.0
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_percentages(self):
        """Test percentage calculations."""
        rows = [
            ['func1', 'bb0', 'true', '10', ''],
            ['func1', 'bb1', 'false', '5', ''],
            ['func1', 'bb2', 'false', '5', ''],
            ['func1', 'bb3', 'false', '5', ''],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # 1 traced out of 4 total = 25%
            assert analysis.traced_percentage == 25.0
            # 3 untraced out of 4 total = 75%
            assert analysis.untraced_percentage == 75.0
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_averages(self):
        """Test average instruction count calculations."""
        rows = [
            ['func1', 'bb0', 'true', '10', ''],
            ['func1', 'bb1', 'true', '20', ''],
            ['func1', 'bb2', 'false', '5', ''],
            ['func1', 'bb3', 'false', '15', ''],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # Traced average: (10 + 20) / 2 = 15.0
            assert analysis.traced_avg == 15.0
            # Untraced average: (5 + 15) / 2 = 10.0
            assert analysis.untraced_avg == 10.0
            # Difference: 15.0 - 10.0 = 5.0
            assert analysis.difference == 5.0
            # Ratio: 15.0 / 10.0 = 1.5
            assert analysis.ratio == 1.5
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_skip_invalid_rows(self):
        """Test that rows with insufficient columns are skipped."""
        rows = [
            ['func1', 'bb0', 'true', '5', 'inst1;inst2'],
            ['func1', 'bb1'],  # Invalid: too few columns
            ['func1', 'bb2', 'false', '3', 'inst1'],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # Should only count the 2 valid rows
            assert analysis.total_blocks == 2
        finally:
            csv_file.unlink()
    
    def test_analyze_csv_blocks_case_insensitive_tracing(self):
        """Test that has_tracing_call is case insensitive."""
        rows = [
            ['func1', 'bb0', 'True', '5', ''],
            ['func1', 'bb1', 'TRUE', '5', ''],
            ['func1', 'bb2', 'true', '5', ''],
            ['func1', 'bb3', 'False', '5', ''],
            ['func1', 'bb4', 'FALSE', '5', ''],
            ['func1', 'bb5', 'false', '5', ''],
        ]
        csv_file = self.create_test_csv(rows)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            assert analysis.traced_count == 3
            assert analysis.untraced_count == 3
        finally:
            csv_file.unlink()


class TestIntegration:
    """Integration tests for the complete analysis workflow."""
    
    def test_realistic_scenario(self):
        """Test with data resembling real-world usage."""
        rows = []
        
        # Simulate traced blocks (larger, more complex)
        for i in range(100):
            rows.append([f'traced_func_{i % 10}', f'bb{i}', 'true', str(10 + i % 15), ''])
        
        # Simulate untraced blocks (many small continuation blocks)
        for i in range(1000):
            rows.append([f'untraced_func_{i % 50}', f'bb{i}', 'false', str(1 + i % 5), ''])
        
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
        writer = csv.writer(tmp)
        writer.writerow(['function_name', 'basicblock_id', 'has_tracing_call', 
                        'number_of_instructions', 'instructions'])
        writer.writerows(rows)
        tmp.close()
        csv_file = Path(tmp.name)
        
        try:
            analysis = analyze_csv_blocks(csv_file)
            
            # Verify total counts
            assert analysis.total_blocks == 1100
            assert analysis.traced_count == 100
            assert analysis.untraced_count == 1000
            
            # Verify percentages
            assert analysis.traced_percentage == pytest.approx(100/1100 * 100)
            assert analysis.untraced_percentage == pytest.approx(1000/1100 * 100)
            
            # Traced blocks should have higher average (10-24 range)
            assert analysis.traced_avg > analysis.untraced_avg
            
            # Untraced should have many tiny blocks (1-5 range)
            assert analysis.untraced_dist.tiny > 0
        finally:
            csv_file.unlink()


class TestCreateAdjustedAnalysis:
    """Tests for create_adjusted_analysis function."""
    
    def test_create_adjusted_analysis_basic(self):
        """Test basic adjustment of traced blocks."""
        # Create original analysis
        traced_dist = SizeDistribution(tiny=0, small=10, medium=20, large=30, xlarge=10)
        untraced_dist = SizeDistribution(tiny=100, small=50, medium=30, large=15, xlarge=5)
        
        original = BlockSizeAnalysis(
            total_blocks=270,
            traced_count=70,
            untraced_count=200,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=15.0,
            untraced_avg=5.0,
        )
        
        # Create traced blocks data
        traced_blocks_data = [
            {'num_instructions': 4},   # Will become 1 (tiny)
            {'num_instructions': 5},   # Will become 2 (tiny)
            {'num_instructions': 6},   # Will become 3 (tiny)
            {'num_instructions': 10},  # Will become 7 (medium)
            {'num_instructions': 15},  # Will become 12 (large)
        ]
        
        # Create adjusted analysis
        adjusted = create_adjusted_analysis(original, traced_blocks_data, overhead=3)
        
        # Check that untraced data is unchanged
        assert adjusted.untraced_count == original.untraced_count
        assert adjusted.untraced_avg == original.untraced_avg
        assert adjusted.untraced_dist.tiny == original.untraced_dist.tiny
        
        # Check that traced count is preserved from original
        assert adjusted.traced_count == original.traced_count
        
        # Check that traced average is reduced by overhead
        # Note: The adjusted avg is calculated from traced_blocks_data, not original.traced_count
        expected_avg = sum(max(1, b['num_instructions'] - 3) for b in traced_blocks_data) / len(traced_blocks_data)
        assert adjusted.traced_avg == pytest.approx(expected_avg)
    
    def test_create_adjusted_analysis_distribution_shift(self):
        """Test that blocks shift to smaller categories after adjustment."""
        # Original: no tiny traced blocks
        traced_dist = SizeDistribution(tiny=0, small=10, medium=20, large=10, xlarge=0)
        untraced_dist = SizeDistribution(tiny=50, small=30, medium=20, large=0, xlarge=0)
        
        original = BlockSizeAnalysis(
            total_blocks=140,
            traced_count=40,
            untraced_count=100,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=10.0,
            untraced_avg=4.0,
        )
        
        # Create traced blocks that will shift categories
        traced_blocks_data = []
        # 10 blocks of 4-6 inst (small) -> will become 1-3 inst (tiny)
        for _ in range(10):
            traced_blocks_data.append({'num_instructions': 5})
        # 20 blocks of 7-10 inst (medium) -> will become 4-7 inst (small/medium)
        for _ in range(20):
            traced_blocks_data.append({'num_instructions': 8})
        # 10 blocks of 11-20 inst (large) -> will become 8-17 inst (medium/large)
        for _ in range(10):
            traced_blocks_data.append({'num_instructions': 15})
        
        adjusted = create_adjusted_analysis(original, traced_blocks_data, overhead=3)
        
        # After removing 3 instructions, some blocks should be in tiny category
        assert adjusted.traced_dist.tiny > 0
        # Average should be reduced
        assert adjusted.traced_avg < original.traced_avg
        # Difference should also be reduced
        assert adjusted.difference < original.difference
    
    def test_create_adjusted_analysis_minimum_one_instruction(self):
        """Test that adjusted blocks have minimum 1 instruction."""
        traced_dist = SizeDistribution(tiny=5, small=0, medium=0, large=0, xlarge=0)
        untraced_dist = SizeDistribution(tiny=10, small=0, medium=0, large=0, xlarge=0)
        
        original = BlockSizeAnalysis(
            total_blocks=15,
            traced_count=5,
            untraced_count=10,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=2.0,
            untraced_avg=2.0,
        )
        
        # Create blocks with very few instructions
        traced_blocks_data = [
            {'num_instructions': 1},  # Will try to become -2, but capped at 1
            {'num_instructions': 2},  # Will try to become -1, but capped at 1
            {'num_instructions': 3},  # Will become 0, but capped at 1
            {'num_instructions': 4},  # Will become 1
            {'num_instructions': 5},  # Will become 2
        ]
        
        adjusted = create_adjusted_analysis(original, traced_blocks_data, overhead=3)
        
        # All adjusted blocks should have at least 1 instruction
        # Expected: [1, 1, 1, 1, 2] -> avg = 1.2
        assert adjusted.traced_avg == pytest.approx(1.2)
        
        # All 5 blocks should still be in tiny category (1-3 inst)
        assert adjusted.traced_dist.tiny == 5
    
    def test_create_adjusted_analysis_empty_traced_blocks(self):
        """Test handling of empty traced blocks list."""
        traced_dist = SizeDistribution()
        untraced_dist = SizeDistribution(tiny=10, small=5, medium=3, large=2, xlarge=0)
        
        original = BlockSizeAnalysis(
            total_blocks=20,
            traced_count=0,
            untraced_count=20,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=0.0,
            untraced_avg=5.0,
        )
        
        adjusted = create_adjusted_analysis(original, [], overhead=3)
        
        # Should return empty traced distribution
        assert adjusted.traced_count == 0
        assert adjusted.traced_avg == 0.0
        assert adjusted.traced_dist.total() == 0
    
    def test_create_adjusted_analysis_custom_overhead(self):
        """Test with different overhead values."""
        traced_dist = SizeDistribution(tiny=0, small=0, medium=10, large=0, xlarge=0)
        untraced_dist = SizeDistribution(tiny=20, small=0, medium=0, large=0, xlarge=0)
        
        original = BlockSizeAnalysis(
            total_blocks=30,
            traced_count=10,
            untraced_count=20,
            traced_dist=traced_dist,
            untraced_dist=untraced_dist,
            traced_avg=10.0,
            untraced_avg=2.0,
        )
        
        traced_blocks_data = [{'num_instructions': 10}] * 10
        
        # Test with overhead=5
        adjusted_5 = create_adjusted_analysis(original, traced_blocks_data, overhead=5)
        assert adjusted_5.traced_avg == pytest.approx(5.0)
        
        # Test with overhead=7
        adjusted_7 = create_adjusted_analysis(original, traced_blocks_data, overhead=7)
        assert adjusted_7.traced_avg == pytest.approx(3.0)
        
        # Test with overhead=10 (should clamp to minimum 1)
        adjusted_10 = create_adjusted_analysis(original, traced_blocks_data, overhead=10)
        assert adjusted_10.traced_avg == pytest.approx(1.0)

