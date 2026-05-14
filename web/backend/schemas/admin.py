from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from web.backend import auth


class AdminUserCreatePayload(BaseModel):
    email: str
    username: Optional[str] = None
    display_name: str
    password: str
    role: auth.UserRole = auth.UserRole.VIEWER
    status: auth.UserStatus = auth.UserStatus.ACTIVE
    must_change_password: bool = True


class AdminUserUpdatePayload(BaseModel):
    username: Optional[str] = None
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
    hourly_limit: Optional[int] = Field(default=None, ge=0)


class AdminDataSourceRouteUpdatePayload(BaseModel):
    vendor_chain: list[str] = Field(min_length=1)


class AdminLLMProviderUpdatePayload(BaseModel):
    enabled: bool
    base_url: str
    daily_limit: Optional[int] = Field(default=None, ge=0)
    hourly_limit: Optional[int] = Field(default=None, ge=0)


class AdminLLMModelUpdatePayload(BaseModel):
    enabled: bool
    cost_tier: str
    visible_to_roles: list[auth.UserRole]
    daily_limit: Optional[int] = Field(default=None, ge=0)
    weekly_limit: Optional[int] = Field(default=None, ge=0)


class AdminLLMProfileUpdatePayload(BaseModel):
    enabled: bool
    default_for_roles: list[auth.UserRole] = Field(default_factory=list)


class AdminLLMProfileRoutePayload(BaseModel):
    provider: str
    quick_model: str
    deep_model: str


class AdminLLMProfileRoutesUpdatePayload(BaseModel):
    routes: list[AdminLLMProfileRoutePayload] = Field(min_length=1)


class AdminLLMModuleSettingUpdatePayload(BaseModel):
    enabled: bool
    model_profile: str
    output_language: str = "cn"
    custom_provider: Optional[str] = None
    custom_model: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    google_thinking_level: Optional[str] = None


class AdminLLMUiSettingUpdatePayload(BaseModel):
    enabled: bool


class SearchGlobalUpdatePayload(BaseModel):
    enabled: bool


class SearchProviderUpdatePayload(BaseModel):
    enabled: Optional[bool] = None
    monthly_free_quota: Optional[int] = Field(default=None, ge=0)
    monthly_hard_cap: Optional[int] = Field(default=None, ge=0)
