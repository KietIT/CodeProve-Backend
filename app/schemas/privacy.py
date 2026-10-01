from pydantic import BaseModel


class PrivacyOut(BaseModel):
    consented: bool  # accepted the current policy version
    version: str | None  # the version they accepted, if any
    current_version: str
    ai_personalization: bool


class ConsentIn(BaseModel):
    version: str  # must be the current version: the student accepts the text they were shown


class PrivacyUpdateIn(BaseModel):
    ai_personalization: bool
