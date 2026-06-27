from pydantic import BaseModel, Field


class EventIn(BaseModel):
    type: str
    ts: int
    payload: dict = Field(default_factory=dict)
    integrity_flags: list[str] = Field(default_factory=list)


class EventsIn(BaseModel):
    events: list[EventIn]
