from irprint.models import BasicBlock, Instruction
from irprint.normalizer import (demangle_symbol, is_runtime_boilerplate, is_runtime_call,
                                merge_straight_line_blocks, remove_panic_guards,
                                strip_debug_lines)

SAMPLE = """; ModuleID = 'x.c'
source_filename = "x.c"
target triple = "x86_64-unknown-linux-gnu"

define dso_local i32 @f(i32 noundef %0) #0 !dbg !10 {
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata ptr %2, metadata !15, metadata !DIExpression()), !dbg !16
  store i32 %0, ptr %2, align 4, !dbg !17
  %3 = load i32, ptr %2, align 4, !dbg !18 ; trailing comment
  ret i32 %3, !dbg !19
}

attributes #0 = { noinline nounwind }
!10 = distinct !DISubprogram(name: "f")
"""


def test_strip_debug_lines_removes_noise():
    cleaned = strip_debug_lines(SAMPLE)
    assert "source_filename" not in cleaned
    assert "target triple" not in cleaned
    assert "llvm.dbg" not in cleaned
    assert "!dbg" not in cleaned
    assert "attributes #0" not in cleaned
    assert "DISubprogram" not in cleaned
    assert "trailing comment" not in cleaned
    assert "store i32 %0, ptr %2, align 4" in cleaned


def test_demangle_c_cpp_rust():
    assert demangle_symbol("max_val") == "max_val"
    assert demangle_symbol("_Z7max_valPii") == "max_val"
    assert demangle_symbol("_ZN7student7max_val17h0123456789abcdefE") == "max_val"
    assert demangle_symbol("_RNvCs8AlEeC1jcYO_1m7max_val") == "max_val"
    assert demangle_symbol("_RNvCs8AlEeC1jcYO_1m7max_val", hint="m::max_val") == "max_val"


def test_runtime_boilerplate_detection():
    assert is_runtime_boilerplate("_ZN4core9panicking18panic_bounds_check17h0123456789abcdefE")
    assert is_runtime_boilerplate("__rust_alloc")
    assert is_runtime_boilerplate("_RNvMNtCskADBYZwJmSU_4core5sliceSl4iterCsX021x86inA_5grace")
    assert is_runtime_boilerplate("_ZNKSt6vectorIiSaIiEE4sizeEv")
    assert not is_runtime_boilerplate("max_val")
    assert not is_runtime_boilerplate("_RNvCs8AlEeC1jcYO_1m7max_val")


def test_runtime_call_detection():
    assert is_runtime_call("call void @_RNvNtCskADBYZwJmSU_4core9panicking18panic_bounds_check(i64 0)")
    assert not is_runtime_call("%5 = call i32 @helper(i32 %4)")


def _bb(label, *lines):
    from irprint.ir_parser import extract_opcode
    return BasicBlock(label=label, original_label=label,
                      instructions=[Instruction(extract_opcode(l), l) for l in lines])


def test_remove_panic_guards():
    blocks = [
        _bb("start", "%_6 = icmp ult i64 0, %a.1", "br i1 %_6, label %bb1, label %panic"),
        _bb("bb1", "%1 = load i32, ptr %0, align 4", "ret i32 %1"),
        _bb("panic", "unreachable"),
    ]
    kept = remove_panic_guards(blocks)
    assert [b.original_label for b in kept] == ["start", "bb1"]
    assert [i.raw_line for i in kept[0].instructions] == ["br label %bb1"]


def test_merge_straight_line_blocks():
    blocks = [
        _bb("entry", "%1 = alloca i32, align 4", "br label %a"),
        _bb("a", "store i32 0, ptr %1, align 4", "br label %b"),
        _bb("b", "ret void"),
    ]
    merged = merge_straight_line_blocks(blocks)
    assert len(merged) == 1
    assert [i.opcode for i in merged[0].instructions] == ["alloca", "store", "ret"]
