"""
Functionality 2 (part 2): a small line-oriented parser for textual LLVM IR.

Textual IR has a very regular shape, which is why plain regexes are enough:

    define dso_local i32 @max_val(ptr noundef %0, i32 noundef %1) {
      %3 = alloca ptr, align 8                 <- entry block (no label line)
      ...
      br label %5
    5:                                         <- label line starts a new block
      %6 = load i32, ptr %4, align 4
      ...
    }                                          <- end of function
"""

from __future__ import annotations

import re

from irprint.models import BasicBlock, Function, Instruction
from irprint.normalizer import (collect_demangle_hints, demangle_symbol,
                                is_runtime_boilerplate, is_runtime_call,
                                merge_straight_line_blocks,
                                remove_panic_guards, strip_debug_lines)

# An LLVM identifier: plain (letters, digits, $ . _ -) or quoted.
IDENT = r'(?:[-\w$.]+|"[^"]+")'

DEFINE_LINE = re.compile(r"^define\b.*?@(" + IDENT + r")\s*\(")
LABEL_LINE = re.compile(r"^(" + IDENT + r"):\s*$")
ASSIGNMENT = re.compile(r"^%" + IDENT + r"\s*=\s*")
BRANCH_TARGET = re.compile(r"label %(" + IDENT + r")")
TERMINATORS_WITH_TARGETS = ("br", "switch", "indirectbr", "invoke", "callbr")
CALL_PREFIXES = ("tail", "musttail", "notail")

# Name used for the entry block, which clang/rustc often leave unlabeled.
ENTRY_LABEL = "%entry"


# =====================================================================
# FUNCTIONALITY 2: Instruction Opcode Extraction (register canonicalization)
# =====================================================================
def extract_opcode(line: str) -> str:
    """
    Return the opcode of one instruction line.

        "%5 = load i32, ptr %4, align 4"   -> "load"
        "store i32 %1, ptr %3, align 4"    -> "store"
        "%7 = tail call i32 @foo(i32 %6)"  -> "call"
        "br i1 %9, label %10, label %12"   -> "br"

    Keeping only the opcode is how register names (%5, %x.addr, %_7 ...)
    are canonicalized away: two programs that differ only in variable
    names produce exactly the same opcode stream.
    """
    text = ASSIGNMENT.sub("", line.strip())
    words = text.split()
    if not words:
        return ""
    if words[0] in CALL_PREFIXES and len(words) > 1:
        return words[1]
    return words[0]


def _join_multiline_instructions(lines: list[str]) -> list[str]:
    """
    `switch` instructions span several lines:
        switch i32 %4, label %8 [
          i32 1, label %5
          i32 2, label %6
        ]
    Join them into one line so the rest of the parser can stay line-based.
    """
    joined, buffer = [], None
    for line in lines:
        if buffer is not None:
            buffer += " " + line.strip()
            if "]" in line:
                joined.append(buffer)
                buffer = None
        elif "[" in line and "]" not in line and ("switch" in line or "indirectbr" in line):
            buffer = line.rstrip()
        else:
            joined.append(line)
    if buffer is not None:
        joined.append(buffer)
    return joined


def _split_into_blocks(body_lines: list[str]) -> list[BasicBlock]:
    """Partition a function body into basic blocks on label lines."""
    blocks: list[BasicBlock] = []
    current = BasicBlock(label=ENTRY_LABEL, original_label=ENTRY_LABEL)
    for line in body_lines:
        stripped = line.strip()
        label_match = LABEL_LINE.match(stripped)
        if label_match:
            if current.instructions or current.original_label != ENTRY_LABEL:
                blocks.append(current)
            name = label_match.group(1).strip('"')
            current = BasicBlock(label=name, original_label=name)
            continue
        if is_runtime_call(stripped):
            continue    # e.g. call to core::panicking::panic_bounds_check
        current.instructions.append(Instruction(extract_opcode(stripped), stripped))
    if current.instructions:
        blocks.append(current)
    return blocks


# =====================================================================
# FUNCTIONALITY 2: Line-Oriented Function Parser
# =====================================================================
def parse_ir(ir_text: str, source_path: str = "", language: str = "",
             keep_runtime: bool = False) -> list[Function]:
    """
    Split an LLVM module into Function objects.

      1. collect_demangle_hints() reads rustc's "; crate::fn" comments.
      2. strip_debug_lines() removes metadata noise.
      3. Each `define ... @name(...) {` starts a function; `}` ends it.
      4. Compiler/runtime helpers (Rust panics, std generics) are skipped
         unless keep_runtime=True.
      5. Each body is split into BasicBlocks on label lines, Rust
         bounds-check guards are removed (remove_panic_guards), and
         trivial jump-only chains are merged (merge_straight_line_blocks).
    """
    functions: list[Function] = []
    hints = collect_demangle_hints(ir_text)
    lines = strip_debug_lines(ir_text).splitlines()

    i = 0
    while i < len(lines):
        match = DEFINE_LINE.match(lines[i])
        if not match:
            i += 1
            continue

        raw_name = match.group(1).strip('"')
        body: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() != "}":
            body.append(lines[i])
            i += 1
        i += 1  # skip the closing "}"

        hint = hints.get(raw_name)
        if not keep_runtime and is_runtime_boilerplate(raw_name, hint):
            continue

        func = Function(name=demangle_symbol(raw_name, hint), raw_name=raw_name,
                        source_path=source_path, language=language)
        blocks = _split_into_blocks(_join_multiline_instructions(body))
        blocks = remove_panic_guards(blocks)
        func.blocks = merge_straight_line_blocks(blocks)
        functions.append(func)
    return functions


def branch_targets(instruction: Instruction) -> list[str]:
    """
    Original labels a terminator can jump to.
        "br i1 %13, label %14, label %32" -> ["14", "32"]
        "ret i32 %33"                      -> []
    """
    if instruction.opcode not in TERMINATORS_WITH_TARGETS:
        return []
    return [t.strip('"') for t in BRANCH_TARGET.findall(instruction.raw_line)]


def reverse_postorder(blocks: list[BasicBlock]) -> list[BasicBlock]:
    """
    Order blocks by a depth-first walk from the entry block (reverse
    post-order). clang and rustc lay blocks out differently in the file;
    RPO gives one layout that depends only on the control-flow graph.
    Unreachable blocks (rare at -O0) are kept at the end in file order.
    """
    by_label = {bb.original_label: bb for bb in blocks}
    visited: set[str] = set()
    postorder: list[BasicBlock] = []

    def visit(bb: BasicBlock) -> None:
        # iterative DFS so huge functions cannot hit Python's recursion limit
        stack = [(bb, iter(branch_targets(bb.terminator()) if bb.terminator() else []))]
        visited.add(bb.original_label)
        while stack:
            node, successors = stack[-1]
            for label in successors:
                nxt = by_label.get(label)
                if nxt is not None and label not in visited:
                    visited.add(label)
                    stack.append((nxt, iter(branch_targets(nxt.terminator())
                                            if nxt.terminator() else [])))
                    break
            else:
                stack.pop()
                postorder.append(node)

    if blocks:
        visit(blocks[0])
    ordered = list(reversed(postorder))
    ordered += [bb for bb in blocks if bb.original_label not in visited]
    return ordered


# =====================================================================
# FUNCTIONALITY 2: Basic-Block Label Canonicalization
# =====================================================================
def canonicalize_function(func: Function) -> Function:
    """
    Rename basic-block labels to positional names bb0, bb1, bb2 ...

    Clang names blocks with numbers ("5:", "12:") and rustc uses names like
    "bb3:" or "start:". After this step both look the same.

      1. Blocks are first put in reverse post-order (reverse_postorder), so
         the numbering does not depend on how the compiler laid out the file.
      2. Block i is renamed to "bb<i>".

    IMPORTANT: the original labels are saved in func.label_map
    (original -> canonical) and in bb.original_label, because
    compute_cfg_signature() needs the ORIGINAL names to resolve the
    `label %X` targets written inside branch instructions.
    """
    for bb in func.blocks:
        if not bb.original_label:
            bb.original_label = bb.label
    func.blocks = reverse_postorder(func.blocks)
    func.label_map = {}
    for index, bb in enumerate(func.blocks):
        canonical = f"bb{index}"
        func.label_map[bb.original_label] = canonical
        bb.label = canonical
    return func


def normalized_ir_text(func: Function) -> str:
    """
    Pretty, canonical IR used by the dashboard diff view:
      - block labels become bb0, bb1, ...
      - virtual registers become %v0, %v1, ... in order of first use
      - only the student's function body is shown, metadata already gone
    """
    register_names: dict[str, str] = {}

    def rename_label(match: re.Match) -> str:
        original = match.group(1).strip('"')
        return "label %" + func.label_map.get(original, original)

    def rename_register(match: re.Match) -> str:
        name = match.group(0)
        if name not in register_names:
            register_names[name] = f"%v{len(register_names)}"
        return register_names[name]

    out_lines = [f"define @{func.name}"]
    for bb in func.blocks:
        out_lines.append(f"{bb.label}:")
        for ins in bb.instructions:
            text = re.sub(r"label %(" + IDENT + ")", rename_label, ins.raw_line)
            # rename %registers but leave the already-canonical %bbN labels alone
            text = re.sub(r"%(?!bb\d+\b)" + IDENT, rename_register, text)
            out_lines.append("  " + text)
    return "\n".join(out_lines)
