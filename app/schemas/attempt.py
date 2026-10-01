from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.mentor import CielQuota

MAX_REASON_CHARS = 500  # the one-sentence "why" of the debug locate step


class CreateAttemptIn(BaseModel):
    exercise_code: str


class AttemptOut(BaseModel):
    attempt_id: int
    started_at: datetime


class DebugState(BaseModel):
    """Locate step of a debug exercise (P2.2); null on other exercises."""
    located: bool
    hints_used: int
    hints: list[str]


class AttemptState(BaseModel):
    id: int
    exercise_code: str
    status: str
    score: float | None
    latest_code: str | None
    debug: DebugState | None = None
    tests: "TestsState | None" = None
    ciel: CielQuota | None = None  # P3.6


class StudentTestIn(BaseModel):
    """One student-written test (P2.3): an input expression and the value it should give."""
    category: Literal["happy", "boundary", "edge", "error"]
    input: str = Field(min_length=1, max_length=300)
    expected: str = Field(max_length=300)
    why: str = Field(default="", max_length=200)


class StudentTestsIn(BaseModel):
    tests: list[StudentTestIn] = Field(max_length=10)


class TestsState(BaseModel):
    __test__ = False  # not a pytest test class
    enabled: bool
    required: bool  # junior/senior: tests count towards Testing even when missing
    tests: list[StudentTestIn]


class CheckOut(BaseModel):
    status: Literal["valid", "wrong_expected", "error"]
    reason: str | None = None


class OwnRunIn(BaseModel):
    source_code: str = Field(max_length=20000)


class LocateIn(BaseModel):
    lines: list[int] = Field(default_factory=list)
    reason: str = Field(default="", max_length=MAX_REASON_CHARS)
    skipped: bool = False


class HintOut(BaseModel):
    step: int
    text: str


class SnapshotIn(BaseModel):
    version: int
    source_code: str


class RunIn(BaseModel):
    source_code: str
    run_tests: bool = True


class RunCase(BaseModel):
    name: str
    passed: bool
    stdout: str = ""
    error: str | None = None


class RunResult(BaseModel):
    passed: int
    total: int
    coverage: float
    cases: list[RunCase]
    runtime_error: str | None = None


# AttemptState refers to TestsState, defined after it.
AttemptState.model_rebuild()
