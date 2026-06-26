from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str


class AuthOut(BaseModel):
    user: UserOut
    access_token: str
