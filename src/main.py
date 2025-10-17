import argparse
from ir_parser import analyze_ir
from report import SummaryReport



def main():
    parser = argparse.ArgumentParser(
        prog='summarize_ir',
        description='Analyze IR CSV or parse textual LLVM IR/MIR to summarize basic blocks and instructions.'
    )
    parser.add_argument('input', help='Path to .csv (from analyze_ir.py) or textual .ir/.mir file')
    parser.add_argument(
        '--skip-funcitons', dest='skip_functions', metavar='SUBSTR', action='append', default=None,
        help='Skip functions whose name contains SUBSTR. Can be repeated; defaults to __yk_trace_basicblock'
    )

    args = parser.parse_args()

    filename = args.input
    skip_patterns = args.skip_functions or ['__yk_trace_basicblock']

    functions = analyze_ir(filename, skip_patterns=skip_patterns)
    summary_json = SummaryReport(functions=functions).to_json(indent=2)
    print(summary_json)


if __name__ == '__main__':
    main()

