from ir_parser.model import Function, Block
from report import SummaryReport


def test_summary_report_dict_and_json():
    fn = Function(name="foo")
    fn.blocks_detail.append(Block(block="bb.0", instructions=1, text="bb.0:\n  inst"))
    fn.blocks_detail.append(Block(block="bb.1", instructions=3, text="bb.1:\n  inst1\n  inst2\n  inst3"))
    fn.blocks = 2
    fn.total_instructions = 4

    report = SummaryReport(functions={"foo": fn})
    d = report.to_dict()

    assert d["summary"]["total_functions"] == 1
    assert d["summary"]["total_basic_blocks"] == 2
    assert d["summary"]["total_instructions"] == 4
    largest = d["largest_block"]
    assert largest["function"] == "foo"
    assert largest["block"] == "bb.1"
    assert largest["instructions"] == 3
    assert "bb.1:" in largest["text"]

    json_text = report.to_json(indent=2)
    assert "\n" in json_text
    assert '"total_functions": 1' in json_text


