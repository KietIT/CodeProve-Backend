from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LearnerSkill(Base):
    """A student's Elo rating on one skill (P3.3). Derived data: learner.rebuild recomputes it from reports."""

    __tablename__ = "learner_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill", name="uq_learner_skill_user_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(40))  # key of content.skills.TAXONOMY
    rating: Mapped[float] = mapped_column(Float)
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # scored attempts that practised it
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
