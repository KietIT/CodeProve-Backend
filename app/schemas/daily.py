from pydantic import BaseModel, Field


class DailyResult(BaseModel):
    correct: bool
    tier: str
    buggy_line: int
    explanation_vi: str
    explanation_en: str
    hints_used: int
    time_taken_seconds: int


class DailyChallengeOut(BaseModel):
    challenge_number: int
    prompt_title_vi: str
    prompt_title_en: str
    buggy_code: str
    hint_1_vi: str
    hint_1_en: str
    hint_2_vi: str
    hint_2_en: str
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
    explanation_vi: str
    explanation_en: str
    streak: int | None = None


class ClaimHistoryItem(BaseModel):
    date: str
    selected_line: int
    hints_used: int = 0
    time_taken_seconds: int = 0


class ClaimStreakIn(BaseModel):
    history: list[ClaimHistoryItem] = Field(max_length=60)


class ClaimStreakOut(BaseModel):
    streak: int
