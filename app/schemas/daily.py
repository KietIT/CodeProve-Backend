from pydantic import BaseModel


class DailyResult(BaseModel):
    correct: bool
    tier: str
    buggy_line: int
    explanation: str
    hints_used: int
    time_taken_seconds: int


class DailyChallengeOut(BaseModel):
    challenge_number: int
    prompt_title: str
    buggy_code: str
    already_played: bool
    result: DailyResult | None = None


class DailyAttemptIn(BaseModel):
    selected_line: int
    hints_used: int = 0
    time_taken_seconds: int


class DailyAttemptOut(BaseModel):
    correct: bool
    tier: str
    buggy_line: int
    explanation: str
    streak: int | None = None


class ClaimHistoryItem(BaseModel):
    date: str
    selected_line: int
    hints_used: int = 0
    time_taken_seconds: int = 0


class ClaimStreakIn(BaseModel):
    history: list[ClaimHistoryItem]


class ClaimStreakOut(BaseModel):
    streak: int
