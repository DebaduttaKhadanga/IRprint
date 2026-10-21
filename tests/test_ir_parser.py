from conftest import FIXTURES, requires_clang

from irprint.cfg_signature import compute_cfg_signature
from irprint.compiler_wrapper import compile_to_ir
from irprint.ir_parser import (canonicalize_function, extract_opcode, normalized_ir_text,
                               parse_ir)

LOOP_IR = """
define i32 @count(i32 %0) {
  %2 = alloca i32, align 4
  store i32 0, ptr %2, align 4
  br label %3

3:                                                ; preds = %6, %1
  %4 = load i32, ptr %2, align 4
  %5 = icmp slt i32 %4, %0
  br i1 %5, label %6, label %8

6:                                                ; preds = %3
  %7 = add nsw i32 %4, 1
  store i32 %7, ptr %2, align 4
  br label %3

8:                                                ; preds = %3
  ret i32 %4
}

define void @pick(i32 %0) {
  switch i32 %0, label %4 [
    i32 1, label %2
    i32 2, label %3
  ]

2:
  br label %4

3:
  br label %4

4:
  ret void
}
"""


def test_extract_opcode():
    assert extract_opcode("%5 = load i32, ptr %4, align 4") == "load"
    assert extract_opcode("store i32 %1, ptr %3, align 4") == "store"
    assert extract_opcode("%7 = tail call i32 @foo(i32 %6)") == "call"
    assert extract_opcode("br i1 %9, label %10, label %12") == "br"
    assert extract_opcode("ret void") == "ret"


def test_parse_splits_functions_and_blocks():
    funcs = parse_ir(LOOP_IR)
    assert [f.name for f in funcs] == ["count", "pick"]
    count = funcs[0]
    assert len(count.blocks) == 4
    assert count.opcode_sequence()[:3] == ["alloca", "store", "br"]
    assert count.blocks[1].instructions[0].raw_line == "%4 = load i32, ptr %2, align 4"


def test_switch_is_joined_into_one_instruction():
    pick = parse_ir(LOOP_IR)[1]
    term = pick.blocks[0].terminator()
    assert term.opcode == "switch"
    assert "label %2" in term.raw_line and "label %3" in term.raw_line


def test_canonicalize_renames_labels_and_keeps_map():
    func = canonicalize_function(parse_ir(LOOP_IR)[0])
    assert [b.label for b in func.blocks] == ["bb0", "bb1", "bb2", "bb3"]
    assert func.label_map["3"] == "bb1"
    assert func.blocks[1].original_label == "3"


def test_cfg_signature_uses_original_labels_after_canonicalization():
    # Regression test for the label-resolution bug: back-edge %6 -> %3 must be
    # found even though the blocks are now called bb0..bb3.
    func = canonicalize_function(parse_ir(LOOP_IR)[0])
    sig = compute_cfg_signature(func)
    assert sig.as_tuple() == (4, 4, 1)


def test_switch_edges_counted():
    func = canonicalize_function(parse_ir(LOOP_IR)[1])
    sig = compute_cfg_signature(func)
    assert sig.num_edges == 3 + 1 + 1
    assert sig.max_loop_depth == 0


def test_normalized_ir_text_renames_registers():
    func = canonicalize_function(parse_ir(LOOP_IR)[0])
    text = normalized_ir_text(func)
    assert "bb1:" in text and "label %bb1" in text
    assert "%v0 = alloca" in text
    assert "%2" not in text


@requires_clang
def test_parse_real_clang_output():
    result = compile_to_ir(FIXTURES / "max_a.c")
    funcs = parse_ir(result.ir_text)
    assert [f.name for f in funcs] == ["max_val"]
    func = canonicalize_function(funcs[0])
    assert compute_cfg_signature(func).max_loop_depth == 1
