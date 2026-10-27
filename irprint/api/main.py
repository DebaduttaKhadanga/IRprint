"""
Functionality 8: FastAPI web server behind the instructor dashboard.

Routes
  GET  /                      dashboard: upload form, heat-map, flagged pairs
  POST /scan                  upload source files and scan them
  POST /scan/demo             scan the built-in demo class (no upload needed)
  GET  /api/scan/latest       latest scan as JSON (heat-map data + pairs)
  GET  /pair/{index}          pair inspector: scores, CFG, side-by-side IR
  POST /pair/{index}/verdict  instructor triage verdict
"""

from __future__ import annotations

import difflib
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from irprint.compiler_wrapper import detect_language
from irprint.db import crud
from irprint.db.schema import DEFAULT_DB_URL, VERDICTS
from irprint.pipeline import scan_directory
from irprint.similarity import DEFAULT_THRESHOLD

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DEMO_CLASS_DIR = PROJECT_ROOT / "experiments" / "corpus" / "class_demo"

app = FastAPI(title="IRprint Instructor Dashboard")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")
templates = Jinja2Templates(directory=DASHBOARD_DIR / "templates")


def db_url() -> str:
    return os.environ.get("IRPRINT_DB_URL", DEFAULT_DB_URL)


def latest_scan_payload() -> dict | None:
    """Everything the dashboard needs about the most recent scan."""
    url = db_url()
    scan_id = crud.latest_scan_id(url)
    if scan_id is None:
        return None
    submissions = crud.get_submissions(url, scan_id)
    comparisons = crud.get_comparisons(url, scan_id)
    labels = [s.filename for s in submissions]
    index_of = {name: i for i, name in enumerate(labels)}

    # heat-map: best hybrid score per file pair, plus which pair to open on click
    n = len(labels)
    matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    pair_ids = [[None] * n for _ in range(n)]
    for comp in comparisons:            # sorted best-first, so first hit wins
        i, j = index_of[comp["file_a"]], index_of[comp["file_b"]]
        if pair_ids[i][j] is None:
            matrix[i][j] = matrix[j][i] = round(comp["hybrid_score"], 4)
            pair_ids[i][j] = pair_ids[j][i] = comp["id"]

    return {
        "scan_id": scan_id,
        "labels": labels,
        "matrix": matrix,
        "pair_ids": pair_ids,
        "submissions": [{"name": s.filename, "language": s.language,
                         "compiled": s.compiled, "error": s.error} for s in submissions],
        "flagged": [c for c in comparisons if c["flagged"]],
        "threshold": DEFAULT_THRESHOLD,
    }


# =====================================================================
# FUNCTIONALITY 8: Dashboard Home (Class-Wide Similarity Heat-Map)
# =====================================================================
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html",
                                      {"scan": latest_scan_payload()})


@app.get("/api/scan/latest")
def api_latest_scan():
    payload = latest_scan_payload()
    if payload is None:
        return JSONResponse({"scan_id": None}, status_code=404)
    return payload


# =====================================================================
# FUNCTIONALITY 8: Batch Upload & Scan Endpoint
# =====================================================================
@app.post("/scan")
async def scan_upload(files: list[UploadFile] = File(...), k: int = Form(3),
                      threshold: float = Form(DEFAULT_THRESHOLD)):
    """Save uploaded files to a temp folder, scan them, persist, redirect home."""
    with tempfile.TemporaryDirectory(prefix="irprint_upload_") as workdir:
        saved = 0
        for upload in files:
            name = Path(upload.filename or "").name     # drop any client path
            if not name or detect_language(name) is None:
                continue
            with open(Path(workdir) / name, "wb") as out:
                shutil.copyfileobj(upload.file, out)
            saved += 1
        if saved < 2:
            raise HTTPException(400, "upload at least two .c/.cpp/.rs/.swift files")
        scan_directory(workdir, k=k, threshold=threshold, db_url=db_url())
    return RedirectResponse("/", status_code=303)


@app.post("/scan/demo")
def scan_demo():
    """Scan the built-in demo class so the dashboard can be shown offline."""
    scan_directory(DEMO_CLASS_DIR, db_url=db_url())
    return RedirectResponse("/", status_code=303)


# =====================================================================
# FUNCTIONALITY 8: Pair Inspector (Side-by-Side Normalized IR Diff)
# =====================================================================
def side_by_side_rows(ir_a: str, ir_b: str) -> list[dict]:
    """
    Align the two normalized IR listings line by line with difflib.
    Each row: {"left", "right", "tag"} where tag is "equal", "replace",
    "delete" (only on the left) or "insert" (only on the right).
    """
    left, right = ir_a.splitlines(), ir_b.splitlines()
    rows = []
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        span = max(i2 - i1, j2 - j1)
        for offset in range(span):
            rows.append({
                "left": left[i1 + offset] if i1 + offset < i2 else "",
                "right": right[j1 + offset] if j1 + offset < j2 else "",
                "tag": tag,
            })
    return rows


@app.get("/pair/{index}", response_class=HTMLResponse)
def pair_detail(request: Request, index: int):
    pair = crud.get_comparison(db_url(), index)
    if pair is None:
        raise HTTPException(404, "pair not found")
    rows = side_by_side_rows(pair["ir_a"], pair["ir_b"])
    return templates.TemplateResponse(request, "pair_detail.html",
                                      {"pair": pair, "rows": rows,
                                       "verdicts": VERDICTS[1:]})


# =====================================================================
# FUNCTIONALITY 8: Instructor Triage Workflow
# =====================================================================
@app.post("/pair/{index}/verdict")
def pair_verdict(index: int, verdict: str = Form(...)):
    if verdict not in VERDICTS:
        raise HTTPException(400, f"verdict must be one of {VERDICTS}")
    if not crud.set_verdict(db_url(), index, verdict):
        raise HTTPException(404, "pair not found")
    return RedirectResponse(f"/pair/{index}", status_code=303)
