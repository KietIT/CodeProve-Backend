from pydantic import BaseModel

from app.schemas.exercise import SkillTag


class Kpis(BaseModel):
    completed: int
    streak: int
    avg_score: float


class RadarPoint(BaseModel):
    name: str
    value: float | None  # 0..100; None = never observed in any report


class RecentItem(BaseModel):
    title: str
    meta: str
    status: str
    score: float | None
    ok: bool


class RecommendedItem(BaseModel):
    """A next exercise from the learner model (P3.4). The success chance is internal and not sent."""
    code: str
    title: str
    level: str
    kind: str
    skills: list[SkillTag]
    reason_skills: list[str]  # keys of `skills` that are among the student's weak skills; may be empty


class DashboardOut(BaseModel):
    kpis: Kpis
    radar: list[RadarPoint]
    trend: list[float]
    recent: list[RecentItem]
    recommended: list[RecommendedItem] = []
