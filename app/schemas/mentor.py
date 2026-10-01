from pydantic import BaseModel, Field


class CielQuota(BaseModel):
    """Ciel messages the student has left (P3.6)."""
    attempt_left: int
    day_left: int


class MentorIn(BaseModel):
    # Capped: every character is sent to the LLM (P3.6).
    message: str = Field(min_length=1, max_length=4000)
    # The student's current editor code, sent so Ciel can reason about what
    # they have written so far. Optional + capped to keep prompts bounded.
    code: str | None = Field(default=None, max_length=8000)


class MentorOut(BaseModel):
    # The injected-bug flag stays in the event log for scoring; exposing it here
    # would tell the student which reply is the trap.
    reply: str
    ciel: CielQuota | None = None


class HypothesisIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)  # stored capped at 2000 anyway


class HypothesisOut(BaseModel):
    correct: bool
    note: str
