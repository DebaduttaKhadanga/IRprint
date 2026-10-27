import json
import shutil

from click.testing import CliRunner
from conftest import FIXTURES, requires_clang, requires_rustc

from irprint.cli import main
from irprint.pipeline import best_match, process_file, scan_directory


@requires_clang
def test_renamed_copy_scores_perfectly():
    a = process_file(FIXTURES / "max_a.c")
    b = process_file(FIXTURES / "max_b_renamed.c")
    match = best_match(a, b, k=3)
    assert match.dice == 1.0
    assert match.cfg_match
    assert match.hybrid_score == 1.0
    assert match.flagged


@requires_clang
def test_unrelated_code_is_not_flagged():
    a = process_file(FIXTURES / "max_a.c")
    c = process_file(FIXTURES / "unrelated.c")
    match = best_match(a, c, k=3)
    assert match is not None
    assert not match.flagged


@requires_clang
@requires_rustc
def test_cross_language_pair_has_same_cfg():
    c = process_file(FIXTURES / "max_a.c")
    r = process_file(FIXTURES / "max_rust.rs")
    assert [f.name for f in r.functions] == ["max_val"]
    match = best_match(c, r, k=3)
    assert match.cfg_match
    assert match.cfg_a.as_tuple() == match.cfg_b.as_tuple()
    assert match.dice > 0.5


@requires_clang
@requires_rustc
def test_scan_directory_with_database(tmp_path):
    for f in FIXTURES.iterdir():
        shutil.copy(f, tmp_path / f.name)
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    report = scan_directory(tmp_path, k=3, db_url=db_url)

    assert len(report.submissions) == 4
    assert all(s.compile_result.success for s in report.submissions)
    names = {(c.file_a, c.file_b) for c in report.flagged}
    assert ("max_a.c", "max_b_renamed.c") in names
    assert report.scan_id is not None

    from irprint.db import crud
    flagged = crud.get_comparisons(db_url, report.scan_id, flagged_only=True)
    assert flagged
    pair = crud.get_comparison(db_url, flagged[0]["id"])
    assert "define @" in pair["ir_a"]
    assert crud.set_verdict(db_url, pair["id"], "confirmed")
    assert crud.get_comparison(db_url, pair["id"])["instructor_verdict"] == "confirmed"


@requires_clang
def test_cli_scan_writes_json(tmp_path):
    out = tmp_path / "report.json"
    result = CliRunner().invoke(main, ["scan", str(FIXTURES), "--json-out", str(out)])
    assert result.exit_code == 0, result.output
    assert "flagged pair" in result.output
    data = json.loads(out.read_text())
    assert data["flagged_pairs"]
    assert len(data["matrix"]) == len(data["labels"])


@requires_clang
def test_web_dashboard_flow(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("IRPRINT_DB_URL", f"sqlite:///{tmp_path / 'web.db'}")
    from irprint.api.main import app
    client = TestClient(app)

    assert "No scans yet" in client.get("/").text
    files = [("files", (f.name, f.read_bytes(), "text/plain"))
             for f in sorted(FIXTURES.glob("*.c"))]
    response = client.post("/scan", files=files, follow_redirects=True)
    assert response.status_code == 200
    assert "heat-map" in response.text

    latest = client.get("/api/scan/latest").json()
    assert latest["flagged"]
    pair_id = latest["flagged"][0]["id"]
    detail = client.get(f"/pair/{pair_id}")
    assert detail.status_code == 200 and "Side-by-side" in detail.text

    client.post(f"/pair/{pair_id}/verdict", data={"verdict": "false_positive"})
    assert "false_positive" in client.get(f"/pair/{pair_id}").text
    assert client.post(f"/pair/{pair_id}/verdict", data={"verdict": "bogus"}).status_code == 400
