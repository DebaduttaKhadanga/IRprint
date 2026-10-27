"""
Functionality 8: SQLite tables (SQLAlchemy 2.x declarative style).

    Submission 1 ── * FunctionRecord
    FunctionRecord 2 ── * ComparisonRecord   (function A and function B)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DEFAULT_DB_URL = "sqlite:///data/irprint.db"
VERDICTS = ("pending", "confirmed", "false_positive", "needs_discussion")


class Base(DeclarativeBase):
    pass


# =====================================================================
# FUNCTIONALITY 8: SQLite Persistence Schema
# =====================================================================
class Submission(Base):
    """One uploaded / scanned source file."""
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[str] = mapped_column(String(36), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    language: Mapped[str] = mapped_column(String(16))
    compiled: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc))

    functions: Mapped[list["FunctionRecord"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan")


class FunctionRecord(Base):
    """One function extracted from a submission, with its normalized IR."""
    __tablename__ = "functions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    name: Mapped[str] = mapped_column(String(256))
    ir_text: Mapped[str] = mapped_column(Text)          # normalized IR for the diff view
    num_blocks: Mapped[int] = mapped_column(Integer)
    num_edges: Mapped[int] = mapped_column(Integer)
    loop_depth: Mapped[int] = mapped_column(Integer)
    opcode_count: Mapped[int] = mapped_column(Integer)

    submission: Mapped[Submission] = relationship(back_populates="functions")


class ComparisonRecord(Base):
    """A compared function pair, its scores, and the instructor's verdict."""
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[str] = mapped_column(String(36), index=True)
    function_a_id: Mapped[int] = mapped_column(ForeignKey("functions.id"))
    function_b_id: Mapped[int] = mapped_column(ForeignKey("functions.id"))
    k: Mapped[int] = mapped_column(Integer)
    dice: Mapped[float] = mapped_column(Float)
    jaccard: Mapped[float] = mapped_column(Float)
    cosine: Mapped[float] = mapped_column(Float)
    cfg_match: Mapped[bool] = mapped_column(Boolean)
    hybrid_score: Mapped[float] = mapped_column(Float)
    flagged: Mapped[bool] = mapped_column(Boolean)
    instructor_verdict: Mapped[str] = mapped_column(String(32), default="pending")

    function_a: Mapped[FunctionRecord] = relationship(foreign_keys=[function_a_id])
    function_b: Mapped[FunctionRecord] = relationship(foreign_keys=[function_b_id])


def make_session_factory(db_url: str = DEFAULT_DB_URL) -> sessionmaker:
    """Create the database file and tables if needed; return a Session maker."""
    if db_url.startswith("sqlite:///"):
        from pathlib import Path
        Path(db_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
