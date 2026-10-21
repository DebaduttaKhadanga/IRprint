"""
Functionality 2 (part 1): clean raw LLVM IR before parsing.

Three jobs:
  * strip_debug_lines()        - remove debug info and metadata noise
  * demangle_symbol()          - turn C++/Rust mangled names into plain names
  * is_runtime_boilerplate()   - spot compiler-inserted helper functions
                                 (Rust panics, bounds checks, std internals)
"""

from __future__ import annotations

import re

# `, !dbg !12`, `, !tbaa !7`, `, !llvm.loop !9` ... attached to instructions.
METADATA_ATTACHMENT = re.compile(r",\s*!(?:[\w.]+)\s+!\d+")
# `!dbg !10`, `!guid !8` attached to a define line (no leading comma).
DEFINE_METADATA = re.compile(r"\s!(?:[\w.]+)\s+!\d+")
# `#0`, `#1` attribute-group references at the end of a define line.
ATTRIBUTE_GROUP_REF = re.compile(r"\s#\d+")
# Calls to debug intrinsics: call void @llvm.dbg.declare(...)
DEBUG_INTRINSIC_CALL = re.compile(r"\bcall\s+void\s+@llvm\.dbg\.")
# New-style (LLVM 19+) debug records: #dbg_declare(...), #dbg_value(...)
DEBUG_RECORD = re.compile(r"^\s*#dbg_\w+\(")
# Rust legacy-mangling hash component, e.g. "17h0123456789abcdefE" -> "h0123456789abcdef".
RUST_HASH = re.compile(r"^h[0-9a-f]{16}$")

# Function names (after demangling) that are compiler runtime support,
# not student logic. A submission's score should not depend on them.
RUNTIME_NAME_MARKERS = (
    "panic",                 # core::panicking::panic, panic_fmt, ...
    "panic_bounds_check",
    "__rust_",               # __rust_alloc, __rust_dealloc, ...
    "rust_begin_unwind",
    "__cxa_",                # C++ exception runtime
    "__gxx_personality",
    "rust_eh_personality",
    "llvm.",                 # LLVM intrinsics
)
# Rust standard-library paths that get monomorphized into the student crate.
RUST_STD_PREFIXES = ("core::", "alloc::", "std::", "<core::", "<alloc::", "<std::")
RUST_STD_CRATES = ("core", "alloc", "std")
# C++ standard-library symbols (std::vector<int>::size, __gnu_cxx iterators...)
# that clang emits as linkonce_odr copies inside the student's module.
CPP_STD_PREFIXES = ("_ZNSt", "_ZNKSt", "_ZSt", "_ZNSa", "_ZNKSa", "_ZNSs", "_ZNKSs",
                    "_ZN9__gnu_cxx", "_ZNK9__gnu_cxx", "_ZNSt3__1", "_ZNKSt3__1")


# =====================================================================
# FUNCTIONALITY 2: LLVM-IR Normalization (debug & metadata stripping)
# =====================================================================
def strip_debug_lines(ir_text: str) -> str:
    """
    Remove everything that changes between compilations but says nothing
    about the algorithm:
      - source_filename / ModuleID / target lines (file names, machine info)
      - top-level metadata lines that start with "!"
      - attribute group definitions ("attributes #0 = {...}")
      - calls to @llvm.dbg.* and #dbg_* records
      - ", !dbg !<id>" style attachments at the end of instructions
      - comments (everything after ";" on a line)
    Returns the cleaned IR text.
    """
    cleaned_lines = []
    for line in ir_text.splitlines():
        stripped = line.strip()

        if stripped.startswith(("source_filename", "target datalayout",
                                "target triple", "attributes #", "!")):
            continue
        if DEBUG_INTRINSIC_CALL.search(line) or DEBUG_RECORD.match(line):
            continue
        if stripped.startswith("declare ") and "@llvm.dbg." in stripped:
            continue

        line = _strip_comment(line)
        line = METADATA_ATTACHMENT.sub("", line)
        if line.lstrip().startswith("define "):
            line = ATTRIBUTE_GROUP_REF.sub("", line)
            line = DEFINE_METADATA.sub("", line)
        line = line.rstrip()

        if line.strip():
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines) + "\n"


def _strip_comment(line: str) -> str:
    """Drop a trailing `; comment`, but not a ';' that sits inside a string."""
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_string = not in_string
        elif ch == ";" and not in_string:
            return line[:i]
    return line


def _read_length_prefixed(text: str, pos: int) -> tuple[str, int] | None:
    """Itanium-style `<len><chars>` reader: "7max_val" -> ("max_val", 8)."""
    digits = ""
    while pos < len(text) and text[pos].isdigit():
        digits += text[pos]
        pos += 1
    if not digits:
        return None
    length = int(digits)
    return text[pos:pos + length], pos + length


def collect_demangle_hints(ir_text: str) -> dict[str, str]:
    """
    rustc writes the readable path in a comment right above each function:

        ; m::max_val
        ; Function Attrs: nounwind nonlazybind uwtable
        define i32 @_RNvCs8AlEeC1jcYO_1m7max_val(...)

    Return {mangled symbol: "m::max_val"} so we can use rustc's own
    demangling instead of re-implementing the full v0 grammar.
    Must be called BEFORE strip_debug_lines(), which removes comments.
    """
    hints: dict[str, str] = {}
    last_comment = None
    for line in ir_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("; ") and not stripped.startswith(("; Function Attrs", "; ModuleID")):
            last_comment = stripped[2:].strip()
        elif stripped.startswith("define "):
            match = re.search(r"@([-\w$.]+|\"[^\"]+\")\s*\(", stripped)
            if match and last_comment:
                hints[match.group(1).strip('"')] = last_comment
            last_comment = None
        elif stripped and not stripped.startswith(";"):
            last_comment = None
    return hints


def _split_rust_path(path: str) -> list[str]:
    """'m::max_val' -> ['m', 'max_val'], keeping '<A as B>::f' style paths whole-ish."""
    return [part for part in re.split(r"::(?![^<]*>)", path) if part] or [path]


def rust_v0_crate(name: str) -> str | None:
    """
    Crate that owns a v0-mangled Rust symbol: the first crate root
    'C' [s<disambiguator>_] <len><name>. For "<[i32]>::iter" this is "core",
    even though the readable name does not start with "core::".
    """
    match = re.search(r"C(?:s[0-9A-Za-z]*_)?(\d+)_?", name)
    if not match:
        return None
    start = match.end()
    return name[start:start + int(match.group(1))]


def _demangle_rust_v0(name: str) -> list[str]:
    """
    Minimal v0 ("_R...") demangler for the common case. The crate name follows
    'C' (+ optional disambiguator 's<base62>_'), and the function name is the
    final length-prefixed identifier, e.g.
        _RNvCs8AlEeC1jcYO_1m7max_val -> ["m", "max_val"]
    """
    crate = rust_v0_crate(name)
    last = None
    for i in range(len(name)):
        if not name[i].isdigit() or (i > 0 and name[i - 1].isdigit()):
            continue
        j = i
        while j < len(name) and name[j].isdigit():
            j += 1
        k = j + 1 if j < len(name) and name[j] == "_" else j
        if len(name) - k == int(name[i:j]) and int(name[i:j]) > 0:
            last = name[k:]
            break
    parts = [p for p in (crate, last) if p]
    return parts or [name]


def demangle_path(symbol: str, hint: str | None = None) -> list[str]:
    """
    Split a mangled symbol into its path components.

      _ZN4core3ptr13drop_in_place17h0123456789abcdefE
          -> ["core", "ptr", "drop_in_place"]       (Rust legacy mangling)
      _RNvCs8AlEeC1jcYO_1m7max_val -> ["m", "max_val"] (Rust v0 mangling)
      _Z7max_valPii             -> ["max_val"]          (C++ free function)
      max_val                   -> ["max_val"]          (C, not mangled)

    If rustc gave us a readable `hint` comment, that wins.
    """
    if hint:
        return _split_rust_path(hint)
    name = symbol.strip('"')
    if name.startswith("_R"):
        return _demangle_rust_v0(name)
    if name.startswith("_ZN"):
        parts, pos = [], 3
        while pos < len(name) and name[pos] != "E":
            piece = _read_length_prefixed(name, pos)
            if piece is None:
                # C++ nested names can contain things like 'C1', 'K' etc.
                pos += 1
                continue
            component, pos = piece
            parts.append(component)
        parts = [p for p in parts if not RUST_HASH.match(p)]
        return [_unescape_rust(p) for p in parts] or [name]
    if name.startswith("_Z"):
        piece = _read_length_prefixed(name, 2)
        if piece is not None and piece[0]:
            return [piece[0]]
    return [name]


def _unescape_rust(component: str) -> str:
    """Rust legacy mangling escapes: $LT$ -> <, $GT$ -> >, .. -> ::, $u20$ -> ' '."""
    replacements = {"$LT$": "<", "$GT$": ">", "$u20$": " ", "$C$": ",",
                    "$RF$": "&", "$BP$": "*", "$u7b$": "{", "$u7d$": "}"}
    for escaped, plain in replacements.items():
        component = component.replace(escaped, plain)
    return component.replace("..", "::")


# =====================================================================
# FUNCTIONALITY 2: Symbol Demangling & Runtime-Boilerplate Filtering
# =====================================================================
def demangle_symbol(symbol: str, hint: str | None = None) -> str:
    """
    Return the clean base name of a function, e.g.
      "_ZN7student7max_val17h9f2a...E" -> "max_val"
      "_RNvCs8AlEeC1jcYO_1m7max_val"   -> "max_val"
      "_Z7max_valPii"                  -> "max_val"
      "max_val"                        -> "max_val"
    """
    return demangle_path(symbol, hint)[-1]


def is_runtime_boilerplate(symbol: str, hint: str | None = None) -> bool:
    """
    True for functions the compiler or standard library added, which must
    not count as student code: Rust panic/bounds-check helpers, __rust_*
    allocator shims, monomorphized core::/std:: generics, LLVM intrinsics.
    """
    raw = symbol.strip('"')
    full_path = "::".join(demangle_path(raw, hint))
    if raw.startswith(("_ZN", "_R")) and full_path.startswith(RUST_STD_PREFIXES):
        return True
    if raw.startswith("_R") and rust_v0_crate(raw) in RUST_STD_CRATES:
        return True
    if raw.startswith(CPP_STD_PREFIXES):
        return True
    lowered = (raw + " " + full_path).lower()
    return any(marker in lowered for marker in RUNTIME_NAME_MARKERS)


def is_runtime_call(raw_line: str) -> bool:
    """
    True if an instruction calls a runtime helper (e.g. a Rust panic on a
    failed bounds check). Such calls are removed from the opcode stream so
    C and Rust versions of the same algorithm line up.
    """
    match = re.search(r"\b(?:call|invoke)\b[^@]*@([-\w$.]+|\"[^\"]+\")", raw_line)
    return bool(match) and is_runtime_boilerplate(match.group(1))


# =====================================================================
# FUNCTIONALITY 2: Panic-Guard Removal (Rust bounds checks)
# =====================================================================
def remove_panic_guards(blocks: list) -> list:
    """
    Rust protects every a[i] with a bounds check that C does not have:

        bb3:
          %_14 = icmp ult i64 %_12, %a.1        <- guard compare
          br i1 %_14, label %bb4, label %panic1 <- guard branch
        panic1:
          unreachable                           <- (panic call already removed)

    This function:
      1. deletes blocks that only contain `unreachable` (dead panic blocks),
      2. rewrites `br i1 %c, label %ok, label %panic` into `br label %ok`,
      3. deletes the guard compare `%c = icmp ...` if nothing else uses it.
    Works on ORIGINAL labels, so it must run before canonicalize_function().
    """
    dead = {bb.original_label for bb in blocks
            if [ins.opcode for ins in bb.instructions] == ["unreachable"]}
    if not dead:
        return blocks

    kept = [bb for bb in blocks if bb.original_label not in dead]
    for bb in kept:
        term = bb.terminator()
        if term is None or term.opcode != "br":
            continue
        match = re.match(r"br i1 (%[-\w$.]+), label %([-\w$.]+), label %([-\w$.]+)$",
                         term.raw_line)
        if not match:
            continue
        cond, true_label, false_label = match.groups()
        if true_label in dead and false_label not in dead:
            survivor = false_label
        elif false_label in dead and true_label not in dead:
            survivor = true_label
        else:
            continue
        term.raw_line = f"br label %{survivor}"
        # drop the guard compare if the branch was its only user
        users = [ins for b in kept for ins in b.instructions
                 if re.search(re.escape(cond) + r"\b", ins.raw_line)]
        if len(users) == 1:   # only its own definition remains
            bb.instructions = [ins for ins in bb.instructions
                               if not ins.raw_line.startswith(cond + " =")]
    return kept


# =====================================================================
# FUNCTIONALITY 2: Straight-Line Block Merging
# =====================================================================
UNCONDITIONAL_BR = re.compile(r"^br label %([-\w$.]+|\"[^\"]+\")$")
ANY_LABEL_REF = re.compile(r"label %([-\w$.]+|\"[^\"]+\")")


def merge_straight_line_blocks(blocks: list) -> list:
    """
    Merge block B into block A when:
        A ends with `br label %B` (an unconditional jump), and
        A is B's only predecessor.
    The `br` is removed and B's instructions are appended to A.

    Why: these chains carry no control-flow meaning. clang -O0 emits empty
    "br label %next" blocks for `for` loops, and Rust leaves them behind
    after remove_panic_guards(). Merging makes `for` vs `while` and C vs
    Rust produce the same block structure.
    Works on ORIGINAL labels, so it must run before canonicalize_function().
    """
    changed = True
    while changed:
        changed = False
        predecessors: dict[str, int] = {}
        for bb in blocks:
            term = bb.terminator()
            if term is not None:
                for target in ANY_LABEL_REF.findall(term.raw_line):
                    target = target.strip('"')
                    predecessors[target] = predecessors.get(target, 0) + 1

        by_label = {bb.original_label: bb for bb in blocks}
        for a in blocks:
            term = a.terminator()
            match = UNCONDITIONAL_BR.match(term.raw_line) if term else None
            if not match:
                continue
            target = match.group(1).strip('"')
            b = by_label.get(target)
            if b is None or b is a or b is blocks[0] or predecessors.get(target) != 1:
                continue
            a.instructions = a.instructions[:-1] + b.instructions
            blocks = [bb for bb in blocks if bb is not b]
            changed = True
            break
    return blocks
