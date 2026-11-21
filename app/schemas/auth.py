import re

from pydantic import AliasChoices, BaseModel, Field, field_validator

# Vietnamese mobile numbers after the 2018 renumbering: 10 digits, 0 + network prefix 3/5/7/8/9.
_VN_MOBILE = re.compile(r"0[35789]\d{8}")
_PHONE_SEPARATORS = re.compile(r"[\s.\-()]")


def normalize_email(v: str) -> str:
    email = v.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Enter a valid email address")
    return email


def normalize_phone(v: str) -> str:
    """Return a Vietnamese mobile number in canonical 0xxxxxxxxx form.

    Accepts 0912345678, +84912345678, 84912345678 and the same with spaces, dots, dashes or brackets.
    """
    digits = _PHONE_SEPARATORS.sub("", v.strip())
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    if not _VN_MOBILE.fullmatch(digits):
        raise ValueError("Enter a valid Vietnamese phone number")
    return digits


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2)
    email: str
    phone: str
    password: str = Field(min_length=8)
    # P3.7: the signup form's required "I accept the Privacy Policy" checkbox. No default on purpose:
    # pydantic does not run validators on defaults, so a missing field must fail as missing.
    accept_privacy: bool

    @field_validator("accept_privacy")
    @classmethod
    def must_accept_privacy(cls, v: bool) -> bool:
        if not v:
            raise ValueError("the privacy policy must be accepted to sign up")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class LoginIn(BaseModel):
    """Staff login (admin panel): internal email only."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return normalize_email(v)


class UserLoginIn(BaseModel):
    """Learner login: the ID is an email or a Vietnamese phone number.

    Sent as `identifier`; `email` is still accepted so older clients keep working.
    """

    identifier: str = Field(validation_alias=AliasChoices("identifier", "email"))
    password: str

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if "@" in v:
            return normalize_email(v)
        try:
            return normalize_phone(v)
        except ValueError:
            raise ValueError("Enter a valid email or Vietnamese phone number") from None

    @property
    def is_email(self) -> bool:
        return "@" in self.identifier


class UpdateMeIn(BaseModel):
    # Both optional so the same endpoint handles a name edit, an avatar upload,
    # or both. Avatar is a data URL (base64) or empty string to clear it.
    full_name: str | None = Field(default=None, min_length=2)
    avatar: str | None = None
    # Lets accounts without a phone (older or Google sign-ups) add one, so they can log in with it.
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return None if v is None else normalize_phone(v)


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None = None
    avatar: str | None = None


class AuthOut(BaseModel):
    user: UserOut
    access_token: str
