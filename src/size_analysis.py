"""Size distribution analysis for basic blocks."""

from dataclasses import dataclass
from pathlib import Path
import csv as csv_module
from parser import ASMParser, MIRParser


@dataclass
class SizeDistribution:
    """Represents size distribution across buckets."""
    tiny: int = 0  # 1-3 instructions
    small: int = 0  # 4-6 instructions
    medium: int = 0  # 7-10 instructions
    large: int = 0  # 11-20 instructions
    xlarge: int = 0  # 21+ instructions

    def total(self) -> int:
        """Return total count across all buckets."""
        return self.tiny + self.small + self.medium + self.large + self.xlarge

    def get_percentage(self, bucket_count: int) -> float:
        """Calculate percentage for a bucket count."""
        total = self.total()
        return (bucket_count / total * 100) if total > 0 else 0.0

    def items(self):
        """Return (label, count) pairs for iteration."""
        return [
            ('1-3', self.tiny),
            ('4-6', self.small),
            ('7-10', self.medium),
            ('11-20', self.large),
            ('21+', self.xlarge),
        ]


@dataclass
class BlockSizeAnalysis:
    """Analysis results for block size distribution."""
    total_blocks: int
    traced_count: int
    untraced_count: int
    traced_dist: SizeDistribution
    untraced_dist: SizeDistribution
    traced_avg: float
    untraced_avg: float

    @property
    def difference(self) -> float:
        """Calculate average difference."""
        return self.traced_avg - self.untraced_avg

    @property
    def ratio(self) -> float:
        """Calculate ratio of traced to untraced average."""
        return self.traced_avg / self.untraced_avg if self.untraced_avg > 0 else 0.0

    @property
    def traced_percentage(self) -> float:
        """Percentage of traced blocks."""
        return (self.traced_count / self.total_blocks * 100) if self.total_blocks > 0 else 0.0

    @property
    def untraced_percentage(self) -> float:
        """Percentage of untraced blocks."""
        return (self.untraced_count / self.total_blocks * 100) if self.total_blocks > 0 else 0.0


def categorize_by_size(num_instructions: int) -> str:
    """Categorize a block by its instruction count."""
    if num_instructions <= 3:
        return 'tiny'
    elif num_instructions <= 6:
        return 'small'
    elif num_instructions <= 10:
        return 'medium'
    elif num_instructions <= 20:
        return 'large'
    else:
        return 'xlarge'


def create_distribution(blocks: list[dict]) -> SizeDistribution:
    """Create size distribution from list of blocks."""
    dist = SizeDistribution()

    for block in blocks:
        category = categorize_by_size(block['num_instructions'])
        if category == 'tiny':
            dist.tiny += 1
        elif category == 'small':
            dist.small += 1
        elif category == 'medium':
            dist.medium += 1
        elif category == 'large':
            dist.large += 1
        elif category == 'xlarge':
            dist.xlarge += 1

    return dist


def analyze_csv_blocks(csv_file: Path) -> BlockSizeAnalysis:
    """
    Analyse block size distribution from CSV file.

    Args:
        csv_file: Path to CSV file with columns: function_name, basicblock_id,
                 has_tracing_call, number_of_instructions, instructions

    Returns:
        BlockSizeAnalysis with distribution statistics

    Raises:
        ValueError: If CSV format is invalid
    """
    # Deduplicate by (function_name, basicblock_id)
    blocks_dict = {}

    with open(csv_file, 'r') as f:
        reader = csv_module.reader(f)
        header = next(reader)

        # Validate CSV format
        if len(header) < 5 or 'has_tracing_call' not in header:
            raise ValueError(
                "CSV file must have 'has_tracing_call' column. "
                "Expected format: function_name,basicblock_id,has_tracing_call,number_of_instructions,instructions"
            )

        for row in reader:
            if len(row) < 5:
                continue

            function_name = row[0]
            basicblock_id = row[1]
            has_tracing = row[2].lower() == 'true'
            num_instructions = int(row[3])

            key = (function_name, basicblock_id)

            # Prefer traced version if duplicate
            if key in blocks_dict:
                if has_tracing and not blocks_dict[key]['has_tracing']:
                    pass  # Will replace
                elif not has_tracing and blocks_dict[key]['has_tracing']:
                    continue  # Keep existing traced version

            blocks_dict[key] = {
                'has_tracing': has_tracing,
                'num_instructions': num_instructions,
            }

    # Separate into traced and untraced
    traced = [b for b in blocks_dict.values() if b['has_tracing']]
    untraced = [b for b in blocks_dict.values() if not b['has_tracing']]

    # Create distributions
    traced_dist = create_distribution(traced)
    untraced_dist = create_distribution(untraced)

    # Calculate averages
    traced_count = len(traced)
    untraced_count = len(untraced)

    traced_avg = (sum(b['num_instructions'] for b in traced) / traced_count
                  if traced_count > 0 else 0.0)
    untraced_avg = (sum(b['num_instructions'] for b in untraced) / untraced_count
                    if untraced_count > 0 else 0.0)

    return BlockSizeAnalysis(
        total_blocks=len(blocks_dict),
        traced_count=traced_count,
        untraced_count=untraced_count,
        traced_dist=traced_dist,
        untraced_dist=untraced_dist,
        traced_avg=traced_avg,
        untraced_avg=untraced_avg,
    )


def analyze_asm_blocks(asm_file: Path) -> tuple[BlockSizeAnalysis, dict[str, int], list[dict]]:
    """
    Analyse block size distribution from ASM file.

    Args:
        asm_file: Path to ASM file

    Returns:
        Tuple of (BlockSizeAnalysis, dict of function_name -> traced_block_count, list of traced block data)
    """
    # Parse ASM file
    parser = ASMParser()
    parser.parse(str(asm_file), skip_prefixes=[])

    functions = parser.get_functions()

    # Collect all blocks
    traced_blocks = []
    untraced_blocks = []
    traced_funcs = {}

    for func_name, func in functions.items():
        for block in func.blocks_detail:
            # Check if block has tracing call
            has_trace = any('__yk_trace_basicblock' in inst for inst in block.instruction_lines)
            num_inst = len(block.instruction_lines)

            block_info = {
                'function': func_name,
                'block_id': block.block,
                'num_instructions': num_inst
            }

            if has_trace:
                traced_blocks.append(block_info)
                traced_funcs[func_name] = traced_funcs.get(func_name, 0) + 1
            else:
                untraced_blocks.append(block_info)

    # Create distributions
    traced_dist = create_distribution(traced_blocks)
    untraced_dist = create_distribution(untraced_blocks)

    # Calculate averages
    traced_count = len(traced_blocks)
    untraced_count = len(untraced_blocks)

    traced_avg = (sum(b['num_instructions'] for b in traced_blocks) / traced_count
                  if traced_count > 0 else 0.0)
    untraced_avg = (sum(b['num_instructions'] for b in untraced_blocks) / untraced_count
                    if untraced_count > 0 else 0.0)

    analysis = BlockSizeAnalysis(
        total_blocks=traced_count + untraced_count,
        traced_count=traced_count,
        untraced_count=untraced_count,
        traced_dist=traced_dist,
        untraced_dist=untraced_dist,
        traced_avg=traced_avg,
        untraced_avg=untraced_avg,
    )

    return analysis, traced_funcs, traced_blocks


def analyze_mir_blocks(mir_file: Path) -> tuple[BlockSizeAnalysis, dict[str, int], list[dict]]:
    """
    Analyse block size distribution from MIR file.
    
    Args:
        mir_file: Path to MIR file
    
    Returns:
        Tuple of (BlockSizeAnalysis, dict of function_name -> traced_block_count, list of traced block data)
    """
    # Parse MIR file
    parser = MIRParser()
    parser.parse(str(mir_file), skip_patterns=[], skip_prefixes=[])
    
    functions = parser.get_functions()
    
    # Collect all blocks
    traced_blocks = []
    untraced_blocks = []
    traced_funcs = {}
    
    for func_name, func in functions.items():
        for block in func.blocks_detail:
            # Check if block has tracing call
            has_trace = any('__yk_trace_basicblock' in inst for inst in block.instruction_lines)
            num_inst = len(block.instruction_lines)
            
            block_info = {
                'function': func_name,
                'block_id': block.block,
                'num_instructions': num_inst
            }
            
            if has_trace:
                traced_blocks.append(block_info)
                traced_funcs[func_name] = traced_funcs.get(func_name, 0) + 1
            else:
                untraced_blocks.append(block_info)
    
    # Create distributions
    traced_dist = create_distribution(traced_blocks)
    untraced_dist = create_distribution(untraced_blocks)
    
    # Calculate averages
    traced_count = len(traced_blocks)
    untraced_count = len(untraced_blocks)
    
    traced_avg = (sum(b['num_instructions'] for b in traced_blocks) / traced_count 
                  if traced_count > 0 else 0.0)
    untraced_avg = (sum(b['num_instructions'] for b in untraced_blocks) / untraced_count 
                    if untraced_count > 0 else 0.0)
    
    analysis = BlockSizeAnalysis(
        total_blocks=traced_count + untraced_count,
        traced_count=traced_count,
        untraced_count=untraced_count,
        traced_dist=traced_dist,
        untraced_dist=untraced_dist,
        traced_avg=traced_avg,
        untraced_avg=untraced_avg,
    )
    
    return analysis, traced_funcs, traced_blocks


def create_adjusted_analysis(original: BlockSizeAnalysis, traced_blocks_data: list[dict], 
                             overhead: int = 3) -> BlockSizeAnalysis:
    """
    Create adjusted analysis by subtracting tracing overhead from traced blocks.
    
    Args:
        original: Original BlockSizeAnalysis
        traced_blocks_data: List of traced block dictionaries with 'num_instructions'
        overhead: Number of instructions to subtract (default: 3)
    
    Returns:
        New BlockSizeAnalysis with adjusted traced block sizes
    """
    # Adjust traced block sizes
    adjusted_blocks = []
    for block in traced_blocks_data:
        adjusted_size = max(1, block['num_instructions'] - overhead)  # Minimum 1 instruction
        adjusted_blocks.append({
            **block,
            'num_instructions': adjusted_size
        })
    
    # Recalculate distribution and average for adjusted traced blocks
    adjusted_traced_dist = create_distribution(adjusted_blocks)
    adjusted_traced_avg = (sum(b['num_instructions'] for b in adjusted_blocks) / len(adjusted_blocks)
                          if adjusted_blocks else 0.0)
    
    # Return new analysis with adjusted traced data, keeping untraced data the same
    return BlockSizeAnalysis(
        total_blocks=original.total_blocks,
        traced_count=original.traced_count,
        untraced_count=original.untraced_count,
        traced_dist=adjusted_traced_dist,
        untraced_dist=original.untraced_dist,  # Unchanged
        traced_avg=adjusted_traced_avg,
        untraced_avg=original.untraced_avg,  # Unchanged
    )

