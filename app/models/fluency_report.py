from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FluencyReport(Base):
    __tablename__ = "fluency_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), unique=True, index=True)
    understanding_score: Mapped[float] = mapped_column(Float)
    hypothesis_score: Mapped[float] = mapped_column(Float)
    prompt_score: Mapped[float] = mapped_column(Float)
    verification_score: Mapped[float] = mapped_column(Float)
    testing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    debugging_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation_score: Mapped[float] = mapped_column(Float)
    overall_score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
