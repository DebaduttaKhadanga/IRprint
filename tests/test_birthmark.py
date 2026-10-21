from irprint.birthmark import build_birthmark, extract_kgrams
from irprint.ir_parser import canonicalize_function, parse_ir

IR = """
define i32 @f(i32 %0) {
  %2 = add i32 %0, 1
  %3 = mul i32 %2, 2
  %4 = sub i32 %3, 1
  ret i32 %4
}
"""


def test_extract_kgrams_sliding_window():
    ops = ["a", "b", "c", "d"]
    assert extract_kgrams(ops, 2) == {("a", "b"), ("b", "c"), ("c", "d")}
    assert extract_kgrams(ops, 3) == {("a", "b", "c"), ("b", "c", "d")}


def test_short_sequence_gives_one_kgram():
    assert extract_kgrams(["a", "b"], 5) == {("a", "b")}
    assert extract_kgrams([], 3) == set()


def test_build_birthmark_has_all_ks():
    func = canonicalize_function(parse_ir(IR)[0])
    bm = build_birthmark(func)
    assert sorted(bm.kgrams) == [2, 3, 4, 5]
    assert ("add", "mul", "sub") in bm.kgrams[3]
    assert bm.opcode_count == 4
    assert bm.cfg.as_tuple() == (1, 0, 0)
    assert "define @f" in bm.normalized_ir


def test_register_names_do_not_matter():
    renamed = IR.replace("%0", "%x").replace("%2", "%tmp").replace("%3", "%y").replace("%4", "%z")
    a = build_birthmark(canonicalize_function(parse_ir(IR)[0]))
    b = build_birthmark(canonicalize_function(parse_ir(renamed)[0]))
    assert a.kgrams == b.kgrams
