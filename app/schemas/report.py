from pydantic import BaseModel


class ExplainAnswer(BaseModel):
    question: str
    answer: str


class ExplainBackIn(BaseModel):
    answers: list[ExplainAnswer]


class ReportOut(BaseModel):
    overall: float
    tier: str
    axes: dict[str, float | None]
    axes_pct: dict[str, float | None]
    feedback: dict
    integrity_status: str
    timeline: list[dict]
