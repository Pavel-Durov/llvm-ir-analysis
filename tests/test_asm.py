import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.asm_parser import ASMParser
import pytest


class ASMTestCase:
    def __init__(self, asm: str, count: int):
        self.asm = asm
        self.count = count


# Test case 1: Simple basic block with common instructions
SimpleBlock = ASMTestCase(
    asm="""# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %rbp, -16
	movq	%rsi, %r14
	movl	%edi, %ebp
	movl	$1000000, %edi
	callq	malloc
	movq	shadowstack_head@GOTTPOFF(%rip), %rcx
	movq	%rax, %fs:(%rcx)
	movq	shadowstack_0@GOTTPOFF(%rip), %rcx
	movq	%rax, %fs:(%rcx)
	callq	lua_newstate.specialized.1
	testq	%rax, %rax
	je	.LBB0_1
    """,
    # Count only actual instructions, not .cfi_ directives or comments
    # pushq (3x) + movq (5x) + movl (2x) + callq (2x) + testq + je = 14
    count=14,
)

# Test case 2: Block with mixed instructions and directives
BlockWithDirectives = ASMTestCase(
    asm="""# %bb.4:
	movq	%rax, %rbx
	movq	24(%rax), %rax
	movq	$panic, 256(%rax)
	movq	%rbx, 1408(%rax)
	movq	$warnfoff, 1400(%rax)
	movq	%rbx, %rdi
	xorl	%esi, %esi
	xorl	%eax, %eax
	callq	lua_gc
	movl	$pmain, %esi
	movq	%rbx, %rdi
	xorl	%edx, %edx
	callq	lua_pushcclosure
    """,
    # movq (7x) + xorl (3x) + callq (2x) + movl (1x) = 13
    count=13,
)

# Test case 3: Block with conditional jumps and comparisons
BlockWithJumps = ASMTestCase(
    asm="""# %bb.2:
	movq	stderr(%rip), %rdi
	movl	$.L.str.1, %esi
	xorl	%eax, %eax
	callq	fprintf
	movq	stderr(%rip), %rdi
	callq	fflush
	testq	%rdx, %rdx
	je	.LBB0_3
	cmpb	$1, %al
	sete	%cl
    """,
    # movq (2x) + movl + xorl + callq (2x) + testq + je + cmpb + sete = 10
    count=10,
)

# Test case 4: Block with arithmetic and bitwise operations
ArithmeticBlock = ASMTestCase(
    asm="""# %bb.7:
	movl	%eax, %ebp
	movq	16(%rbx), %rax
	movzbl	-8(%rax), %eax
	cmpb	$1, %al
	sete	%cl
	testb	$15, %al
	sete	%r14b
	orb	%cl, %r14b
	addq	$16, 16(%rbx)
	leaq	16(%rax), %rcx
    """,
    # movl + movq + movzbl + cmpb + sete (2x) + testb + orb + addq + leaq = 10
    count=10,
)

# Test case 5: Block ending with return
ReturnBlock = ASMTestCase(
    asm=""".LBB0_5:
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%rbp
	.cfi_def_cfa_offset 8
	retq
    """,
    # popq (3x) + retq = 4
    count=4,
)

# Test case 6: Block with memory operations and immediate values
MemoryOpsBlock = ASMTestCase(
    asm="""# %bb.10:
	movslq	%ebp, %rax
	movq	16(%rbx), %rcx
	movq	%rax, (%rcx)
	movb	$3, 8(%rcx)
	movq	16(%rbx), %rax
	leaq	16(%rax), %rcx
	movq	%rcx, 16(%rbx)
	movq	%r14, 16(%rax)
	movb	$2, 24(%rax)
	addq	$16, 16(%rbx)
    """,
    # movslq + movq (5x) + movb (2x) + leaq + addq = 10
    count=10,
)


@pytest.mark.parametrize("test_case", [
    SimpleBlock,
    BlockWithDirectives,
    BlockWithJumps,
    ArithmeticBlock,
    ReturnBlock,
    MemoryOpsBlock,
])
def test_asm_block_counts_instructions(test_case: ASMTestCase):
    """Test that ASM parser correctly counts instructions in various blocks."""
    parser = ASMParser()
    blk = parser._parse_basic_block(test_case.asm.splitlines())
    assert blk.instructions == test_case.count
    assert len(blk.instruction_lines) == test_case.count


def test_asm_filters_directives():
    """Test that ASM parser filters out .cfi_ and other directives."""
    lines = [
        "# %bb.0:",
        "	pushq	%rbp",
        "	.cfi_def_cfa_offset 16",
        "	.cfi_offset %rbp, -16",
        "	movq	%rsp, %rbp",
        "	.cfi_def_cfa_register %rbp",
        "	retq",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    # Only pushq, movq, retq should be counted
    assert blk.instructions == 3
    assert ".cfi_" not in "".join(blk.instruction_lines)


def test_asm_filters_comments_and_labels():
    """Test that ASM parser filters comments and standalone labels."""
    lines = [
        "# %bb.1:",
        "	# This is a comment",
        "	movq	%rax, %rbx",
        ".LBB0_2:                                # Label with comment",
        "	callq	some_function",
        "	# Another comment",
        "	retq",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    # Only movq, callq, retq should be counted
    assert blk.instructions == 3


def test_asm_empty_block():
    """Test that ASM parser handles empty blocks correctly."""
    lines = [
        "# %bb.0:",
        "	.cfi_startproc",
        "	.cfi_endproc",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    assert blk.instructions == 0
    assert len(blk.instruction_lines) == 0


def test_asm_yk_trace_basicblock_no_calls():
    """Test block with no __yk_trace_basicblock calls."""
    lines = [
        "# %bb.0:",
        "	movq	%rax, %rbx",
        "	addq	$16, %rsp",
        "	retq",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    assert blk.instructions == 3
    assert blk.yk_trace_bb_calls == 0


def test_asm_yk_trace_basicblock_single_call():
    """Test block with one __yk_trace_basicblock call."""
    lines = [
        "# %bb.1:",
        "	movl	$135, %edi",
        "	movl	$0, %esi",
        "	callq	__yk_trace_basicblock",
        "	movq	%rax, %rbx",
        "	retq",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    assert blk.instructions == 5
    assert blk.yk_trace_bb_calls == 1


def test_asm_yk_trace_basicblock_multiple_calls():
    """Test block with multiple __yk_trace_basicblock calls."""
    lines = [
        "# %bb.2:",
        "	movl	$135, %edi",
        "	movl	$0, %esi",
        "	callq	__yk_trace_basicblock",
        "	movq	%rax, %rbx",
        "	callq	__yk_trace_basicblock",
        "	addq	$16, %rsp",
        "	retq",
    ]
    parser = ASMParser()
    blk = parser._parse_basic_block(lines)
    assert blk.instructions == 7
    assert blk.yk_trace_bb_calls == 2


def test_asm_summary_report_yk_trace_stats():
    """Test that summary report includes __yk_trace_basicblock statistics."""
    import tempfile
    from pathlib import Path
    
    # Create a temporary ASM file with functions containing __yk_trace_basicblock calls
    asm_content = """	.text
	# -- Begin function test_func1
	.globl	test_func1
test_func1:
# %bb.0:
	movl	$135, %edi
	movl	$0, %esi
	callq	__yk_trace_basicblock
	movq	%rax, %rbx
	retq
	# -- End function

	# -- Begin function test_func2
	.globl	test_func2
test_func2:
# %bb.0:
	pushq	%rbp
	movq	%rsp, %rbp
	retq
# %bb.1:
	movl	$136, %edi
	movl	$1, %esi
	callq	__yk_trace_basicblock
	popq	%rbp
	retq
	# -- End function
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.s', delete=False) as f:
        f.write(asm_content)
        temp_path = f.name

    try:
        parser = ASMParser()
        parser.parse(temp_path)
        report = parser.create_summary_report()

        # Check basic stats
        assert report.num_functions == 2
        assert report.num_basic_blocks == 3

        # Check __yk_trace_basicblock stats
        assert report.yk_trace_stats is not None
        assert report.yk_trace_stats.num_blocks == 2
        assert report.yk_trace_stats.total_calls == 2
        assert report.yk_trace_stats.num_instructions > 0
        assert report.yk_trace_stats.avg_instr_per_call > 0
    finally:
        Path(temp_path).unlink()

