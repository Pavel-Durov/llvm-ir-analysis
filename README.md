## LLVM IR/MIR analyzer

Parses LLVM textual IR and MIR dumps and produces JSON summaries of functions and basic blocks.


### Samples

- Reports:
  - [`reports/ykcbf.report`](reports/ykcbf.report)
  - [`reports/yklua.report`](reports/yklua.report)
- MIR inputs:
  - [`ir/ykcbf.mir`](ir/ykcbf.mir)
  - [`ir/yklua.mir`](ir/yklua.mir)
  - [`ir/yklua.ir`](ir/yklua.ir)


### Install

```shell
uv sync --dev
```

### CLI

- Analyze a single file (default command is `analyze`):

```shell
uv run python -m src.main ./ir/yklua.mir --skip-funcitons __yk_trace_basicblock
```


### JSON output shape

```json
{
  "summary": {
    "total_functions": 1,
    "total_basic_blocks": 13,
    "total_instructions": 123,
    "average_instructions_per_block": 9.46,
    "average_blocks_per_function": 13.0,
    "average_instructions_per_function": 123.0
  },
  "largest_block": {
    "function": "GCTM",
    "block": "38",
    "instructions": 40,
    "text": "... full basic block text ..."
  },
  "top_by_instructions": [ { "function": "GCTM", "blocks": 13, "instructions": 123, "conditional_branches": 0 } ],
  "top_by_blocks": [ { "function": "GCTM", "blocks": 13, "instructions": 123, "conditional_branches": 0 } ]
}
```

### Tests

```shell
uv run pytest -q
```

### Pre-commit (lint + tests)

This repo uses pre-commit to run Ruff (lint + format) and the unit test suite before each commit.

Setup (one-time):

```shell
uv run pre-commit install
# optional: update hook versions
uv run pre-commit autoupdate
```

Run hooks against all files:

```shell
uv run pre-commit run --all-files
```

What runs:
- Ruff (with autofix) and Ruff format
- Unit tests via `pytest`
