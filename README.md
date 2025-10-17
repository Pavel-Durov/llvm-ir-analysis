# LLVM IR/MIR analyzer

This tool parses LLVM textual IR and MIR dumps and summarizes per-function and per-basic-block statistics.

# Run

```shell
uv run python ./src/main.py ./ir/yklua.mir --skip-funcitons __yk_trace_basicblock
```

# Tests

```shell
uv run pytest
```

# Report example:

```json

  "summary": {
    "total_functions": 1,
    "total_basic_blocks": 13,
    "total_instructions": 123,
    "average_instructions_per_block": 9.461538461538462,
    "average_blocks_per_function": 13.0,
    "average_instructions_per_function": 123.0
  },
  "largest_block": {
    "function": "GCTM",
    "block": "38",
    "instructions": 40,
    "text": "..."
  },
  "top_by_instructions": [
    {
      "function": "GCTM",
      "blocks": 13,
      "instructions": 123,
      "conditional_branches": 0
    }
  ],
  "top_by_blocks": [
    {
      "function": "GCTM",
      "blocks": 13,
      "instructions": 123,
      "conditional_branches": 0
    }
  ]
}
```
