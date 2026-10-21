"""
Functionality 8: command-line interface.

    irprint scan <directory> [--k 3] [--threshold 0.8] [--json-out report.json] [--db]
    irprint serve [--host 127.0.0.1] [--port 8000]
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from irprint.compiler_wrapper import available_compilers
from irprint.db.schema import DEFAULT_DB_URL
from irprint.pipeline import scan_directory
from irprint.similarity import DEFAULT_THRESHOLD


@click.group()
def main() -> None:
    """IRprint: plagiarism detection on LLVM IR."""


# =====================================================================
# FUNCTIONALITY 8: Batch CLI Scan Command
# =====================================================================
@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--k", "k", default=3, show_default=True, type=click.IntRange(2, 5),
              help="k-gram size used for scoring.")
@click.option("--threshold", default=DEFAULT_THRESHOLD, show_default=True,
              help="Hybrid score at or above which a pair is flagged.")
@click.option("--opt-level", default="O0", show_default=True,
              type=click.Choice(["O0", "O1", "O2", "O3"]),
              help="Optimization level (IRprint's canonical mode is O0).")
@click.option("--json-out", type=click.Path(dir_okay=False), default=None,
              help="Write the full report as JSON to this file.")
@click.option("--db/--no-db", "use_db", default=False, show_default=True,
              help="Also save the scan to the SQLite database for the dashboard.")
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def scan(directory: str, k: int, threshold: float, opt_level: str,
         json_out: str | None, use_db: bool, db_url: str) -> None:
    """Scan a directory of submissions and print suspicious function pairs."""
    report = scan_directory(directory, k=k, threshold=threshold, opt_level=opt_level,
                            db_url=db_url if use_db else None)

    click.echo(f"Scanned {len(report.submissions)} submission(s) in {directory} "
               f"(k={k}, threshold={threshold}, -{opt_level})")
    for sub in report.submissions:
        status = "ok" if sub.compile_result.success else "FAILED"
        detail = (f"{len(sub.functions)} function(s)" if sub.compile_result.success
                  else sub.compile_result.error.splitlines()[0][:100])
        click.echo(f"  [{status:6}] {sub.name:40} {sub.compile_result.language:6} {detail}")

    click.echo("")
    if not report.flagged:
        click.echo("No pairs flagged.")
    else:
        click.echo(f"{len(report.flagged)} flagged pair(s):")
        click.echo(f"  {'hybrid':>6} {'dice':>6} {'cfg':>5}  pair")
        for c in report.flagged:
            click.echo(f"  {c.hybrid_score:6.3f} {c.dice:6.3f} {str(c.cfg_match):>5}  "
                       f"{c.file_a}:{c.func_a}  <->  {c.file_b}:{c.func_b}")

    if json_out:
        Path(json_out).write_text(json.dumps(report.to_dict(), indent=2))
        click.echo(f"\nJSON report written to {json_out}")
    if report.scan_id:
        click.echo(f"Saved to database as scan {report.scan_id}")


# =====================================================================
# FUNCTIONALITY 8: Dashboard Server Command
# =====================================================================
@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def serve(host: str, port: int, db_url: str) -> None:
    """Start the instructor dashboard (FastAPI + uvicorn)."""
    import os

    import uvicorn

    os.environ["IRPRINT_DB_URL"] = db_url
    click.echo(f"IRprint dashboard on http://{host}:{port}")
    uvicorn.run("irprint.api.main:app", host=host, port=port)


@main.command()
def doctor() -> None:
    """Show which compilers IRprint can find on this machine."""
    for language, path in available_compilers().items():
        click.echo(f"  {language:6} {path or 'NOT FOUND'}")


if __name__ == "__main__":
    main()
