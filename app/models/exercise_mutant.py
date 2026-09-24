from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ExerciseMutant(Base):
    """A copy of the reference solution with exactly one line broken.

    Used by P2 for mutation-testing student tests and as the Ciel trap bank.
    """

    __tablename__ = "exercise_mutants"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(Text)
    bug_line: Mapped[int] = mapped_column(Integer)  # 1-based
    bug_type: Mapped[str] = mapped_column(String(32))
    note_vi: Mapped[str] = mapped_column(Text, default="")
    note_en: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
