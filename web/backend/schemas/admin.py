from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from web.backend import auth


class AdminUserCreatePayload(BaseModel):
    email: str
    display_name: str
    password: str
    role: auth.UserRole = auth.UserRole.VIEWER
    status: auth.UserStatus = auth.UserStatus.ACTIVE
    must_change_password: bool = True


class AdminUserUpdatePayload(BaseModel):
    display_name: Optional[str] = None
    role: Optional[auth.UserRole] = None
    status: Optional[auth.UserStatus] = None
    must_change_password: Optional[bool] = None


class AdminUserResetPasswordPayload(BaseModel):
    new_password: str
    must_change_password: bool = True


class AdminAnalysisRoleLimitPayload(BaseModel):
    role: auth.UserRole
    weekly_limit: Optional[int] = Field(default=None, ge=0)


class AdminAnalysisLimitsUpdatePayload(BaseModel):
    limits: list[AdminAnalysisRoleLimitPayload]


class AdminDataSourceUpdatePayload(BaseModel):
    enabled: bool
    daily_limit: Optional[int] = Field(default=None, ge=0)
