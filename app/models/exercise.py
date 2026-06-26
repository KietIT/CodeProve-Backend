from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
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
    language: Mapped[str] = mapped_column(String(32), default="python")
    acceptance: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    starter_code: Mapped[str] = mapped_column(Text, default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    domain_keywords: Mapped[list] = mapped_column(JSONB, default=list)
    reference_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    buggy_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_trap: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
