"""
The end-to-end pipeline. Everything else (CLI, web API, experiments) calls
into this file.

    source file
      -> compile_to_ir()          compiler_wrapper.py   CompileResult
      -> parse_ir()               ir_parser.py          list[Function]
      -> canonicalize_function()  ir_parser.py          Function (bb0, bb1, ...)
      -> build_birthmark()        birthmark.py          Birthmark (+ CFGSignature)
      -> compare_birthmarks()     similarity.py         ComparisonResult
      -> save_scan()  (optional)  db/crud.py            rows in SQLite
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

from irprint.birthmark import DEFAULT_KS, build_birthmark
from irprint.compiler_wrapper import compile_to_ir, detect_language
from irprint.ir_parser import canonicalize_function, parse_ir
from irprint.models import Birthmark, CompileResult, ComparisonResult, Function
from irprint.similarity import DEFAULT_THRESHOLD, compare_birthmarks

# Functions with fewer opcodes than this (tiny getters, empty main) are not
# compared: almost any two tiny functions look alike.
MIN_OPCODES = 10


@dataclass
class SubmissionResult:
    """Everything we learned about one submitted source file."""
    name: str                       # display name (path relative to scan root)
    compile_result: CompileResult
    functions: list[Function] = field(default_factory=list)
    birthmarks: list[Birthmark] = field(default_factory=list)


@dataclass
class ScanReport:
    """Result of scanning a whole directory of submissions."""
    root: str
    k: int
    threshold: float
    opt_level: str
    submissions: list[SubmissionResult]
    best_pairs: list[ComparisonResult]      # best function pair for each file pair
    flagged: list[ComparisonResult]         # every function pair over threshold
    matrix: list[list[float]]               # file x file best hybrid score (heat-map)
    scan_id: str | None = None              # set when saved to the database

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "root": self.root,
            "k": self.k,
            "threshold": self.threshold,
            "opt_level": self.opt_level,
            "submissions": [
                {"name": s.name, "language": s.compile_result.language,
                 "compiled": s.compile_result.success,
                 "error": s.compile_result.error,
                 "functions": [f.name for f in s.functions]}
                for s in self.submissions
            ],
            "labels": [s.name for s in self.submissions],
            "matrix": [[round(v, 4) for v in row] for row in self.matrix],
            "flagged_pairs": [c.to_dict() for c in self.flagged],
            "best_pairs": [c.to_dict() for c in self.best_pairs],
        }


def process_file(path: str | Path, opt_level: str = "O0",
                 ks: tuple[int, ...] = DEFAULT_KS, display_name: str | None = None
                 ) -> SubmissionResult:
    """Compile -> parse -> canonicalize -> birthmark, for one file."""
    path = Path(path)
    result = compile_to_ir(path, opt_level=opt_level)
    submission = SubmissionResult(name=display_name or path.name, compile_result=result)
    if not result.success:
        return submission

    for func in parse_ir(result.ir_text, source_path=submission.name,
                         language=result.language):
        canonicalize_function(func)
        submission.functions.append(func)
        submission.birthmarks.append(build_birthmark(func, ks))
    return submission


def comparable(birthmarks: list[Birthmark], min_opcodes: int = MIN_OPCODES) -> list[Birthmark]:
    return [b for b in birthmarks if b.opcode_count >= min_opcodes]


def compare_submissions(a: SubmissionResult, b: SubmissionResult, k: int = 3,
                        threshold: float = DEFAULT_THRESHOLD,
                        min_opcodes: int = MIN_OPCODES) -> list[ComparisonResult]:
    """Compare every function of `a` with every function of `b`."""
    return [compare_birthmarks(x, y, k, threshold)
            for x in comparable(a.birthmarks, min_opcodes)
            for y in comparable(b.birthmarks, min_opcodes)]


def best_match(a: SubmissionResult, b: SubmissionResult, k: int = 3,
               threshold: float = DEFAULT_THRESHOLD, score: str = "hybrid_score",
               min_opcodes: int = MIN_OPCODES) -> ComparisonResult | None:
    """The single most similar function pair between two submissions."""
    results = compare_submissions(a, b, k, threshold, min_opcodes)
    return max(results, key=lambda c: getattr(c, score)) if results else None


def collect_source_files(directory: str | Path) -> list[Path]:
    """All supported source files below `directory`, sorted for stable output."""
    directory = Path(directory)
    return sorted(p for p in directory.rglob("*")
                  if p.is_file() and detect_language(p)
                  and not any(part.startswith(".") for part in p.relative_to(directory).parts))


# =====================================================================
# FUNCTIONALITY 8: Batch Scan Pipeline (used by CLI + dashboard)
# =====================================================================
def scan_directory(directory: str | Path, k: int = 3,
                   threshold: float = DEFAULT_THRESHOLD, opt_level: str = "O0",
                   db_url: str | None = None) -> ScanReport:
    """
    Scan every submission in a directory and compare all pairs of files.

    db_url is OPTIONAL. Without it everything stays in memory (CLI and
    experiments). With it, the report is also written to SQLite so the
    dashboard can show it and store instructor verdicts.
    """
    directory = Path(directory)
    files = collect_source_files(directory)
    submissions = [process_file(f, opt_level, display_name=str(f.relative_to(directory)))
                   for f in files]

    n = len(submissions)
    matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    best_pairs: list[ComparisonResult] = []
    flagged: list[ComparisonResult] = []

    for i, j in itertools.combinations(range(n), 2):
        results = compare_submissions(submissions[i], submissions[j], k, threshold)
        if not results:
            continue
        best = max(results, key=lambda c: c.hybrid_score)
        best_pairs.append(best)
        matrix[i][j] = matrix[j][i] = best.hybrid_score
        flagged.extend(r for r in results if r.flagged)

    flagged.sort(key=lambda c: c.hybrid_score, reverse=True)
    report = ScanReport(root=str(directory), k=k, threshold=threshold,
                        opt_level=opt_level, submissions=submissions,
                        best_pairs=best_pairs, flagged=flagged, matrix=matrix)

    if db_url:
        # Imported here so the core pipeline never needs SQLAlchemy.
        from irprint.db.crud import save_scan
        report.scan_id = save_scan(db_url, report)
    return report
