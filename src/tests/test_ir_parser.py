import tempfile
from pathlib import Path

from ir_parser import analyze_ir, parse_basic_block


def test_parse_basic_block_mir():
    lines = [
        "bb.7:",
        "  %x = MOV32ri 1",
        "  successors: %bb.8",
    ]
    blk = parse_basic_block(lines, in_mir=True)
    assert blk.block == "bb.7"
    assert blk.instructions == 1
    assert "bb.7:" in blk.text


def test_analyze_ir_counts_blocks_and_instructions():
    sample = """
Function: foo
bb.0:
  %0 = ADD32rr killed renamable $eax, renamable $ecx, implicit-def dead $eflags
  successors: %bb.1
bb.1:
  %1 = MOV32ri 42
  %2 = ADD32rr renamable $edx, renamable $ebx, implicit-def dead $eflags
  %3 = RETQ
""".lstrip()
    with tempfile.TemporaryDirectory() as td:
        ir_path = Path(td) / "sample.mir"
        ir_path.write_text(sample, encoding="utf-8")

        functions = analyze_ir(str(ir_path))
        assert "foo" in functions
        fn = functions["foo"]
        assert fn.blocks == 2
        assert fn.total_instructions == 4
        blocks = {b.block: b for b in fn.blocks_detail}
        assert blocks["bb.0"].instructions == 1
        assert blocks["bb.1"].instructions == 3


