from ir_parser import parse_basic_block
import pytest

def test_ir_block_counts_four_instructions():
    lines = [
        "11:                                               ; preds = %3",
        "  %12 = getelementptr inbounds %struct.lua_State, ptr %0, i64 0, i32 7",
        "  %13 = load ptr, ptr %12, align 8, !tbaa !10",
        "  %14 = getelementptr inbounds %struct.global_State, ptr %13, i64 0, i32 8",
        "  br label %15",
    ]
    blk = parse_basic_block(lines, in_mir=False)
    assert blk.block.startswith("11")
    assert blk.instructions == 4


@pytest.mark.parametrize("ir, count", [
    (
        """
        bb.20 (%ir-block.84):
            ; predecessors: %bb.19
            successors: %bb.21
            liveins: $ebx
            $edi = MOV32ri 134
            $esi = MOV32ri 19
            CALL64pcrel32 target-flags(x86-plt) @__yk_trace_basicblock, <regmask $bh $bl $bp $bph $bpl $bx $ebp $ebx $hbp $hbx $rbp $rbx $r12 $r13 $r14 $r15 $r12b $r13b $r14b $r15b $r12bh $r13bh $r14bh $r15bh $r12d $r13d $r14d $r15d $r12w $r13w $r14w $r15w $r12wh and 3 more...>, implicit $rsp, implicit $ssp, implicit $edi, implicit $esi
            renamable $r14 = MOV64ri @.str.21.62
            renamable $rax = MOV64ri @.str.25.61
            CMP32ri killed renamable $ebx, 0, implicit-def $eflags
            renamable $r14 = CMOV64rr killed renamable $r14(tied-def 0), killed renamable $rax, 4, implicit killed $eflags
        """, 7
    ),(
        """15:                                               ; preds = %11, %3
        %16 = phi ptr [ %14, %11 ], [ %7, %3 ]
        %17 = getelementptr inbounds %struct.TValue, ptr %16, i64 0, i32 1
        %18 = load i8, ptr %17, align 8, !tbaa !23
        %19 = zext i8 %18 to i32
        %20 = and i32 %19, 15
        switch i32 %20, label %66 [
            i32 4, label %40
            i32 3, label %21
        ]""", 6
    ),
])
def test_ir_block_counts_instructions(ir:str, count:int):
    blk = parse_basic_block(ir.splitlines(), in_mir=True)
    assert blk.instructions == count


@pytest.mark.parametrize("ir, count", [(
    """
    bb.20 (%ir-block.84):
        ; predecessors: %bb.19
        successors: %bb.21
        liveins: $ebx
        $edi = MOV32ri 134
        $esi = MOV32ri 19
        CALL64pcrel32 target-flags(x86-plt) @__yk_trace_basicblock, <regmask $bh $bl $bp $bph $bpl $bx $ebp $ebx $hbp $hbx $rbp $rbx $r12 $r13 $r14 $r15 $r12b $r13b $r14b $r15b $r12bh $r13bh $r14bh $r15bh $r12d $r13d $r14d $r15d $r12w $r13w $r14w $r15w $r12wh and 3 more...>, implicit $rsp, implicit $ssp, implicit $edi, implicit $esi
        renamable $r14 = MOV64ri @.str.21.62
        renamable $rax = MOV64ri @.str.25.61
        CMP32ri killed renamable $ebx, 0, implicit-def $eflags
        renamable $r14 = CMOV64rr killed renamable $r14(tied-def 0), killed renamable $rax, 4, implicit killed $eflags
    """, 7),
    (
        """bb.50:
; predecessors: %bb.5
  successors: %bb.46(0x80000000); %bb.46(100.00%)
  liveins: $r8
  JMP_1 %bb.46""", 1),

    ])
def test_mir_block_counts_instructions(ir:str, count:int):
    blk = parse_basic_block(ir.splitlines(), in_mir=True)
    assert blk.instructions == count
