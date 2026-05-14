from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LoginPayload(BaseModel):
    account: Optional[str] = None
    email: Optional[str] = None
    password: str

    @property
    def login_identifier(self) -> str:
        if self.account is not None and self.account.strip():
            return self.account
        return self.email or ""


class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str
