from pydantic import BaseModel, Field


class MentorIn(BaseModel):
    message: str
    # The student's current editor code, sent so Ciel can reason about what
    # they have written so far. Optional + capped to keep prompts bounded.
    code: str | None = Field(default=None, max_length=8000)


class MentorOut(BaseModel):
    reply: str
    injected_error: bool


class HypothesisIn(BaseModel):
    text: str


class HypothesisOut(BaseModel):
    correct: bool
    note: str
