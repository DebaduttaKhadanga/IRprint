"""
Core data structures passed between every stage of the IRprint pipeline.

Pipeline handoff order (see flow.md):
    CompileResult -> Function / BasicBlock / Instruction -> CFGSignature
    -> Birthmark -> ComparisonResult

All classes are plain dataclasses so they are easy to print, inspect and
explain during the viva.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Stage 1 output: what the compiler wrapper returns for one source file.
# ---------------------------------------------------------------------------
@dataclass
class CompileResult:
    source_path: str          # path of the student's source file
    language: str             # "c", "cpp", "rust" or "swift"
    success: bool             # True if the compiler produced IR
    ir_text: str = ""         # raw textual LLVM IR (.ll contents)
    error: str = ""           # compiler stderr / reason for failure
    command: list[str] = field(default_factory=list)  # exact command we ran
    opt_level: str = "O0"     # optimization level used


# ---------------------------------------------------------------------------
# Stage 2 output: parsed LLVM IR.
# ---------------------------------------------------------------------------
@dataclass
class Instruction:
    opcode: str               # e.g. "load", "icmp", "br", "call"
    raw_line: str             # original IR text, kept for the diff viewer


@dataclass
class BasicBlock:
    label: str                            # canonical label after renaming (bb0, bb1, ...)
    instructions: list[Instruction] = field(default_factory=list)
    original_label: str = ""              # label as printed by the compiler (e.g. "5", "bb3")

    def terminator(self) -> Instruction | None:
        """The last instruction of a block is its terminator (br, ret, switch...)."""
        return self.instructions[-1] if self.instructions else None


@dataclass
class Function:
    name: str                             # demangled, human-readable name
    raw_name: str                         # symbol as it appears in the IR
    source_path: str = ""
    language: str = ""
    blocks: list[BasicBlock] = field(default_factory=list)
    # original label -> canonical label. Filled by canonicalize_function().
    label_map: dict[str, str] = field(default_factory=dict)

    def opcode_sequence(self) -> list[str]:
        """Linear list of opcodes in block order. This is what birthmarks use."""
        return [ins.opcode for bb in self.blocks for ins in bb.instructions]

    def instruction_count(self) -> int:
        return sum(len(bb.instructions) for bb in self.blocks)


# ---------------------------------------------------------------------------
# Stage 3 output: structural fingerprints of one function.
# ---------------------------------------------------------------------------
@dataclass
class CFGSignature:
    num_basic_blocks: int
    num_edges: int
    max_loop_depth: int       # approximated by the number of back-edges

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.num_basic_blocks, self.num_edges, self.max_loop_depth)


@dataclass
class Birthmark:
    function_name: str
    source_path: str
    language: str
    kgrams: dict[int, set[tuple[str, ...]]]   # k -> set of opcode k-grams
    cfg: CFGSignature
    opcode_count: int
    normalized_ir: str = ""                   # canonical IR text for the diff view


# ---------------------------------------------------------------------------
# Stage 4 output: result of comparing two birthmarks.
# ---------------------------------------------------------------------------
@dataclass
class ComparisonResult:
    file_a: str
    func_a: str
    file_b: str
    func_b: str
    k: int
    dice: float               # raw Dice (the k-gram-only score)
    jaccard: float
    cosine: float
    cfg_a: CFGSignature
    cfg_b: CFGSignature
    cfg_match: bool
    hybrid_score: float       # Addition D: Dice adjusted by CFG agreement
    flagged: bool = False

    def to_dict(self) -> dict:
        return {
            "file_a": self.file_a,
            "func_a": self.func_a,
            "file_b": self.file_b,
            "func_b": self.func_b,
            "k": self.k,
            "dice": round(self.dice, 4),
            "jaccard": round(self.jaccard, 4),
            "cosine": round(self.cosine, 4),
            "cfg_a": list(self.cfg_a.as_tuple()),
            "cfg_b": list(self.cfg_b.as_tuple()),
            "cfg_match": self.cfg_match,
            "hybrid_score": round(self.hybrid_score, 4),
            "flagged": self.flagged,
        }
