from ir_parser import parse_basic_block
import pytest



class TestCase():
    def __init__(self, mir: str, count: int):
        self.mir = mir
        self.count = count


SingleBlock = TestCase(
    mir="""
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
    """,
    count=7,
)

MultipleBlocks = TestCase(
    mir="""
    bb.0 (%ir-block.149):
; predecessors: %bb.17
  liveins: $rax, $r14
  renamable $eax = MOV32rr renamable $eax, implicit killed $rax, implicit-def $rax
  renamable $ecx = LEA64_32r renamable $r14, 1, $noreg, -48, $noreg
  renamable $r14d = OR32ri renamable $r14d(tied-def 0), 32, implicit-def dead $eflags, implicit killed $r14, implicit-def $r14
  renamable $r14d = nsw ADD32ri renamable $r14d(tied-def 0), -87, implicit-def dead $eflags, implicit killed $r14, implicit-def $r14
  TEST8mi killed renamable $rax, 1, $noreg, @luai_ctype_, $noreg, 2, implicit-def $eflags :: (invariant load (s8) from %ir.151, !tbaa !22)
  renamable $r14d = CMOV32rr renamable $r14d(tied-def 0), killed renamable $ecx, 5, implicit $eflags, implicit killed $r14, implicit-def $r14
  $eax = COPY renamable $r14d, implicit killed $r14
  $rsp = frame-destroy ADD64ri32 $rsp(tied-def 0), 24, implicit-def dead $eflags
  frame-destroy CFI_INSTRUCTION def_cfa_offset 56
  $rbx = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 48
  $r12 = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 40
  $r13 = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 32
  $r14 = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 24
  $r15 = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 16
  $rbp = frame-destroy POP64r implicit-def $rsp, implicit $rsp
  frame-destroy CFI_INSTRUCTION def_cfa_offset 8
  RET 0, $eax
bb.28 (%ir-block.1):
  successors: %bb.1(0x40000000), %bb.3(0x40000000); %bb.1(50.00%), %bb.3(50.00%)
  liveins: $rdi, $r15, $r14, $rbx
  frame-setup PUSH64r killed $r15, implicit-def $rsp, implicit $rsp
  frame-setup CFI_INSTRUCTION def_cfa_offset 16
  frame-setup PUSH64r killed $r14, implicit-def $rsp, implicit $rsp
  frame-setup CFI_INSTRUCTION def_cfa_offset 24
  frame-setup PUSH64r killed $rbx, implicit-def $rsp, implicit $rsp
  frame-setup CFI_INSTRUCTION def_cfa_offset 32
  $rsp = frame-setup SUB64ri32 $rsp(tied-def 0), 16, implicit-def dead $eflags
  frame-setup CFI_INSTRUCTION def_cfa_offset 48
  CFI_INSTRUCTION offset $rbx, -32
  CFI_INSTRUCTION offset $r14, -24
  CFI_INSTRUCTION offset $r15, -16
  renamable $rbx = COPY $rdi
  renamable $rax = MOV64rm $rdi, 1, $noreg, 32, $noreg :: (load (s64) from %ir.4)
  renamable $rax = MOV64rm killed renamable $rax, 1, $noreg, 0, $noreg :: (load (s64) from %ir.5)
  renamable $cl = MOV8rm renamable $rax, 1, $noreg, 8, $noreg :: (load (s8) from %ir.7, align 8)
  CMP8ri renamable $cl, 102, implicit-def $eflags
  JCC_1 %bb.3, 5, implicit $eflags
    """,
    count=23,
)
@pytest.mark.parametrize("test_case", [SingleBlock, MultipleBlocks])
def test_mir_block_counts_instructions(test_case: TestCase):
    blk = parse_basic_block(test_case.mir.splitlines(), in_mir=True)
    assert blk.instructions == test_case.count
    assert len(blk.instruction_lines) == test_case.count