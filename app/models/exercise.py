from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text, false, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # e.g. "CP-001"
    title: Mapped[str] = mapped_column(String(255))
    difficulty: Mapped[str] = mapped_column(String(16))   # Easy|Medium|Hard
    category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    learning_objective: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(16))         # fresher|junior|senior
    # "implement" = student writes the solution (starter is stripped to a stub);
    # "debug" = student must find/fix a flaw, so the buggy starter is shown as-is.
    kind: Mapped[str] = mapped_column(String(16), default="implement", server_default="implement")
    language: Mapped[str] = mapped_column(String(32), default="python")
    acceptance: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    starter_code: Mapped[str] = mapped_column(Text, default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    domain_keywords: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list)
    reference_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    buggy_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Debug exercises (P2.2), from the reviewed content file: {"regions": [[line, ...], ...] (1-based, starter
    # as served), "explanation_vi/en", "hint_vi/en"}. Never sent to the student before submit.
    debug_meta: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    # P2.3: the student writes tests (Tests tab). Set by content sync where the exercise's own tests
    # fit the student-test input rules (student_tests.safety).
    student_tests: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # P3.2: skills practised (keys of content.skills.TAXONOMY), from the reviewed content file.
    skills: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list,
                                              server_default="[]")
    verification_trap: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
