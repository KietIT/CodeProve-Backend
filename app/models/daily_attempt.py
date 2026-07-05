from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DailyAttempt(Base):
    __tablename__ = "daily_attempts"
    __table_args__ = (UniqueConstraint("user_id", "challenge_date", name="uq_daily_attempt_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_date: Mapped[date] = mapped_column(Date, index=True)
    selected_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(16), nullable=True)  # green|yellow|red
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
