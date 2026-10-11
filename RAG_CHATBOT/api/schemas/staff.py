from pydantic import BaseModel, EmailStr, Field


class StaffLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class StaffProfile(BaseModel):
    email: EmailStr
    name: str
    role: str
    metrics: list[str]


class StaffLogoutResponse(BaseModel):
    detail: str