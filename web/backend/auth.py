from __future__ import annotations

import hashlib
import logging
import os
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator, Literal, Sequence

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, create_engine, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from web.backend.runtime import task_store

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(PROJECT_ENV_FILE)

AuthMode = Literal["disabled", "optional", "required"]

DEFAULT_SESSION_COOKIE_NAME = "tradingagents_session"
DEFAULT_SESSION_TTL_HOURS = 24 * 7
DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME = "Administrator"
VALID_COOKIE_SAMESITE = {"lax", "strict", "none"}
VALID_AUTH_MODES = {"disabled", "optional", "required"}
MIN_PASSWORD_LENGTH = 8
LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

_PASSWORD_HASHER = PasswordHasher()
_ENGINE_LOCK = threading.Lock()
_ENGINE: Engine | None = None
_ENGINE_URL: str | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
_LOGIN_FAILURE_LOCK = threading.Lock()
_LOGIN_FAILURES: dict[str, list[float]] = {}
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_positive_int(value: str | None, default: int, field_name: str) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"{field_name} must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{field_name} must be greater than zero")
    return parsed


def _normalize_database_url(value: str | None) -> str | None:
    if value is None:
        return None
    raw_value = value.strip()
    if not raw_value:
        return None
    if raw_value.startswith("postgres://"):
        return raw_value.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_value.startswith("postgresql://"):
        return raw_value.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_value


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _require_text(value: str | None, field_name: str) -> str:
    if value is None or not value.strip():
        raise AuthValidationError(f"{field_name} is required")
    return value.strip()


def normalize_email(value: str | None) -> str:
    candidate = _require_text(value, "email").lower()
    if "@" not in candidate or candidate.startswith("@") or candidate.endswith("@"):
        raise AuthValidationError("email must look like a valid address")
    return candidate


def normalize_password(value: str | None, *, field_name: str = "password") -> str:
    candidate = _require_text(value, field_name)
    if len(candidate) < MIN_PASSWORD_LENGTH:
        raise AuthValidationError(
            f"{field_name} must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return candidate


def hash_password(password: str) -> str:
    normalized = normalize_password(password)
    return _PASSWORD_HASHER.hash(normalized)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _login_rate_limit_keys(email: str | None, ip_address: str | None) -> tuple[str, str, str]:
    normalized_email = str(email or "").strip().lower() or "<missing>"
    normalized_ip = str(ip_address or "").strip() or "<unknown>"
    return (
        f"ip:{normalized_ip}",
        f"email:{normalized_email}",
        f"pair:{normalized_ip}:{normalized_email}",
    )


def ensure_login_allowed(email: str | None, ip_address: str | None) -> None:
    keys = _login_rate_limit_keys(email, ip_address)
    now = time.monotonic()
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    redis_client = _login_failure_redis_client()
    if redis_client is not None:
        for key in keys:
            redis_key = f"tradingagents:auth:failures:{key}"
            redis_client.zremrangebyscore(redis_key, 0, cutoff)
            if int(redis_client.zcard(redis_key) or 0) >= LOGIN_FAILURE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed login attempts. Try again later.",
                )
        return
    with _LOGIN_FAILURE_LOCK:
        for key in keys:
            failures = [value for value in _LOGIN_FAILURES.get(key, []) if value >= cutoff]
            _LOGIN_FAILURES[key] = failures
            if len(failures) >= LOGIN_FAILURE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed login attempts. Try again later.",
                )


def record_login_failure(email: str | None, ip_address: str | None) -> None:
    keys = _login_rate_limit_keys(email, ip_address)
    now = time.monotonic()
    cutoff = now - LOGIN_FAILURE_WINDOW_SECONDS
    redis_client = _login_failure_redis_client()
    if redis_client is not None:
        for key in keys:
            redis_key = f"tradingagents:auth:failures:{key}"
            redis_client.zremrangebyscore(redis_key, 0, cutoff)
            redis_client.zadd(redis_key, {str(now): now})
            redis_client.expire(redis_key, LOGIN_FAILURE_WINDOW_SECONDS)
        return
    with _LOGIN_FAILURE_LOCK:
        for key in keys:
            failures = [value for value in _LOGIN_FAILURES.get(key, []) if value >= cutoff]
            failures.append(now)
            _LOGIN_FAILURES[key] = failures


def clear_login_failures(email: str | None, ip_address: str | None) -> None:
    _ip_key, email_key, pair_key = _login_rate_limit_keys(email, ip_address)
    redis_client = _login_failure_redis_client()
    if redis_client is not None:
        redis_client.delete(
            f"tradingagents:auth:failures:{email_key}",
            f"tradingagents:auth:failures:{pair_key}",
        )
        return
    with _LOGIN_FAILURE_LOCK:
        _LOGIN_FAILURES.pop(email_key, None)
        _LOGIN_FAILURES.pop(pair_key, None)


def _login_failure_redis_client():
    if not task_store.redis_task_backend_enabled():
        return None
    store = task_store.get_task_store()
    return getattr(store, "client", None)


class AuthError(Exception):
    """Base class for auth/service errors."""


class AuthDisabledError(AuthError):
    pass


class AuthValidationError(AuthError):
    pass


class AuthConflictError(AuthError):
    pass


class AuthNotFoundError(AuthError):
    pass


class AuthPermissionError(AuthError):
    pass


class Base(DeclarativeBase):
    pass


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role_status", "role", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.VIEWER.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE.value)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_token_hash", "token_hash", unique=True),
        Index("ix_auth_sessions_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    user: Mapped[User] = relationship(back_populates="sessions")


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    mode: AuthMode
    database_url: str | None
    session_cookie_name: str
    session_ttl_hours: int
    session_cookie_secure: bool
    session_cookie_samesite: Literal["lax", "strict", "none"]
    bootstrap_admin_email: str | None
    bootstrap_admin_password: str | None
    bootstrap_admin_display_name: str


def get_auth_settings() -> AuthSettings:
    raw_enabled = _env_bool("AUTH_ENABLED", False)
    raw_mode = os.environ.get("AUTH_MODE", "required").strip().lower()
    if raw_mode not in VALID_AUTH_MODES:
        raise RuntimeError(
            "AUTH_MODE must be one of disabled, optional, or required"
        )

    enabled = raw_enabled and raw_mode != "disabled"
    effective_mode: AuthMode = "disabled" if not enabled else raw_mode  # type: ignore[assignment]
    cookie_samesite = os.environ.get("SESSION_COOKIE_SAMESITE", "lax").strip().lower()
    if cookie_samesite not in VALID_COOKIE_SAMESITE:
        raise RuntimeError("SESSION_COOKIE_SAMESITE must be one of lax, strict, or none")

    bootstrap_email = os.environ.get("AUTH_BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_password = os.environ.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_display_name = (
        os.environ.get("AUTH_BOOTSTRAP_ADMIN_DISPLAY_NAME", DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME).strip()
        or DEFAULT_BOOTSTRAP_ADMIN_DISPLAY_NAME
    )

    return AuthSettings(
        enabled=enabled,
        mode=effective_mode,
        database_url=_normalize_database_url(os.environ.get("DATABASE_URL")),
        session_cookie_name=os.environ.get("SESSION_COOKIE_NAME", DEFAULT_SESSION_COOKIE_NAME).strip()
        or DEFAULT_SESSION_COOKIE_NAME,
        session_ttl_hours=_coerce_positive_int(
            os.environ.get("SESSION_TTL_HOURS"),
            DEFAULT_SESSION_TTL_HOURS,
            "SESSION_TTL_HOURS",
        ),
        session_cookie_secure=_env_bool("SESSION_COOKIE_SECURE", False),
        session_cookie_samesite=cookie_samesite,  # type: ignore[arg-type]
        bootstrap_admin_email=bootstrap_email.strip().lower() if bootstrap_email and bootstrap_email.strip() else None,
        bootstrap_admin_password=bootstrap_password.strip() if bootstrap_password and bootstrap_password.strip() else None,
        bootstrap_admin_display_name=bootstrap_display_name,
    )


def auth_enabled() -> bool:
    return get_auth_settings().enabled


def auth_mode() -> AuthMode:
    return get_auth_settings().mode


def _create_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, connect_args=connect_args)


def get_engine(settings: AuthSettings | None = None) -> Engine:
    resolved_settings = settings or get_auth_settings()
    if not resolved_settings.enabled:
        raise AuthDisabledError("Auth is disabled")
    if not resolved_settings.database_url:
        raise RuntimeError("DATABASE_URL is required when auth is enabled")

    normalized_url = resolved_settings.database_url
    global _ENGINE
    global _ENGINE_URL
    global _SESSION_FACTORY
    with _ENGINE_LOCK:
        if _ENGINE is None or _ENGINE_URL != normalized_url:
            if _ENGINE is not None:
                _ENGINE.dispose()
            _ENGINE = _create_engine(normalized_url)
            _ENGINE_URL = normalized_url
            _SESSION_FACTORY = sessionmaker(_ENGINE, autoflush=False, expire_on_commit=False)
        return _ENGINE


def get_session_factory(settings: AuthSettings | None = None) -> sessionmaker[Session]:
    resolved_settings = settings or get_auth_settings()
    if not resolved_settings.enabled:
        raise AuthDisabledError("Auth is disabled")
    get_engine(resolved_settings)
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


def reset_runtime_state() -> None:
    global _ENGINE
    global _ENGINE_URL
    global _SESSION_FACTORY
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None
        _ENGINE_URL = None
        _SESSION_FACTORY = None
    with _LOGIN_FAILURE_LOCK:
        _LOGIN_FAILURES.clear()


def create_all_for_testing() -> None:
    from web.backend import asset_entries, report_metadata, screener_runs, trade_entries  # noqa: F401

    settings = get_auth_settings()
    engine = get_engine(settings)
    Base.metadata.create_all(engine)


def _ensure_auth_tables_exist(settings: AuthSettings) -> None:
    engine = get_engine(settings)
    inspector = inspect(engine)
    required_tables = ("users", "auth_sessions")
    missing_tables = [table_name for table_name in required_tables if not inspector.has_table(table_name)]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            f"Auth is enabled but the following tables are missing: {joined}. "
            "Run `alembic -c web/backend/alembic.ini upgrade head` before starting the backend."
        )


@contextmanager
def db_session() -> Iterator[Session]:
    settings = get_auth_settings()
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def serialize_user(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "last_login_at": _serialize_datetime(user.last_login_at),
        "created_at": _serialize_datetime(user.created_at),
        "updated_at": _serialize_datetime(user.updated_at),
    }


def build_auth_state_payload(user: User | None) -> dict[str, object]:
    settings = get_auth_settings()
    return {
        "enabled": settings.enabled,
        "mode": settings.mode,
        "authenticated": user is not None,
        "user": serialize_user(user) if user is not None else None,
    }


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = normalize_email(email)
    return db.scalar(select(User).where(User.email == normalized_email))


def get_user_by_id(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AuthNotFoundError(f"User '{user_id}' not found")
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.asc(), User.email.asc())))


def _normalize_role(value: UserRole | str | None, field_name: str = "role") -> str:
    if isinstance(value, UserRole):
        return value.value
    candidate = _require_text(str(value) if value is not None else None, field_name).lower()
    try:
        return UserRole(candidate).value
    except ValueError as exc:
        raise AuthValidationError(f"{field_name} must be one of admin, operator, or viewer") from exc


def _normalize_status(value: UserStatus | str | None, field_name: str = "status") -> str:
    if isinstance(value, UserStatus):
        return value.value
    candidate = _require_text(str(value) if value is not None else None, field_name).lower()
    try:
        return UserStatus(candidate).value
    except ValueError as exc:
        raise AuthValidationError(f"{field_name} must be one of active or disabled") from exc


def _active_admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN.value,
                User.status == UserStatus.ACTIVE.value,
            )
        )
        or 0
    )


def _ensure_not_last_active_admin(
    db: Session,
    user: User,
    *,
    next_role: str | None = None,
    next_status: str | None = None,
    deleting: bool = False,
) -> None:
    is_active_admin = (
        user.role == UserRole.ADMIN.value and user.status == UserStatus.ACTIVE.value
    )
    if not is_active_admin:
        return

    effective_role = next_role if next_role is not None else user.role
    effective_status = next_status if next_status is not None else user.status
    remains_active_admin = (
        not deleting
        and effective_role == UserRole.ADMIN.value
        and effective_status == UserStatus.ACTIVE.value
    )
    if remains_active_admin:
        return

    if _active_admin_count(db) <= 1:
        raise AuthConflictError("Cannot remove the last active admin user")


def create_user(
    db: Session,
    *,
    email: str,
    display_name: str | None,
    password: str,
    role: UserRole | str = UserRole.VIEWER.value,
    status: UserStatus | str = UserStatus.ACTIVE.value,
    must_change_password: bool = True,
) -> User:
    normalized_email = normalize_email(email)
    normalized_role = _normalize_role(role)
    normalized_status = _normalize_status(status)
    normalized_display_name = (
        display_name.strip() if display_name is not None and display_name.strip() else normalized_email
    )

    user = User(
        email=normalized_email,
        display_name=normalized_display_name,
        password_hash=hash_password(password),
        role=normalized_role,
        status=normalized_status,
        must_change_password=must_change_password,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise AuthConflictError(f"User '{normalized_email}' already exists") from exc
    return user


def update_user(
    db: Session,
    user_id: str,
    *,
    display_name: str | None = None,
    role: UserRole | str | None = None,
    status: UserStatus | str | None = None,
    must_change_password: bool | None = None,
) -> User:
    user = get_user_by_id(db, user_id)
    next_role = _normalize_role(role) if role is not None else None
    next_status = _normalize_status(status) if status is not None else None
    _ensure_not_last_active_admin(db, user, next_role=next_role, next_status=next_status)

    if display_name is not None:
        normalized_display_name = display_name.strip()
        if not normalized_display_name:
            raise AuthValidationError("display_name cannot be empty")
        user.display_name = normalized_display_name
    if next_role is not None:
        user.role = next_role
    if next_status is not None:
        user.status = next_status
    if must_change_password is not None:
        user.must_change_password = must_change_password
    user.updated_at = _utcnow()
    db.flush()
    return user


def revoke_all_user_sessions(db: Session, user: User, *, exclude_session_id: str | None = None) -> None:
    now = _utcnow()
    statement = select(AuthSession).where(
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
    )
    for auth_session in db.scalars(statement):
        if exclude_session_id is not None and auth_session.id == exclude_session_id:
            continue
        auth_session.revoked_at = now
        auth_session.updated_at = now


def delete_user(db: Session, user_id: str) -> None:
    user = get_user_by_id(db, user_id)
    _ensure_not_last_active_admin(db, user, deleting=True)
    revoke_all_user_sessions(db, user)
    db.delete(user)
    db.flush()


def reset_user_password(
    db: Session,
    user_id: str,
    *,
    new_password: str,
    must_change_password: bool = True,
) -> User:
    user = get_user_by_id(db, user_id)
    user.password_hash = hash_password(new_password)
    user.must_change_password = must_change_password
    user.updated_at = _utcnow()
    revoke_all_user_sessions(db, user)
    db.flush()
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(user.password_hash, password):
        raise AuthValidationError("Invalid email or password")
    if user.status != UserStatus.ACTIVE.value:
        raise AuthPermissionError("User account is disabled")
    return user


def create_user_session(
    db: Session,
    user: User,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    settings: AuthSettings | None = None,
) -> str:
    resolved_settings = settings or get_auth_settings()
    token = secrets.token_urlsafe(48)
    now = _utcnow()
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=_hash_session_token(token),
        expires_at=now + timedelta(hours=resolved_settings.session_ttl_hours),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    user.last_login_at = now
    user.updated_at = now
    db.add(auth_session)
    db.flush()
    return token


def revoke_session_token(db: Session, token: str | None) -> None:
    if not token:
        return
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == _hash_session_token(token))
    )
    if auth_session is None or auth_session.revoked_at is not None:
        return
    now = _utcnow()
    auth_session.revoked_at = now
    auth_session.updated_at = now
    db.flush()


def get_request_user(
    db: Session,
    request: Request,
    *,
    settings: AuthSettings | None = None,
) -> User | None:
    resolved_settings = settings or get_auth_settings()
    if not resolved_settings.enabled:
        return None

    session_token = request.cookies.get(resolved_settings.session_cookie_name)
    if not session_token:
        return None

    now = _utcnow()
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash_session_token(session_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if auth_session is None:
        return None

    user = auth_session.user
    if user.status != UserStatus.ACTIVE.value:
        auth_session.revoked_at = now
        auth_session.updated_at = now
        db.flush()
        return None

    auth_session.last_seen_at = now
    auth_session.updated_at = now
    db.flush()
    return user


def require_request_user(db: Session, request: Request) -> User:
    user = get_request_user(db, request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def enforce_password_change_completed(user: User, request: Request) -> None:
    if not user.must_change_password:
        return
    allowed_paths = {
        "/api/auth/me",
        "/api/auth/logout",
        "/api/auth/change-password",
    }
    if request.url.path in allowed_paths:
        return
    raise HTTPException(status_code=403, detail="Password change required")


def require_request_user_role(
    db: Session,
    request: Request,
    allowed_roles: Sequence[str],
) -> User:
    user = require_request_user(db, request)
    enforce_password_change_completed(user, request)
    if user.role not in allowed_roles:
        logger.warning(
            "permission denied user_id=%s role=%s path=%s allowed_roles=%s",
            user.id,
            user.role,
            request.url.path,
            ",".join(allowed_roles),
        )
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


def change_user_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
    current_session_id: str | None = None,
) -> None:
    if not verify_password(user.password_hash, current_password):
        raise AuthValidationError("Current password is incorrect")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.updated_at = _utcnow()
    revoke_all_user_sessions(db, user, exclude_session_id=current_session_id)
    db.flush()


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_auth_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_auth_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


def current_session_token(request: Request) -> str | None:
    settings = get_auth_settings()
    return request.cookies.get(settings.session_cookie_name)


def current_session_record(db: Session, request: Request) -> AuthSession | None:
    settings = get_auth_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == _hash_session_token(token),
            AuthSession.revoked_at.is_(None),
        )
    )


def ensure_bootstrap_admin(db: Session, settings: AuthSettings | None = None) -> User | None:
    resolved_settings = settings or get_auth_settings()
    user_count = int(db.scalar(select(func.count(User.id))) or 0)
    if user_count > 0:
        return None

    if not resolved_settings.bootstrap_admin_email or not resolved_settings.bootstrap_admin_password:
        raise RuntimeError(
            "Auth is enabled but no users exist. Set AUTH_BOOTSTRAP_ADMIN_EMAIL and "
            "AUTH_BOOTSTRAP_ADMIN_PASSWORD, or run `python -m web.backend.devops.bootstrap_admin`."
        )

    user = create_user(
        db,
        email=resolved_settings.bootstrap_admin_email,
        display_name=resolved_settings.bootstrap_admin_display_name,
        password=resolved_settings.bootstrap_admin_password,
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
        must_change_password=True,
    )
    logger.info("bootstrap admin created user_id=%s email=%s", user.id, user.email)
    return user


def bootstrap_admin_from_env() -> bool:
    settings = get_auth_settings()
    if not settings.enabled:
        return False
    _ensure_auth_tables_exist(settings)
    with db_session() as db:
        created_user = ensure_bootstrap_admin(db, settings)
        return created_user is not None


def initialize_auth_runtime() -> None:
    settings = get_auth_settings()
    if not settings.enabled:
        return
    _ensure_auth_tables_exist(settings)
    with db_session() as db:
        ensure_bootstrap_admin(db, settings)


def enforce_authenticated_api_access(request: Request) -> None:
    settings = get_auth_settings()
    if not settings.enabled or settings.mode != "required":
        return
    with db_session() as db:
        user = require_request_user(db, request)
        enforce_password_change_completed(user, request)


def enforce_admin_api_access(request: Request) -> None:
    settings = get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=409, detail="Auth is disabled")
    with db_session() as db:
        require_request_user_role(db, request, (UserRole.ADMIN.value,))


def enforce_operator_api_access(request: Request) -> None:
    settings = get_auth_settings()
    if not settings.enabled:
        return
    with db_session() as db:
        require_request_user_role(
            db,
            request,
            (UserRole.ADMIN.value, UserRole.OPERATOR.value),
        )
