from pydantic import BaseModel


class MentorIn(BaseModel):
    message: str


class MentorOut(BaseModel):
    reply: str
    injected_error: bool


class HypothesisIn(BaseModel):
    text: str


class HypothesisOut(BaseModel):
    correct: bool
    note: str
