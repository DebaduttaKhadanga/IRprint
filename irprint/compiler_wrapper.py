"""
Functionality 1: turn C / C++ / Rust / Swift source files into textual LLVM IR.

Every compilation runs inside its own temporary directory and has a timeout,
so a broken or malicious submission cannot hang the scan or pollute the
working directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from irprint.models import CompileResult

# File extension -> language name.
LANGUAGE_BY_EXTENSION = {
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".rs": "rust",
    ".swift": "swift",
}

# Language -> the compiler executable we need.
COMPILER_BY_LANGUAGE = {
    "c": "clang",
    "cpp": "clang++",
    "rust": "rustc",
    "swift": "swiftc",
}

# Extra places we look for compilers that were installed without root
# (rustup puts rustc in ~/.cargo/bin, for example).
EXTRA_TOOL_DIRS = [
    Path.home() / ".cargo" / "bin",
    Path.home() / ".local" / "llvm-env" / "bin",
    Path("/usr/lib/llvm-18/bin"),
    Path("/usr/lib/llvm-19/bin"),
]

DEFAULT_TIMEOUT_SECONDS = 30


def detect_language(source_path: str | Path) -> str | None:
    """Return "c", "cpp", "rust", "swift", or None for unsupported files."""
    return LANGUAGE_BY_EXTENSION.get(Path(source_path).suffix.lower())


def find_tool(name: str) -> str | None:
    """
    Locate a compiler. Order: IRPRINT_<NAME> env var, then $PATH, then the
    user-space install folders above. Returns None if it is not installed.
    """
    env_key = "IRPRINT_" + name.upper().replace("+", "X").replace("-", "_")
    if os.environ.get(env_key):
        return os.environ[env_key]
    on_path = shutil.which(name)
    if on_path:
        return on_path
    for folder in EXTRA_TOOL_DIRS:
        candidate = folder / name
        if candidate.exists():
            return str(candidate)
    return None


def build_command(language: str, compiler: str, source: Path, output: Path,
                  opt_level: str) -> list[str]:
    """
    Build the exact compiler command line for one language.

    opt_level is "O0", "O1", "O2" or "O3". IRprint's canonical mode is "O0".
    """
    level_number = opt_level.lstrip("Oo")

    if language in ("c", "cpp"):
        cmd = [compiler, "-S", "-emit-llvm", f"-O{level_number}", "-g0"]
        if level_number == "0":
            # Without this flag clang tags every function `optnone`, which
            # blocks any later pass from touching it. We keep the IR at -O0
            # but leave it in a "normal" state (see decision.md, Decision 2).
            cmd += ["-Xclang", "-disable-O0-optnone"]
        return cmd + ["-o", str(output), str(source)]

    if language == "rust":
        # --crate-type=lib: student files often have no main(); a library
        # crate compiles fine without one (see decision.md, Decision 2).
        # overflow-checks=off: stops rustc injecting an add-with-overflow +
        # panic branch after every arithmetic op, which C does not have.
        return [compiler, "--emit=llvm-ir", "--crate-type=lib",
                "-C", f"opt-level={level_number}", "-C", "debuginfo=0",
                "-C", "overflow-checks=off", "-C", "panic=abort",
                "-o", str(output), str(source)]

    if language == "swift":
        swift_level = "-Onone" if level_number == "0" else "-O"
        return [compiler, "-emit-ir", swift_level, "-parse-as-library",
                "-o", str(output), str(source)]

    raise ValueError(f"unsupported language: {language}")


# =====================================================================
# FUNCTIONALITY 1: Multi-Language LLVM-IR Compilation Wrapper
# =====================================================================
def compile_to_ir(source_path: str | Path, opt_level: str = "O0",
                  timeout: int = DEFAULT_TIMEOUT_SECONDS) -> CompileResult:
    """
    Compile one source file to LLVM IR text.

    Steps:
      1. Detect the language from the file extension.
      2. Find the right compiler (clang / clang++ / rustc / swiftc).
      3. Copy the file into a fresh temporary directory.
      4. Run the compiler with a timeout.
      5. Read the produced .ll file and return it in a CompileResult.
    """
    source_path = Path(source_path)
    language = detect_language(source_path)
    if language is None:
        return CompileResult(str(source_path), "unknown", False,
                             error=f"unsupported file extension: {source_path.suffix}",
                             opt_level=opt_level)

    compiler = find_tool(COMPILER_BY_LANGUAGE[language])
    if compiler is None:
        return CompileResult(str(source_path), language, False,
                             error=f"{COMPILER_BY_LANGUAGE[language]} is not installed",
                             opt_level=opt_level)

    with tempfile.TemporaryDirectory(prefix="irprint_") as workdir:
        isolated_source = Path(workdir) / source_path.name
        shutil.copyfile(source_path, isolated_source)
        output_ll = Path(workdir) / "out.ll"
        cmd = build_command(language, compiler, isolated_source, output_ll, opt_level)

        try:
            proc = subprocess.run(cmd, cwd=workdir, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return CompileResult(str(source_path), language, False,
                                 error=f"compiler timed out after {timeout}s",
                                 command=cmd, opt_level=opt_level)

        if proc.returncode != 0 or not output_ll.exists():
            return CompileResult(str(source_path), language, False,
                                 error=proc.stderr.strip() or "compiler failed",
                                 command=cmd, opt_level=opt_level)

        ir_text = output_ll.read_text(errors="replace")

    return CompileResult(str(source_path), language, True, ir_text=ir_text,
                         command=cmd, opt_level=opt_level)


def available_compilers() -> dict[str, str | None]:
    """Which compilers this machine has. Used by the CLI and the tests."""
    return {lang: find_tool(tool) for lang, tool in COMPILER_BY_LANGUAGE.items()}
