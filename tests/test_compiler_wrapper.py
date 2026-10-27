from conftest import FIXTURES, requires_clang, requires_rustc

from irprint.compiler_wrapper import build_command, compile_to_ir, detect_language


def test_detect_language():
    assert detect_language("a.c") == "c"
    assert detect_language("a.CPP") == "cpp"
    assert detect_language("a.cc") == "cpp"
    assert detect_language("a.rs") == "rust"
    assert detect_language("a.swift") == "swift"
    assert detect_language("a.py") is None


def test_c_command_uses_canonical_flags(tmp_path):
    cmd = build_command("c", "clang", tmp_path / "a.c", tmp_path / "out.ll", "O0")
    assert cmd[:4] == ["clang", "-S", "-emit-llvm", "-O0"]
    assert "-disable-O0-optnone" in cmd


def test_optnone_flag_only_at_O0(tmp_path):
    cmd = build_command("c", "clang", tmp_path / "a.c", tmp_path / "out.ll", "O2")
    assert "-O2" in cmd and "-disable-O0-optnone" not in cmd


def test_rust_command_is_library_crate(tmp_path):
    cmd = build_command("rust", "rustc", tmp_path / "a.rs", tmp_path / "out.ll", "O0")
    assert "--emit=llvm-ir" in cmd
    assert "--crate-type=lib" in cmd
    assert "opt-level=0" in cmd


def test_unsupported_extension(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    result = compile_to_ir(f)
    assert not result.success
    assert "unsupported" in result.error


@requires_clang
def test_compile_c_produces_ir():
    result = compile_to_ir(FIXTURES / "max_a.c")
    assert result.success, result.error
    assert "define" in result.ir_text and "@max_val" in result.ir_text
    assert "optnone" not in result.ir_text.split("@max_val")[1].split("{")[0]


@requires_clang
def test_compile_error_is_reported(tmp_path):
    bad = tmp_path / "bad.c"
    bad.write_text("int f( { return 0; }")
    result = compile_to_ir(bad)
    assert not result.success
    assert result.error


@requires_rustc
def test_compile_rust_produces_ir():
    result = compile_to_ir(FIXTURES / "max_rust.rs")
    assert result.success, result.error
    assert result.language == "rust"
    assert "define" in result.ir_text
