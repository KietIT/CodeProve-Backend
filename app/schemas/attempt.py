from datetime import datetime

from pydantic import BaseModel


class CreateAttemptIn(BaseModel):
    exercise_code: str


class AttemptOut(BaseModel):
    attempt_id: int
    started_at: datetime


class AttemptState(BaseModel):
    id: int
    exercise_code: str
    status: str
    score: float | None
    latest_code: str | None


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
