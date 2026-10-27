"""
Shared helpers for the four experiment scripts (Additions A-D).

Kept deliberately small: corpus paths, a cached "compile + birthmark"
loader, a source-token baseline, and table/JSON output.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:          # lets `python experiments/x.py` work
    sys.path.insert(0, str(ROOT))

from irprint.pipeline import (MIN_OPCODES, SubmissionResult, best_match,  # noqa: E402
                              process_file)

CORPUS = ROOT / "experiments" / "corpus"
C_DIR = CORPUS / "algorithms" / "c"
RUST_DIR = CORPUS / "algorithms" / "rust"
PARAPHRASE_DIR = CORPUS / "llm_paraphrase"
RESULTS_DIR = ROOT / "experiments" / "results"
KS = (2, 3, 4, 5)
PARAPHRASED = ("max_value", "array_sum", "gcd", "binary_search", "bubble_sort", "count_primes")

_cache: dict[tuple[str, str], SubmissionResult] = {}


def load(path: Path, opt_level: str = "O0") -> SubmissionResult:
    """Compile + parse + birthmark a file once, then reuse it."""
    key = (str(path), opt_level)
    if key not in _cache:
        result = process_file(path, opt_level=opt_level, display_name=path.name)
        if not result.compile_result.success:
            raise RuntimeError(f"could not compile {path}: {result.compile_result.error}")
        _cache[key] = result
    return _cache[key]


def pair_scores(a: SubmissionResult, b: SubmissionResult, k: int,
                min_opcodes: int = MIN_OPCODES) -> dict:
    """
    File-level scores for a pair of submissions at one k:
      dice    - best raw Dice over all function pairs   (k-gram-only)
      hybrid  - best hybrid score over all function pairs (k-gram + CFG)
    The two maxima are taken separately, so each method gets its own best pair.
    """
    by_dice = best_match(a, b, k, score="dice", min_opcodes=min_opcodes)
    by_hybrid = best_match(a, b, k, score="hybrid_score", min_opcodes=min_opcodes)
    return {"dice": by_dice.dice if by_dice else 0.0,
            "hybrid": by_hybrid.hybrid_score if by_hybrid else 0.0,
            "cfg_match": by_hybrid.cfg_match if by_hybrid else False}


# ---------------------------------------------------------------------------
# Baseline: MOSS/JPlag-style source-token k-grams (simplified re-implementation)
# ---------------------------------------------------------------------------
TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|\+=|-=|\+\+|--|->|::|&&|\|\||\S")
KEYWORDS = {
    "int", "long", "void", "char", "float", "double", "return", "if", "else",
    "for", "while", "break", "continue", "static", "struct", "unsigned",
    "fn", "let", "mut", "pub", "as", "loop", "usize", "i32", "i64", "u32",
    "bool", "true", "false", "match", "impl", "self",
}


def source_tokens(path: Path) -> list[str]:
    """Lexical tokens with identifiers -> ID and numbers -> NUM (keywords kept)."""
    text = path.read_text()
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    tokens = []
    for tok in TOKEN.findall(text):
        if tok in KEYWORDS:
            tokens.append(tok)
        elif tok[0].isdigit():
            tokens.append("NUM")
        elif tok[0].isalpha() or tok[0] == "_":
            tokens.append("ID")
        else:
            tokens.append(tok)
    return tokens


def token_dice(path_a: Path, path_b: Path, k: int) -> float:
    from irprint.birthmark import extract_kgrams
    from irprint.similarity import dice
    return dice(extract_kgrams(source_tokens(path_a), k),
                extract_kgrams(source_tokens(path_b), k))


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def print_table(headers: list[str], rows: list[list], title: str = "") -> None:
    if title:
        print(f"\n{title}")
    cells = [[f"{v:.3f}" if isinstance(v, float) else str(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))


def write_results(name: str, data: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{name}.json"
    out.write_text(json.dumps(data, indent=2))
    print(f"\nResults written to {out.relative_to(ROOT)}")
    return out


def auc(positives: list[float], negatives: list[float]) -> float:
    """
    Threshold-free ranking quality: probability that a random positive pair
    scores higher than a random negative pair (ties count half). 1.0 = perfect.
    """
    if not positives or not negatives:
        return 0.0
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0
               for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
