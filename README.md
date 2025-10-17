# LLVM IR/MIR analyzer

This tool parses LLVM textual IR and MIR dumps and summarizes per-function and per-basic-block statistics.

```shell
uv run python ./main.py ./ir/yklua.ir --skip-funcitons __yk_trace_basicblock
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
    "text": "38:                                               ; preds = %32\n  %39 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 4\n  %40 = load i8, ptr %39, align 1, !tbaa !117\n  %41 = getelementptr inbounds %struct.global_State, ptr %3, i64 0, i32 16\n  %42 = load i8, ptr %41, align 2, !tbaa !123\n  %43 = or i8 %42, 2\n  store i8 %43, ptr %41, align 2, !tbaa !123\n  store i8 0, ptr %39, align 1, !tbaa !117\n  %44 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 6\n  %45 = load ptr, ptr %44, align 8, !tbaa !22\n  %46 = getelementptr inbounds %union.StackValue, ptr %45, i64 1\n  store ptr %46, ptr %44, align 8, !tbaa !22\n  %47 = load i64, ptr %33, align 8\n  store i64 %47, ptr %45, align 8\n  %48 = getelementptr inbounds i8, ptr %33, i64 8\n  %49 = load i8, ptr %48, align 8, !tbaa !23\n  %50 = getelementptr inbounds %struct.TValue, ptr %45, i64 0, i32 1\n  store i8 %49, ptr %50, align 8, !tbaa !23\n  %51 = load ptr, ptr %44, align 8, !tbaa !22\n  %52 = getelementptr inbounds %union.StackValue, ptr %51, i64 1\n  store ptr %52, ptr %44, align 8, !tbaa !22\n  %53 = ptrtoint ptr %5 to i64\n  store i64 %53, ptr %51, align 8\n  %54 = getelementptr inbounds %struct.TValue, ptr %51, i64 0, i32 1\n  store i8 %9, ptr %54, align 8, !tbaa !23\n  %55 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 8\n  %56 = load ptr, ptr %55, align 8, !tbaa !30\n  %57 = getelementptr inbounds %struct.CallInfo, ptr %56, i64 0, i32 7\n  %58 = load i16, ptr %57, align 2, !tbaa !121\n  %59 = or i16 %58, 128\n  store i16 %59, ptr %57, align 2, !tbaa !121\n  %60 = load ptr, ptr %44, align 8, !tbaa !22\n  %61 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 10\n  %62 = load ptr, ptr %61, align 8, !tbaa !22\n  %63 = load i8, ptr %39, align 1, !tbaa !117\n  %64 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 18\n  %65 = load i64, ptr %64, align 8, !tbaa !118\n  store i64 0, ptr %64, align 8, !tbaa !118\n  %66 = tail call i32 @luaD_rawrunprotected(ptr noundef %0, ptr noundef nonnull @dothecall, ptr noundef null)\n  %67 = icmp eq i32 %66, 0\n  br i1 %67, label %90, label %68, !prof !31\n"
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
## Biggest basic block in yklua:
```ir
38:                                               ; preds = %32
  %39 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 4
  %40 = load i8, ptr %39, align 1, !tbaa !117
  %41 = getelementptr inbounds %struct.global_State, ptr %3, i64 0, i32 16
  %42 = load i8, ptr %41, align 2, !tbaa !123
  %43 = or i8 %42, 2
  store i8 %43, ptr %41, align 2, !tbaa !123
  store i8 0, ptr %39, align 1, !tbaa !117
  %44 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 6
  %45 = load ptr, ptr %44, align 8, !tbaa !22
  %46 = getelementptr inbounds %union.StackValue, ptr %45, i64 1
  store ptr %46, ptr %44, align 8, !tbaa !22
  %47 = load i64, ptr %33, align 8
  store i64 %47, ptr %45, align 8
  %48 = getelementptr inbounds i8, ptr %33, i64 8
  %49 = load i8, ptr %48, align 8, !tbaa !23
  %50 = getelementptr inbounds %struct.TValue, ptr %45, i64 0, i32 1
  store i8 %49, ptr %50, align 8, !tbaa !23
  %51 = load ptr, ptr %44, align 8, !tbaa !22
  %52 = getelementptr inbounds %union.StackValue, ptr %51, i64 1
  store ptr %52, ptr %44, align 8, !tbaa !22
  %53 = ptrtoint ptr %5 to i64
  store i64 %53, ptr %51, align 8
  %54 = getelementptr inbounds %struct.TValue, ptr %51, i64 0, i32 1
  store i8 %9, ptr %54, align 8, !tbaa !23
  %55 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 8
  %56 = load ptr, ptr %55, align 8, !tbaa !30
  %57 = getelementptr inbounds %struct.CallInfo, ptr %56, i64 0, i32 7
  %58 = load i16, ptr %57, align 2, !tbaa !121
  %59 = or i16 %58, 128
  store i16 %59, ptr %57, align 2, !tbaa !121
  %60 = load ptr, ptr %44, align 8, !tbaa !22
  %61 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 10
  %62 = load ptr, ptr %61, align 8, !tbaa !22
  %63 = load i8, ptr %39, align 1, !tbaa !117
  %64 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 18
  %65 = load i64, ptr %64, align 8, !tbaa !118
  store i64 0, ptr %64, align 8, !tbaa !118
  %66 = tail call i32 @luaD_rawrunprotected(ptr noundef %0, ptr noundef nonnull @dothecall, ptr noundef null)
  %67 = icmp eq i32 %66, 0
  br i1 %67, label %90, label %68, !prof !31
```