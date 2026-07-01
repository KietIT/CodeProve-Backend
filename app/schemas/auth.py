from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UpdateMeIn(BaseModel):
    # Both optional so the same endpoint handles a name edit, an avatar upload,
    # or both. Avatar is a data URL (base64) or empty string to clear it.
    full_name: str | None = Field(default=None, min_length=2)
    avatar: str | None = None


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    avatar: str | None = None


class AuthOut(BaseModel):
    user: UserOut
    access_token: str
