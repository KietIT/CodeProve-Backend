from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    # Player-facing text is stored bilingually: the challenge is generated
    # once per day for everyone, but the UI has a live VI/EN toggle.
    prompt_title_vi: Mapped[str] = mapped_column(String(255))
    prompt_title_en: Mapped[str] = mapped_column(String(255))
    buggy_code: Mapped[str] = mapped_column(Text)
    buggy_line: Mapped[int] = mapped_column(Integer)
    bug_category: Mapped[str] = mapped_column(String(64))
    hint_1_vi: Mapped[str] = mapped_column(Text)
    hint_1_en: Mapped[str] = mapped_column(Text)
    hint_2_vi: Mapped[str] = mapped_column(Text)
    hint_2_en: Mapped[str] = mapped_column(Text)
    explanation_vi: Mapped[str] = mapped_column(Text)
    explanation_en: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
