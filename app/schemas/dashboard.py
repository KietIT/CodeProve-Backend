from pydantic import BaseModel


class Kpis(BaseModel):
    completed: int
    streak: int
    avg_score: float


class RadarPoint(BaseModel):
    name: str
    value: float  # 0..100


class RecentItem(BaseModel):
    title: str
    meta: str
    status: str
    score: float | None
    ok: bool


class DashboardOut(BaseModel):
    kpis: Kpis
    radar: list[RadarPoint]
    trend: list[float]
    recent: list[RecentItem]
