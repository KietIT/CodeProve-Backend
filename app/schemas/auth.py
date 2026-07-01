from pydantic import BaseModel, Field, field_validator


def normalize_email(v: str) -> str:
    email = v.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Enter a valid email address")
    return email


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2)
    email: str
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return normalize_email(v)


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return normalize_email(v)


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
