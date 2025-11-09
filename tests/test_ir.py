import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.ir_parser import IRParser
import pytest


class IRBlockTestCase:
    """Test case for individual IR basic blocks."""
    def __init__(self, ir: str, count: int, label: str = ""):
        self.ir = ir
        self.count = count
        self.label = label


class IRFunctionTestCase:
    """Test case for complete IR functions."""
    def __init__(self, ir: str, num_functions: int, function_checks: dict):
        self.ir = ir
        self.num_functions = num_functions
        self.function_checks = function_checks


# Block-level test cases
SimpleBlockFourInstructions = IRBlockTestCase(
    ir="""11:                                               ; preds = %3
  %12 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 7
  %13 = load ptr, ptr %12, align 8, !tbaa !10
  %14 = getelementptr inbounds %struct.global_State, ptr %13, i64 0, i32 8
  br label %15""",
    count=4,
    label="11",
)

BlockWithSwitch = IRBlockTestCase(
    ir="""15:                                               ; preds = %11, %3
  %16 = phi ptr [ %14, %11 ], [ %7, %3 ]
  %17 = getelementptr inbounds %struct.TValue, ptr %16, i64 0, i32 1
  %18 = load i8, ptr %17, align 8, !tbaa !23
  %19 = zext i8 %18 to i32
  %20 = and i32 %19, 15
  switch i32 %20, label %66 [
    i32 4, label %40
    i32 3, label %21
  ]""",
    count=6,
    label="15",
)

UnlabelledEntryBlock = IRBlockTestCase(
    ir="""  ret i32 200""",
    count=1,
    label="",
)

EntryBlockWithLoad = IRBlockTestCase(
    ir="""entry:
  %2 = load double, ptr %0, align 8
  ret double %2""",
    count=2,
    label="entry",
)

# Function-level test cases
SingleBlockFunctionNoLabel = IRFunctionTestCase(
    ir="""define dso_local i32 @simple_return(ptr nocapture noundef readnone %0) local_unnamed_addr #11 {
  ret i32 200
}

define dso_local double @another_function(ptr noundef %0) #0 {
entry:
  %2 = load double, ptr %0, align 8
  ret double %2
}""",
    num_functions=2,
    function_checks={
        'simple_return': {'blocks': 1, 'instructions': 1},
        'another_function': {'blocks': 1, 'instructions': 2},
    },
)

MultiBlockFunction = IRFunctionTestCase(
    ir="""define dso_local i32 @with_branches(i32 %0) {
entry:
  %2 = icmp sgt i32 %0, 0
  br i1 %2, label %if.then, label %if.else

if.then:
  %3 = add i32 %0, 1
  ret i32 %3

if.else:
  %4 = sub i32 %0, 1
  ret i32 %4
}""",
    num_functions=1,
    function_checks={
        'with_branches': {'blocks': 3, 'instructions': 6},
    },
)


@pytest.mark.parametrize("test_case", [
    SimpleBlockFourInstructions,
    BlockWithSwitch,
    UnlabelledEntryBlock,
    EntryBlockWithLoad,
])
def test_ir_block_counts_instructions(test_case: IRBlockTestCase):
    """Test that individual IR basic blocks are parsed correctly."""
    parser = IRParser()
    blk = parser._parse_basic_block(test_case.ir.splitlines(), in_mir=False)
    assert blk.instructions == test_case.count
    assert len(blk.instruction_lines) == test_case.count
    if test_case.label:
        assert blk.block.startswith(test_case.label)


@pytest.mark.parametrize("test_case", [
    SingleBlockFunctionNoLabel,
    MultiBlockFunction,
])
def test_ir_function_parsing(test_case: IRFunctionTestCase):
    """Test that complete IR functions with various structures are parsed correctly."""
    parser = IRParser()
    functions = parser.parse_from_string(test_case.ir)

    # Check number of functions parsed
    assert len(functions) == test_case.num_functions

    # Check individual function properties
    for func_name, expected in test_case.function_checks.items():
        assert func_name in functions, f"Function '{func_name}' not found in parsed functions"
        fn = functions[func_name]
        assert fn.blocks == expected['blocks'], \
            f"{func_name}: expected {expected['blocks']} blocks, got {fn.blocks}"
        assert fn.total_instructions == expected['instructions'], \
            f"{func_name}: expected {expected['instructions']} instructions, got {fn.total_instructions}"


def test_ir_yk_trace_basicblock_no_calls():
    """Test IR block with no __yk_trace_basicblock calls."""
    ir_lines = """entry:
  %2 = load double, ptr %0, align 8
  %3 = add double %2, 1.0
  ret double %3"""

    parser = IRParser()
    blk = parser._parse_basic_block(ir_lines.splitlines(), in_mir=False)
    assert blk.instructions == 3
    assert blk.yk_trace_bb_calls == 0


def test_ir_yk_trace_basicblock_single_call():
    """Test IR block with one __yk_trace_basicblock call."""
    ir_lines = """entry:
  call void @__yk_trace_basicblock(i32 135, i32 0)
  %2 = load double, ptr %0, align 8
  ret double %2"""

    parser = IRParser()
    blk = parser._parse_basic_block(ir_lines.splitlines(), in_mir=False)
    assert blk.instructions == 3
    assert blk.yk_trace_bb_calls == 1


def test_ir_yk_trace_basicblock_multiple_calls():
    """Test IR block with multiple __yk_trace_basicblock calls."""
    ir_lines = """entry:
  call void @__yk_trace_basicblock(i32 135, i32 0)
  %2 = load double, ptr %0, align 8
  call void @__yk_trace_basicblock(i32 135, i32 1)
  ret double %2"""

    parser = IRParser()
    blk = parser._parse_basic_block(ir_lines.splitlines(), in_mir=False)
    assert blk.instructions == 4
    assert blk.yk_trace_bb_calls == 2


def test_ir_summary_report_yk_trace_stats():
    """Test that summary report includes __yk_trace_basicblock statistics."""
    ir_content = """define dso_local i32 @test_func1(ptr %0) {
entry:
  call void @__yk_trace_basicblock(i32 135, i32 0)
  %2 = load i32, ptr %0, align 4
  ret i32 %2
}

define dso_local double @test_func2(ptr %0) {
entry:
  %2 = load double, ptr %0, align 8
  ret double %2

bb1:
  call void @__yk_trace_basicblock(i32 136, i32 1)
  %3 = fadd double %2, 1.0
  ret double %3
}

declare void @__yk_trace_basicblock(i32, i32)
"""

    parser = IRParser()
    parser.parse_from_string(ir_content)
    report = parser.create_summary_report()

    # Check basic stats
    assert report.num_functions == 2
    assert report.num_basic_blocks == 3

    # Check __yk_trace_basicblock stats
    assert report.num_blocks_with_yk_trace == 2
    assert report.total_yk_trace_calls == 2
    assert report.num_instructions_in_yk_trace_blocks > 0
    assert report.avg_instr_per_yk_trace_call > 0
