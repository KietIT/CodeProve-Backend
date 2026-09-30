from datetime import datetime

from pydantic import BaseModel, Field

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
