from ir_parser import parse_basic_block
import pytest


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
(
    """
    # End machine code for function loadFunction.

    # Machine code for function loadStringN: IsSSA, TracksLiveness
    Frame Objects:
        fi#0: size=40, align=16, at location [SP+8]
        Function Live Ins: $rdi in %10, $rsi in %11

    bb.0 (%ir-block.2):
        successors: %bb.1(0x80000000); %bb.1(100.00%)
        liveins: $rdi, $rsi
        %11:gr64 = COPY $rsi
        %10:gr64 = COPY $rdi
        %0:gr64 = MOV64rm %10:gr64, 1, $noreg, 0, $noreg :: (load (s64) from %ir.0)

  """, 3),
(
    """

bb.13 (%ir-block.103):
; predecessors: %bb.11
  successors: %bb.15(0x40000000), %bb.14(0x40000000); %bb.15(50.00%), %bb.14(50.00%)

  %21:gr64 = MOV64rm %1:gr64, 1, $noreg, 256, $noreg :: (load (s64) from %ir.104)
  TEST64rr %21:gr64, %21:gr64, implicit-def $eflags
  JCC_1 %bb.15, 4, implicit $eflags
  JMP_1 %bb.14
""", 4),
])
def test_mir_block_counts_instructions(ir:str, count:int):
    blk = parse_basic_block(ir.splitlines(), in_mir=True)
    assert blk.instructions == count
    assert len(blk.instruction_lines) == count