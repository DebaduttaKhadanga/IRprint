"""
Functionality 8: create / read / update helpers for the dashboard database.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from irprint.db.schema import (VERDICTS, ComparisonRecord, FunctionRecord,
                               Submission, make_session_factory)

_session_factories: dict = {}


def get_session(db_url: str):
    """One sessionmaker per database URL, created lazily."""
    if db_url not in _session_factories:
        _session_factories[db_url] = make_session_factory(db_url)
    return _session_factories[db_url]()


# =====================================================================
# FUNCTIONALITY 8: Persist a Scan Report to SQLite
# =====================================================================
def save_scan(db_url: str, report) -> str:
    """
    Write a ScanReport (from pipeline.scan_directory) to the database.
    Stores every submission, every function's normalized IR, and the
    comparisons the dashboard shows (best pair per file pair + flagged).
    Returns the new scan_id.
    """
    scan_id = str(uuid.uuid4())
    with get_session(db_url) as session:
        function_ids: dict[tuple[str, str], FunctionRecord] = {}
        for sub in report.submissions:
            row = Submission(scan_id=scan_id, filename=sub.name,
                             language=sub.compile_result.language,
                             compiled=sub.compile_result.success,
                             error=sub.compile_result.error)
            for bm in sub.birthmarks:
                func_row = FunctionRecord(
                    name=bm.function_name, ir_text=bm.normalized_ir,
                    num_blocks=bm.cfg.num_basic_blocks, num_edges=bm.cfg.num_edges,
                    loop_depth=bm.cfg.max_loop_depth, opcode_count=bm.opcode_count)
                row.functions.append(func_row)
                function_ids[(sub.name, bm.function_name)] = func_row
            session.add(row)
        session.flush()   # assigns primary keys

        seen = set()
        for comp in report.best_pairs + report.flagged:
            key = (comp.file_a, comp.func_a, comp.file_b, comp.func_b)
            if key in seen:
                continue
            seen.add(key)
            session.add(ComparisonRecord(
                scan_id=scan_id,
                function_a_id=function_ids[(comp.file_a, comp.func_a)].id,
                function_b_id=function_ids[(comp.file_b, comp.func_b)].id,
                k=comp.k, dice=comp.dice, jaccard=comp.jaccard, cosine=comp.cosine,
                cfg_match=comp.cfg_match, hybrid_score=comp.hybrid_score,
                flagged=comp.flagged))
        session.commit()
    return scan_id


def latest_scan_id(db_url: str) -> str | None:
    with get_session(db_url) as session:
        row = session.execute(
            select(Submission).order_by(Submission.id.desc()).limit(1)).scalar_one_or_none()
        return row.scan_id if row else None


def get_submissions(db_url: str, scan_id: str) -> list[Submission]:
    with get_session(db_url) as session:
        return list(session.execute(
            select(Submission).where(Submission.scan_id == scan_id)
            .order_by(Submission.id)).scalars())


def get_comparisons(db_url: str, scan_id: str, flagged_only: bool = False) -> list[dict]:
    """Comparisons of one scan as plain dicts (file + function names included)."""
    with get_session(db_url) as session:
        query = select(ComparisonRecord).where(ComparisonRecord.scan_id == scan_id)
        if flagged_only:
            query = query.where(ComparisonRecord.flagged.is_(True))
        rows = session.execute(query.order_by(ComparisonRecord.hybrid_score.desc())).scalars()
        return [comparison_to_dict(r) for r in rows]


def get_comparison(db_url: str, comparison_id: int) -> dict | None:
    with get_session(db_url) as session:
        row = session.get(ComparisonRecord, comparison_id)
        return comparison_to_dict(row, include_ir=True) if row else None


def comparison_to_dict(row: ComparisonRecord, include_ir: bool = False) -> dict:
    fa, fb = row.function_a, row.function_b
    data = {
        "id": row.id, "scan_id": row.scan_id, "k": row.k,
        "file_a": fa.submission.filename, "func_a": fa.name,
        "file_b": fb.submission.filename, "func_b": fb.name,
        "dice": row.dice, "jaccard": row.jaccard, "cosine": row.cosine,
        "cfg_a": [fa.num_blocks, fa.num_edges, fa.loop_depth],
        "cfg_b": [fb.num_blocks, fb.num_edges, fb.loop_depth],
        "cfg_match": row.cfg_match, "hybrid_score": row.hybrid_score,
        "flagged": row.flagged, "instructor_verdict": row.instructor_verdict,
    }
    if include_ir:
        data["ir_a"] = fa.ir_text
        data["ir_b"] = fb.ir_text
    return data


# =====================================================================
# FUNCTIONALITY 8: Instructor Triage Verdict Update
# =====================================================================
def set_verdict(db_url: str, comparison_id: int, verdict: str) -> bool:
    """Store "confirmed", "false_positive" or "needs_discussion" for a pair."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    with get_session(db_url) as session:
        row = session.get(ComparisonRecord, comparison_id)
        if row is None:
            return False
        row.instructor_verdict = verdict
        session.commit()
        return True
