from __future__ import annotations

from fastapi import HTTPException, Request

from tradingagents.trade_feedback import (
    create_trade_record as create_trade_record_file,
    generate_trade_review as generate_trade_review_file,
    get_trade_feedback_payload as get_trade_feedback_payload_file,
    get_trade_record as get_trade_record_file,
    list_trade_records as list_trade_records_file,
    list_trade_reviews as list_trade_reviews_file,
    save_trade_review as save_trade_review_file,
    update_trade_record as update_trade_record_file,
)
from web.backend import access, analysis_limits, app_config, auth, trade_entries
from web.backend.schemas.trades import (
    TradeRecordCreatePayload,
    TradeRecordUpdatePayload,
    TradeReviewCreatePayload,
    TradeReviewSavePayload,
)
from web.backend.services.config import (
    get_provider_availability,
    hydrate_provider_credentials,
)


def translate_trade_feedback_error(exc: Exception) -> HTTPException:
    if isinstance(exc, analysis_limits.WeeklyUsageLimitExceeded):
        return HTTPException(status_code=429, detail=str(exc))
    detail = str(exc)
    status_code = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)


def record_journal_usage(db, user: auth.User) -> None:
    analysis_limits.record_module_usage(db, user, module="journal")


def sync_trade_entry_metadata(db, record: dict, owner_user_id: str) -> None:
    reviews = list_trade_reviews_file(record["trade_id"], reports_dir=app_config.REPORTS_DIR)
    trade_entries.upsert_trade_entry(
        db,
        record,
        owner_user_id=owner_user_id,
        reports_dir=app_config.REPORTS_DIR,
        reviews=reviews,
    )


def load_owner_scoped_trade_records(
    db,
    owner_user_id: str,
    *,
    ticker: str | None = None,
) -> list[dict]:
    records: list[dict] = []
    for entry in trade_entries.list_trade_entries_for_owner(
        db,
        owner_user_id,
        ticker=ticker,
    ):
        try:
            records.append(get_trade_record_file(entry.trade_id, reports_dir=app_config.REPORTS_DIR))
        except ValueError:
            continue
    return records


def list_trades(ticker: str | None = None, request: Request | None = None) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                return load_owner_scoped_trade_records(db, user.id, ticker=ticker)
        return list_trade_records_file(ticker=ticker, reports_dir=app_config.REPORTS_DIR)
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def create_trade(
    payload: TradeRecordCreatePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                record_journal_usage(db, user)
                record = create_trade_record_file(
                    payload.model_dump(),
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_entry_metadata(db, record, user.id)
                return record
        return create_trade_record_file(payload.model_dump(), reports_dir=app_config.REPORTS_DIR)
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def get_trade(trade_id: str, request: Request | None = None) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                return {
                    "record": get_trade_record_file(trade_id, reports_dir=app_config.REPORTS_DIR),
                    "reviews": list_trade_reviews_file(trade_id, reports_dir=app_config.REPORTS_DIR),
                }
        return {
            "record": get_trade_record_file(trade_id, reports_dir=app_config.REPORTS_DIR),
            "reviews": list_trade_reviews_file(trade_id, reports_dir=app_config.REPORTS_DIR),
        }
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def update_trade(
    trade_id: str,
    payload: TradeRecordUpdatePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                record_journal_usage(db, user)
                record = update_trade_record_file(
                    trade_id,
                    payload.model_dump(exclude_unset=True),
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_entry_metadata(db, record, user.id)
                return record
        return update_trade_record_file(
            trade_id,
            payload.model_dump(exclude_unset=True),
            reports_dir=app_config.REPORTS_DIR,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def get_trade_reviews(trade_id: str, request: Request | None = None) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                return list_trade_reviews_file(trade_id, reports_dir=app_config.REPORTS_DIR)
        return list_trade_reviews_file(trade_id, reports_dir=app_config.REPORTS_DIR)
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def create_trade_review(
    trade_id: str,
    payload: TradeReviewCreatePayload,
    request: Request | None = None,
) -> dict:
    hydrate_provider_credentials(payload.llm_provider)
    provider_availability = get_provider_availability(payload.llm_provider)
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )

    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                record_journal_usage(db, user)
                review = generate_trade_review_file(
                    trade_id,
                    review_type=payload.review_type,
                    llm_provider=payload.llm_provider,
                    model=payload.model,
                    output_language=payload.output_language,
                    google_thinking_level=payload.google_thinking_level,
                    openai_reasoning_effort=payload.openai_reasoning_effort,
                    analysis_date=payload.analysis_date,
                    analysis_references=(
                        payload.model_dump()["analysis_references"]
                        if payload.analysis_references is not None
                        else None
                    ),
                    reports_dir=app_config.REPORTS_DIR,
                )
                record = get_trade_record_file(trade_id, reports_dir=app_config.REPORTS_DIR)
                sync_trade_entry_metadata(db, record, user.id)
                return review
        return generate_trade_review_file(
            trade_id,
            review_type=payload.review_type,
            llm_provider=payload.llm_provider,
            model=payload.model,
            output_language=payload.output_language,
            google_thinking_level=payload.google_thinking_level,
            openai_reasoning_effort=payload.openai_reasoning_effort,
            analysis_date=payload.analysis_date,
            analysis_references=(
                payload.model_dump()["analysis_references"]
                if payload.analysis_references is not None
                else None
            ),
            reports_dir=app_config.REPORTS_DIR,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def save_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewSavePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(db, trade_id, user.id)
                record_journal_usage(db, user)
                review = save_trade_review_file(
                    trade_id,
                    review_type=review_type,
                    payload=payload.model_dump(
                        exclude={"analysis_date", "analysis_references"}
                    ),
                    analysis_date=payload.analysis_date,
                    analysis_references=(
                        payload.model_dump()["analysis_references"]
                        if payload.analysis_references is not None
                        else None
                    ),
                    reports_dir=app_config.REPORTS_DIR,
                )
                record = get_trade_record_file(trade_id, reports_dir=app_config.REPORTS_DIR)
                sync_trade_entry_metadata(db, record, user.id)
                return review
        return save_trade_review_file(
            trade_id,
            review_type=review_type,
            payload=payload.model_dump(
                exclude={"analysis_date", "analysis_references"}
            ),
            analysis_date=payload.analysis_date,
            analysis_references=(
                payload.model_dump()["analysis_references"]
                if payload.analysis_references is not None
                else None
            ),
            reports_dir=app_config.REPORTS_DIR,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def get_ticker_trade_feedback(
    ticker: str,
    *,
    limit: int = 3,
    analysis_date: str | None = None,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                visible_trade_ids = trade_entries.list_visible_trade_ids(
                    db,
                    user.id,
                    ticker=ticker,
                )
                return get_trade_feedback_payload_file(
                    ticker,
                    reports_dir=app_config.REPORTS_DIR,
                    limit=limit,
                    analysis_date=analysis_date,
                    visible_trade_ids=visible_trade_ids,
                )
        return get_trade_feedback_payload_file(
            ticker,
            reports_dir=app_config.REPORTS_DIR,
            limit=limit,
            analysis_date=analysis_date,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc
