from __future__ import annotations

from pydantic import BaseModel


class LoginPayload(BaseModel):
    email: str
    password: str


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str
