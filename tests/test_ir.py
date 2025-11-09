import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from parser.ir_parser import IRParser
import pytest

def test_ir_block_counts_four_instructions():
    lines = [
        "11:                                               ; preds = %3",
        "  %12 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 7",
        "  %13 = load ptr, ptr %12, align 8, !tbaa !10",
        "  %14 = getelementptr inbounds %struct.global_State, ptr %13, i64 0, i32 8",
        "  br label %15",
    ]
    parser = IRParser()
    blk = parser._parse_basic_block(lines, in_mir=False)
    assert blk.block.startswith("11")
    assert blk.instructions == 4


def test_ir_block_with_switch():
    """Test IR block with switch instruction."""
    ir = """15:                                               ; preds = %11, %3
        %16 = phi ptr [ %14, %11 ], [ %7, %3 ]
        %17 = getelementptr inbounds %struct.TValue, ptr %16, i64 0, i32 1
        %18 = load i8, ptr %17, align 8, !tbaa !23
        %19 = zext i8 %18 to i32
        %20 = and i32 %19, 15
        switch i32 %20, label %66 [
            i32 4, label %40
            i32 3, label %21
        ]"""
    parser = IRParser()
    blk = parser._parse_basic_block(ir.splitlines(), in_mir=False)
    assert blk.instructions == 6


