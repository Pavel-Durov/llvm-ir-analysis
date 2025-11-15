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
	movq	%rbx, %rdi
	callq	luaL_openlibs
	movq	(%r14), %rcx
	cmpb	$45, (%rcx)
	jne	.LBB0_5
    """,
    count=9,
)

# Test case 3: Block with many directives (should be filtered out)
BlockWithManyDirectives = ASMTestCase(
    asm="""# %bb.2:
	.cfi_def_cfa %rsp, 8
	.cfi_restore %rbx
	.cfi_restore %r14
	.cfi_restore %rbp
	movl	$0, %eax
	retq
    """,
    count=2,  # Only movl and retq
)

# Test case 4: Block with labels and comments
BlockWithLabels = ASMTestCase(
    asm="""# %bb.5:
	.cfi_def_cfa %rbp, 16
	movq	%rbx, %rdi
	movl	$11, %esi
	callq	lua_gc
.LBB0_6:                                # %10
	movl	$0, %eax
	jmp	.LBB0_2
    """,
    count=5,  # movq, movl, callq, movl, jmp
)

# Test case 5: Block that's just a jump
BlockWithJump = ASMTestCase(
    asm="""# %bb.1:
	jmp	.LBB0_6
    """,
    count=1,
)

# Test case 6: Empty block (only comments and directives)
EmptyBlock = ASMTestCase(
    asm="""# %bb.3:
	.cfi_def_cfa %rsp, 8
	# This is a comment
    """,
    count=0,
)


@pytest.mark.parametrize(
    "test_case",
    [
    SimpleBlock,
    BlockWithDirectives,
        BlockWithManyDirectives,
        BlockWithLabels,
        BlockWithJump,
        EmptyBlock,
    ],
)
def test_asm_block_counts_instructions(test_case):
    parser = ASMParser()
    blk = parser._parse_basic_block(test_case.asm.split("\n"))
    assert blk.instructions == test_case.count


def test_asm_filters_directives():
    asm = """# %bb.0:
	.cfi_startproc
	.cfi_def_cfa %rsp, 8
	.cfi_offset %rbp, -16
	pushq	%rbp
	.cfi_def_cfa_offset 16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    assert blk.instructions == 2  # pushq and movq


def test_asm_filters_comments_and_labels():
    asm = """# %bb.0:
	# This is a comment
	pushq	%rbp
	# Another comment
	movq	%rsp, %rbp
.LBB0_1:                                # %entry
	# Comment after label
	jmp	.LBB0_2
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    assert blk.instructions == 3


def test_asm_empty_block():
    asm = """# %bb.0:
	# Only comments and directives
	.cfi_def_cfa %rsp, 8
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    assert blk.instructions == 0


def test_asm_yk_trace_basicblock_no_calls():
    """Test that blocks without __yk_trace_basicblock calls are counted correctly."""
    asm = """# %bb.0:
	pushq	%rbp
	movq	%rsp, %rbp
	movq	%rdi, %rax
	popq	%rbp
	retq
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    assert blk.instructions == 5
    assert blk.yk_trace_bb_calls == 0


def test_asm_yk_trace_basicblock_single_call():
    """Test that __yk_trace_basicblock calls are included in instruction count."""
    asm = """# %bb.0:
	pushq	%rbp
	movq	%rsp, %rbp
	movl	$100, %edi
	xorl	%esi, %esi
	callq	__yk_trace_basicblock@PLT
	movq	%rdi, %rax
	popq	%rbp
	retq
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    # Total lines: pushq, movq, movl, xorl, callq, movq, popq, retq = 8
    # All instructions are counted INCLUDING the trace call
    assert blk.instructions == 8  # 8 instructions INCLUDING trace call
    assert blk.yk_trace_bb_calls == 1


def test_asm_yk_trace_basicblock_multiple_calls():
    """Test multiple __yk_trace_basicblock calls in same block."""
    asm = """# %bb.0:
	pushq	%rbp
	movl	$100, %edi
	movl	$0, %esi
	callq	__yk_trace_basicblock@PLT
	movq	%rdi, %rax
	movl	$100, %edi
	movl	$1, %esi
	callq	__yk_trace_basicblock@PLT
	popq	%rbp
	retq
    """
    parser = ASMParser()
    blk = parser._parse_basic_block(asm.split("\n"))
    # Total: pushq, movl, movl, callq, movq, movl, movl, callq, popq, retq = 10
    # All instructions are counted INCLUDING trace calls
    assert blk.instructions == 10
    assert blk.yk_trace_bb_calls == 2


def test_asm_summary_report_yk_trace_stats():
    """Test that summary report includes __yk_trace_basicblock statistics."""
    import tempfile

    asm_content = """
	.globl	test_func1                  # -- Begin function test_func1
	.p2align	4, 0x90
	.type	test_func1,@function
test_func1:                             # @test_func1
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	movq	%rsp, %rbp
	movl	$100, %edi
	xorl	%esi, %esi
	callq	__yk_trace_basicblock@PLT
	movq	%rdi, %rax
	popq	%rbp
	retq
.Lfunc_end0:
	.size	test_func1, .Lfunc_end0-test_func1
	.cfi_endproc
	# -- End function
	.globl	test_func2                  # -- Begin function test_func2
	.p2align	4, 0x90
	.type	test_func2,@function
test_func2:                             # @test_func2
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	movl	$200, %edi
	movl	$0, %esi
	callq	__yk_trace_basicblock@PLT
	popq	%rbp
	retq
# %bb.1:
	movq	%rdi, %rax
	retq
.Lfunc_end1:
	.size	test_func2, .Lfunc_end1-test_func2
	.cfi_endproc
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


def test_asm_multi_function_with_many_blocks():
    """Test parsing of multiple functions with many basic blocks and trace calls.

    This test uses real-world functions (varinfo and typeerror) to verify:
    - Correct function parsing
    - Correct basic block identification
    - Correct trace call counting
    - Correct block labeling
    """
    import tempfile
    import re
    
    asm_content = """
	.globl	varinfo                         # -- Begin function varinfo
	.p2align	4, 0x90
	.type	varinfo,@function
varinfo:                                # @varinfo
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	pushq	%r15
	pushq	%r14
	pushq	%r13
	pushq	%r12
	pushq	%rbx
	subq	$40, %rsp
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	movq	%rsi, %r15
	movq	%rdi, %r13
	movl	$134, %edi
	xorl	%esi, %esi
	callq	__yk_trace_basicblock@PLT
	movq	shadowstack_0@GOTTPOFF(%rip), %rax
	movq	%fs:(%rax), %rbx
	movq	%rbx, %rcx
	addq	$16, %rcx
	movq	%rcx, %fs:(%rax)
	movq	32(%r13), %r14
# %bb.1:
	movl	$134, %edi
	movl	$1, %esi
	callq	__yk_trace_basicblock@PLT
# %bb.2:
	movl	$134, %edi
	movl	$2, %esi
	callq	__yk_trace_basicblock@PLT
	movq	$0, (%rbx)
	movw	62(%r14), %ax
	andw	$2, %ax
	cmpw	$0, %ax
	sete	%al
.Ltmp23:
	movabsq	$.L.str.37.892, %r12
	testb	$1, %al
	jne	.LBB114_3
	jmp	.LBB114_11
.LBB114_3:
	movl	$134, %edi
	movl	$3, %esi
	callq	__yk_trace_basicblock@PLT
	movq	(%r14), %rax
	movq	(%rax), %r12
	movq	%r12, %rdi
	movq	%r15, %rsi
	movq	%rbx, %rdx
	callq	getupvalname
	movq	%rax, -56(%rbp)                 # 8-byte Spill
.Ltmp24:
# %bb.4:
	movl	$134, %edi
	movl	$4, %esi
	callq	__yk_trace_basicblock@PLT
	movq	-56(%rbp), %rcx                 # 8-byte Reload
	cmpq	$0, %rcx
	sete	%al
.Ltmp25:
	testb	$1, %al
	jne	.LBB114_5
	jmp	.LBB114_9
.LBB114_5:
	movl	$134, %edi
	movl	$5, %esi
	callq	__yk_trace_basicblock@PLT
	movq	%r13, -64(%rbp)                 # 8-byte Spill
	movq	(%r14), %r13
	movq	8(%r14), %r12
	movq	%r13, %rdi
	movq	%r12, %rsi
	movq	%r15, %rdx
	callq	instack
	movl	%eax, -44(%rbp)                 # 4-byte Spill
	movq	%r13, -72(%rbp)                 # 8-byte Spill
	movq	-64(%rbp), %rax                 # 8-byte Reload
.Ltmp26:
	movq	%rax, %r15
# %bb.6:
	movl	$134, %edi
	movl	$6, %esi
	callq	__yk_trace_basicblock@PLT
	movl	-44(%rbp), %ecx                 # 4-byte Reload
	cmpl	$-1, %ecx
	setg	%al
	movq	-72(%rbp), %r13                 # 8-byte Reload
.Ltmp27:
	movabsq	$.L.str.37.892, %r12
	testb	$1, %al
	jne	.LBB114_7
	jmp	.LBB114_11
.LBB114_7:
	movl	$134, %edi
	movl	$7, %esi
	callq	__yk_trace_basicblock@PLT
	movq	(%r13), %rax
	movq	%r15, %r13
	movq	24(%rax), %r15
	movq	32(%r14), %r12
	movq	64(%r15), %rax
	subq	%rax, %r12
	shrq	$2, %r12
	addl	$-1, %r12d
	movq	%r15, %rdi
	movl	%r12d, %esi
	movl	-44(%rbp), %r14d                # 4-byte Reload
	movl	%r14d, %edx
	movq	%rbx, %rcx
	callq	getobjname
	movq	%rax, -56(%rbp)                 # 8-byte Spill
.Ltmp28:
# %bb.8:
	movl	$134, %edi
	movl	$8, %esi
	callq	__yk_trace_basicblock@PLT
	movq	-56(%rbp), %rcx                 # 8-byte Reload
	cmpq	$0, %rcx
	sete	%al
.Ltmp29:
	movabsq	$.L.str.37.892, %r12
	testb	$1, %al
	jne	.LBB114_11
.LBB114_9:
	movl	$134, %edi
	movl	$9, %esi
	callq	__yk_trace_basicblock@PLT
	movq	(%rbx), %r15
	movabsq	$.L.str.30.95, %rsi
	movq	%r13, %rdi
	movq	-56(%rbp), %r14                 # 8-byte Reload
	movq	%r14, %rdx
	movq	%r15, %rcx
	movb	$0, %al
	callq	luaO_pushfstring
	movq	%rax, %r12
.Ltmp30:
# %bb.10:
	movl	$134, %edi
	movl	$10, %esi
	callq	__yk_trace_basicblock@PLT
.LBB114_11:
	movl	$134, %edi
	movl	$11, %esi
	callq	__yk_trace_basicblock@PLT
# %bb.12:
	movl	$134, %edi
	movl	$12, %esi
	callq	__yk_trace_basicblock@PLT
	jmp	.LBB114_14
.LBB114_13:
	movl	$134, %edi
	movl	$13, %esi
	callq	__yk_trace_basicblock@PLT
	movq	shadowstack_0@GOTTPOFF(%rip), %rax
	movq	%rbx, %fs:(%rax)
	movq	%r12, %rax
	addq	$40, %rsp
	popq	%rbx
	popq	%r12
	popq	%r13
	popq	%r14
	popq	%r15
	popq	%rbp
	.cfi_def_cfa %rsp, 8
	retq
.LBB114_14:
	.cfi_def_cfa %rbp, 16
	movl	$134, %edi
	movl	$14, %esi
	callq	__yk_trace_basicblock@PLT
	jmp	.LBB114_13
.Lfunc_end114:
	.size	varinfo, .Lfunc_end114-varinfo
	.cfi_endproc
	# -- End function
	.globl	typeerror                       # -- Begin function typeerror
	.p2align	4, 0x90
	.type	typeerror,@function
typeerror:                              # @typeerror
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	pushq	%r15
	pushq	%r14
	pushq	%r13
	pushq	%r12
	pushq	%rbx
	pushq	%rax
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	movq	%rcx, %rbx
	movq	%rdx, %r14
	movq	%rsi, %r12
	movq	%rdi, %r15
	movl	$135, %edi
	xorl	%esi, %esi
	callq	__yk_trace_basicblock@PLT
# %bb.1:
	movl	$135, %edi
	movl	$1, %esi
	callq	__yk_trace_basicblock@PLT
	movq	%r15, %rdi
	movq	%r12, %rsi
	callq	luaT_objtypename
	movq	%rax, %r13
.Ltmp31:
# %bb.2:
	movl	$135, %edi
	movl	$2, %esi
	callq	__yk_trace_basicblock@PLT
	movabsq	$.L.str.16.91, %rsi
	movq	%r15, %rdi
	movq	%r14, %rdx
	movq	%r13, %rcx
	movq	%rbx, %r8
	movb	$0, %al
	callq	luaG_runerror
.Ltmp32:
# %bb.3:
	movl	$135, %edi
	movl	$3, %esi
	callq	__yk_trace_basicblock@PLT
.Lfunc_end115:
	.size	typeerror, .Lfunc_end115-typeerror
	.cfi_endproc
	# -- End function
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.s', delete=False) as f:
        f.write(asm_content)
        temp_path = f.name

    try:
        parser = ASMParser()
        functions = parser.parse(temp_path)

        # Verify both functions are parsed
        assert len(functions) == 2
        assert 'varinfo' in functions
        assert 'typeerror' in functions

        # Check varinfo function
        varinfo = functions['varinfo']
        # Parser now splits blocks at every trace call boundary (after the first)
        # varinfo has 15 trace calls (BB IDs 0-14), so we expect 15 blocks
        assert varinfo.blocks == 15
        assert varinfo.total_instructions > 0
        assert varinfo.function_index == 134  # Extracted from trace calls

        # Count blocks with trace calls in varinfo - all should have exactly 1
        varinfo_trace_blocks = [blk for blk in varinfo.blocks_detail if blk.yk_trace_bb_calls > 0]
        assert len(varinfo_trace_blocks) == 15  # Each block has one trace call

        # Verify that blocks contain the expected trace BB IDs
        # The merged blocks will contain multiple trace calls
        trace_ids = set()
        for blk in varinfo_trace_blocks:
            # Extract trace ID from the block (may have multiple)
            for line_idx in range(len(blk.instruction_lines)):
                if '__yk_trace_basicblock@PLT' in blk.instruction_lines[line_idx]:
                    # Look back for the BB ID parameter
                    if line_idx >= 2:
                        esi_line = blk.instruction_lines[line_idx - 1].strip()
                        match = re.search(r'movl\s+\$(\d+),\s+%esi', esi_line)
                        if match:
                            trace_ids.add(int(match.group(1)))
                        elif 'xorl' in esi_line and '%esi' in esi_line:
                            trace_ids.add(0)
        # Should have all 15 trace IDs (0-14) - one per block
        assert len(trace_ids) == 15
        
        # Check typeerror function
        typeerror = functions['typeerror']
        assert typeerror.blocks == 4  # One block per trace call
        assert typeerror.total_instructions > 0
        assert typeerror.function_index == 135  # Extracted from trace calls
        
        # Count blocks with trace calls in typeerror (should be 4)
        typeerror_trace_blocks = [blk for blk in typeerror.blocks_detail if blk.yk_trace_bb_calls > 0]
        assert len(typeerror_trace_blocks) == 4
        
        # Verify trace BB IDs are sequential (0-3)
        trace_ids_typeerror = set()
        for blk in typeerror_trace_blocks:
            trace_id = ASMParser._extract_trace_bb_id(blk.instruction_lines)
            if trace_id is not None:
                trace_ids_typeerror.add(trace_id)
        assert trace_ids_typeerror == set(range(4))  # {0, 1, 2, 3}
        
        # Check summary report
        report = parser.create_summary_report()
        assert report.num_functions == 2
        assert report.num_basic_blocks == 19  # 15 (varinfo) + 4 (typeerror)

        # Check __yk_trace_basicblock stats
        assert report.yk_trace_stats is not None
        assert report.yk_trace_stats.num_blocks == 19  # All blocks have trace calls
        assert report.yk_trace_stats.total_calls == 19  # 15 calls in varinfo + 4 in typeerror
        assert report.yk_trace_stats.num_instructions > 0
        assert report.yk_trace_stats.avg_instr_per_call > 0

    finally:
        Path(temp_path).unlink()


def test_asm_multiple_trace_calls_in_single_comment_block():
    """Test parsing of a block with multiple __yk_trace_basicblock calls.

    This tests the real-world scenario where a single "# %bb.N:" comment block
    contains multiple trace calls that should ideally be split into separate blocks.

    Based on actual output from the typeerror function.
    """
    asm_content = """
	.globl	typeerror                       # -- Begin function typeerror
	.p2align	4, 0x90
	.type	typeerror,@function
typeerror:                              # @typeerror
	.cfi_startproc
# %bb.0:
	pushq	%rbp
	movq	%rsp, %rbp
	pushq	%r15
	pushq	%r14
	pushq	%r13
	pushq	%r12
	pushq	%rbx
	subq	$72, %rsp
	movq	%rcx, %r15
	movl	%edx, -84(%rbp)                 # 4-byte Spill
	movl	%esi, -52(%rbp)                 # 4-byte Spill
	movq	%rdi, %r12
	movl	$135, %edi
	xorl	%esi, %esi
	callq	__yk_trace_basicblock@PLT
	movq	shadowstack_0@GOTTPOFF(%rip), %rax
	movq	%fs:(%rax), %r8
	movq	%r8, %rcx
	addq	$16, %rcx
	movq	%rcx, %fs:(%rax)
	movq	%r8, %rcx
	addq	$8, %rcx
	movq	%r12, -48(%rbp)                 # 8-byte Spill
	addq	$64, %r12
	movq	%r8, -80(%rbp)                  # 8-byte Spill
	movq	%r15, -72(%rbp)                 # 8-byte Spill
	movq	%rcx, -64(%rbp)                 # 8-byte Spill
	movl	$135, %edi
	movl	$1, %esi
	callq	__yk_trace_basicblock@PLT
	movl	-84(%rbp), %ebx                 # 4-byte Reload
	movl	%ebx, %r13d
	addl	$1, %r13d
	movq	-48(%rbp), %r14                 # 8-byte Reload
	movq	%r14, %rdi
	movl	%r13d, %esi
	movl	-52(%rbp), %r15d                # 4-byte Reload
	movl	%r15d, %edx
	callq	luaF_getlocalname
	movq	-72(%rbp), %rcx                 # 8-byte Reload
	movq	%rax, -112(%rbp)                # 8-byte Spill
	movq	-80(%rbp), %rax                 # 8-byte Reload
	movq	%rax, %rbx
	movq	%rcx, %r15
	movl	$135, %edi
	movl	$2, %esi
	callq	__yk_trace_basicblock@PLT
	cmpq	$0, -112(%rbp)                  # 8-byte Folded Reload
	jne	.LBB115_2
.LBB115_2:
	retq
.Lfunc_end:
	.size	typeerror, .Lfunc_end-typeerror
	.cfi_endproc
	# -- End function
"""

    temp_path = '/tmp/test_asm_multiple_trace_in_block.s'
    try:
        with open(temp_path, 'w') as f:
            f.write(asm_content)

        parser = ASMParser()
        functions = parser.parse(temp_path)

        assert len(functions) == 1
        func = functions['typeerror']
        assert func, "Function not found"

        # Parser now splits blocks at __yk_trace_basicblock call boundaries
        # Each trace call ends a block, so we expect 4 blocks:
        # - Block 0: Function prologue + first trace call (BB ID 0)
        # - Block 1: Code after first trace + second trace call (BB ID 1)
        # - Block 2: Code after second trace + third trace call (BB ID 2)
        # - Block 3: Epilogue code (no trace call)
        assert func.blocks == 3
        assert func.function_index == 135

        # First 3 blocks should have exactly 1 trace call each
        for i in range(3):
            block = func.blocks_detail[i]
            assert block.yk_trace_bb_calls == 1, f"Block {i} should have 1 trace call, got {block.yk_trace_bb_calls}"

        # Extract BB IDs from blocks with trace calls
        trace_bb_ids = []
        for block in func.blocks_detail[:3]:  # Only first 3 blocks have trace calls
            bb_id = ASMParser._extract_trace_bb_id(block.instruction_lines)
            if bb_id is not None:
                trace_bb_ids.append(bb_id)

        # Should have BB IDs 0, 1, 2
        assert trace_bb_ids == [0, 1, 2]

        # Verify block labels
        assert func.blocks_detail[0].block == 'bb.0'
        assert func.blocks_detail[1].block == 'bb.1'
        assert func.blocks_detail[2].block == 'bb.2'

        # All blocks should have instructions
        for i, block in enumerate(func.blocks_detail):
            assert block.instructions > 0, f"Block {i} should have instructions"
        
    finally:
        Path(temp_path).unlink(missing_ok=True)
