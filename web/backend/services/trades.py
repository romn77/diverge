from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from diverge.trade_feedback import (
    create_trade_record as create_trade_record_file,
    get_trade_feedback_payload as get_trade_feedback_payload_file,
    get_trade_record as get_trade_record_file,
    list_trade_records as list_trade_records_file,
    list_trade_reviews as list_trade_reviews_file,
    save_trade_review as save_trade_review_file,
    update_trade_record as update_trade_record_file,
)
from diverge.trade_plans import (
    build_execution_trade_payload,
    build_trade_plan_snapshot,
    create_trade_plan as create_trade_plan_file,
    delete_trade_plan as delete_trade_plan_file,
    get_trade_plan as get_trade_plan_file,
    list_trade_plans as list_trade_plans_file,
    mark_trade_plan_executed as mark_trade_plan_executed_file,
    update_trade_plan as update_trade_plan_file,
    validate_plan_link,
)
from web.backend import (
    access,
    analysis_limits,
    app_config,
    audit,
    auth,
    trade_entries,
    trade_plan_entries,
)
from web.backend.schemas.trades import (
    TradePlanCreatePayload,
    TradePlanExecutePayload,
    TradePlanLinkPayload,
    TradePlanUpdatePayload,
    TradeRecordCreatePayload,
    TradeRecordUpdatePayload,
    TradeReviewGeneratePayload,
    TradeReviewSavePayload,
)
from web.backend.runtime import journal_review_tasks
from web.backend.services.preferences import preferred_output_language_from_request
from web.backend.services import trade_review_generation

logger = logging.getLogger(__name__)
AUTO_REVIEW_MODULE = trade_review_generation.AUTO_REVIEW_MODULE


def _external_news_enabled() -> bool:
    return trade_review_generation.external_news_enabled()


def translate_trade_feedback_error(exc: Exception) -> HTTPException:
    if isinstance(exc, analysis_limits.WeeklyUsageLimitExceeded):
        return HTTPException(status_code=429, detail=str(exc))
    detail = str(exc)
    status_code = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)


def record_journal_usage(db, user: auth.User) -> None:
    analysis_limits.record_module_usage(db, user, module="journal")


def sync_trade_entry_metadata(
    db, record: dict, owner_user_id: str, tenant_id: str | None = None
) -> None:
    reviews = list_trade_reviews_file(
        record["trade_id"], reports_dir=app_config.REPORTS_DIR
    )
    trade_entries.upsert_trade_entry(
        db,
        record,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        reports_dir=app_config.REPORTS_DIR,
        reviews=reviews,
    )


def sync_trade_plan_entry_metadata(
    db, plan: dict, owner_user_id: str, tenant_id: str | None = None
) -> None:
    trade_plan_entries.upsert_trade_plan_entry(
        db,
        plan,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        reports_dir=app_config.REPORTS_DIR,
    )


def _review_types_for_auto_generation(
    record: dict, existing_reviews: list[dict]
) -> list[str]:
    return trade_review_generation.review_types_for_auto_generation(
        record,
        existing_reviews,
    )


def _resolve_trade_review_model_setting(*, require_enabled: bool) -> dict | None:
    return trade_review_generation.resolve_trade_review_model_setting(
        require_enabled=require_enabled,
    )


def _ensure_trade_review_provider_available(model_setting: dict) -> None:
    trade_review_generation.ensure_trade_review_provider_available(model_setting)


def _generate_trade_review_with_model_setting(
    trade_id: str,
    review_type: str,
    model_setting: dict,
    *,
    analysis_date: str | None = None,
    analysis_references: list[dict] | None = None,
    output_language: str | None = None,
) -> dict:
    return trade_review_generation.generate_trade_review_with_model_setting(
        trade_id,
        review_type,
        model_setting,
        analysis_date=analysis_date,
        analysis_references=analysis_references,
        output_language=output_language,
    )


def generate_automatic_trade_reviews(
    record: dict,
    *,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
    output_language: str | None = None,
) -> list[dict]:
    return trade_review_generation.generate_automatic_trade_reviews(
        record,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
        output_language=output_language,
    )


def load_owner_scoped_trade_records(
    db,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
    ticker: str | None = None,
) -> list[dict]:
    records: list[dict] = []
    for entry in trade_entries.list_trade_entries_for_owner(
        db,
        owner_user_id,
        tenant_id=tenant_id,
        ticker=ticker,
    ):
        try:
            records.append(
                get_trade_record_file(
                    entry.trade_id, reports_dir=app_config.REPORTS_DIR
                )
            )
        except ValueError:
            continue
    return records


def load_owner_scoped_trade_plans(
    db,
    owner_user_id: str,
    *,
    tenant_id: str | None = None,
    ticker: str | None = None,
    status: str | None = None,
) -> list[dict]:
    plans: list[dict] = []
    for entry in trade_plan_entries.list_trade_plan_entries_for_owner(
        db,
        owner_user_id,
        tenant_id=tenant_id,
        ticker=ticker,
    ):
        try:
            plan = get_trade_plan_file(
                entry.plan_id, reports_dir=app_config.REPORTS_DIR
            )
            if plan.get("status") != entry.status:
                sync_trade_plan_entry_metadata(db, plan, owner_user_id, tenant_id)
            if status and plan.get("status") != status:
                continue
            plans.append(plan)
        except ValueError:
            continue
    return plans


def list_trade_plans(
    *,
    ticker: str | None = None,
    status: str | None = None,
    request: Request | None = None,
) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                return load_owner_scoped_trade_plans(
                    db,
                    user.id,
                    tenant_id=user.tenant_id,
                    ticker=ticker,
                    status=status,
                )
        return list_trade_plans_file(
            ticker=ticker,
            status=status,
            reports_dir=app_config.REPORTS_DIR,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def create_trade_plan(
    payload: TradePlanCreatePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                record_journal_usage(db, user)
                plan = create_trade_plan_file(
                    payload.model_dump(),
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_plan_entry_metadata(db, plan, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.plan.created",
                    resource_type="trade_plan",
                    resource_id=plan.get("plan_id"),
                    metadata={
                        "ticker": plan.get("ticker"),
                        "status": plan.get("status"),
                    },
                    request=request,
                )
                return plan
        return create_trade_plan_file(
            payload.model_dump(), reports_dir=app_config.REPORTS_DIR
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def get_trade_plan(plan_id: str, request: Request | None = None) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_plan_entries.require_trade_plan_entry_for_owner(
                    db, plan_id, user.id, tenant_id=user.tenant_id
                )
                plan = get_trade_plan_file(
                    plan_id, reports_dir=app_config.REPORTS_DIR
                )
                sync_trade_plan_entry_metadata(db, plan, user.id, user.tenant_id)
                return plan
        return get_trade_plan_file(plan_id, reports_dir=app_config.REPORTS_DIR)
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def update_trade_plan(
    plan_id: str,
    payload: TradePlanUpdatePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_plan_entries.require_trade_plan_entry_for_owner(
                    db, plan_id, user.id, tenant_id=user.tenant_id
                )
                record_journal_usage(db, user)
                plan = update_trade_plan_file(
                    plan_id,
                    payload.model_dump(exclude_unset=True),
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_plan_entry_metadata(db, plan, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.plan.updated",
                    resource_type="trade_plan",
                    resource_id=plan_id,
                    metadata={
                        "ticker": plan.get("ticker"),
                        "status": plan.get("status"),
                    },
                    request=request,
                )
                return plan
        return update_trade_plan_file(
            plan_id,
            payload.model_dump(exclude_unset=True),
            reports_dir=app_config.REPORTS_DIR,
        )
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def delete_trade_plan(plan_id: str, request: Request | None = None) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_plan_entries.require_trade_plan_entry_for_owner(
                    db, plan_id, user.id, tenant_id=user.tenant_id
                )
                plan = get_trade_plan_file(
                    plan_id, reports_dir=app_config.REPORTS_DIR
                )
                delete_trade_plan_file(plan_id, reports_dir=app_config.REPORTS_DIR)
                trade_plan_entries.delete_trade_plan_entry(
                    db, plan_id, user.id, tenant_id=user.tenant_id
                )
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.plan.deleted",
                    resource_type="trade_plan",
                    resource_id=plan_id,
                    metadata={"ticker": plan.get("ticker")},
                    request=request,
                )
                return {"deleted": True, "plan_id": plan_id}
        delete_trade_plan_file(plan_id, reports_dir=app_config.REPORTS_DIR)
        return {"deleted": True, "plan_id": plan_id}
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def list_trades(
    ticker: str | None = None, request: Request | None = None
) -> list[dict]:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                return load_owner_scoped_trade_records(
                    db,
                    user.id,
                    tenant_id=user.tenant_id,
                    ticker=ticker,
                )
        return list_trade_records_file(
            ticker=ticker, reports_dir=app_config.REPORTS_DIR
        )
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
                generated_reviews = generate_automatic_trade_reviews(
                    record,
                    owner_user_id=user.id,
                    tenant_id=user.tenant_id,
                    output_language=preferred_output_language_from_request(request),
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.trade.created",
                    resource_type="trade",
                    resource_id=record.get("trade_id"),
                    metadata={
                        "ticker": record.get("ticker"),
                        "status": record.get("status"),
                    },
                    request=request,
                )
                if generated_reviews:
                    audit.record_audit_event_safely(
                        db,
                        tenant_id=user.tenant_id,
                        actor_user_id=user.id,
                        action="journal.review.auto_generated",
                        resource_type="trade",
                        resource_id=record.get("trade_id"),
                        metadata={
                            "review_types": [
                                review["review_type"] for review in generated_reviews
                            ]
                        },
                        request=request,
                    )
                return record
        record = create_trade_record_file(
            payload.model_dump(), reports_dir=app_config.REPORTS_DIR
        )
        generate_automatic_trade_reviews(
            record,
            output_language=preferred_output_language_from_request(request),
        )
        return record
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
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
                return {
                    "record": get_trade_record_file(
                        trade_id, reports_dir=app_config.REPORTS_DIR
                    ),
                    "reviews": list_trade_reviews_file(
                        trade_id, reports_dir=app_config.REPORTS_DIR
                    ),
                }
        return {
            "record": get_trade_record_file(
                trade_id, reports_dir=app_config.REPORTS_DIR
            ),
            "reviews": list_trade_reviews_file(
                trade_id, reports_dir=app_config.REPORTS_DIR
            ),
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
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
                record_journal_usage(db, user)
                record = update_trade_record_file(
                    trade_id,
                    payload.model_dump(exclude_unset=True),
                    reports_dir=app_config.REPORTS_DIR,
                )
                generated_reviews = generate_automatic_trade_reviews(
                    record,
                    owner_user_id=user.id,
                    tenant_id=user.tenant_id,
                    output_language=preferred_output_language_from_request(request),
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.trade.updated",
                    resource_type="trade",
                    resource_id=trade_id,
                    metadata={
                        "ticker": record.get("ticker"),
                        "status": record.get("status"),
                    },
                    request=request,
                )
                if generated_reviews:
                    audit.record_audit_event_safely(
                        db,
                        tenant_id=user.tenant_id,
                        actor_user_id=user.id,
                        action="journal.review.auto_generated",
                        resource_type="trade",
                        resource_id=trade_id,
                        metadata={
                            "review_types": [
                                review["review_type"] for review in generated_reviews
                            ]
                        },
                        request=request,
                    )
                return record
        record = update_trade_record_file(
            trade_id,
            payload.model_dump(exclude_unset=True),
            reports_dir=app_config.REPORTS_DIR,
        )
        generate_automatic_trade_reviews(
            record,
            output_language=preferred_output_language_from_request(request),
        )
        return record
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def execute_trade_plan(
    plan_id: str,
    payload: TradePlanExecutePayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_plan_entries.require_trade_plan_entry_for_owner(
                    db, plan_id, user.id, tenant_id=user.tenant_id
                )
                record_journal_usage(db, user)
                plan = get_trade_plan_file(
                    plan_id, reports_dir=app_config.REPORTS_DIR
                )
                validate_plan_link(
                    plan,
                    {
                        "trade_id": "",
                        "ticker": plan.get("ticker"),
                        "side": plan.get("side"),
                        "entry_timestamp": payload.entry_timestamp,
                    },
                )
                record = create_trade_record_file(
                    build_execution_trade_payload(plan, payload.model_dump()),
                    reports_dir=app_config.REPORTS_DIR,
                )
                generated_reviews = generate_automatic_trade_reviews(
                    record,
                    owner_user_id=user.id,
                    tenant_id=user.tenant_id,
                    output_language=preferred_output_language_from_request(request),
                )
                plan = mark_trade_plan_executed_file(
                    plan_id,
                    record["trade_id"],
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                sync_trade_plan_entry_metadata(db, plan, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.plan.executed",
                    resource_type="trade_plan",
                    resource_id=plan_id,
                    metadata={
                        "ticker": plan.get("ticker"),
                        "trade_id": record.get("trade_id"),
                    },
                    request=request,
                )
                if generated_reviews:
                    audit.record_audit_event_safely(
                        db,
                        tenant_id=user.tenant_id,
                        actor_user_id=user.id,
                        action="journal.review.auto_generated",
                        resource_type="trade",
                        resource_id=record.get("trade_id"),
                        metadata={
                            "review_types": [
                                review["review_type"] for review in generated_reviews
                            ]
                        },
                        request=request,
                    )
                return {"plan": plan, "record": record}

        plan = get_trade_plan_file(plan_id, reports_dir=app_config.REPORTS_DIR)
        validate_plan_link(
            plan,
            {
                "trade_id": "",
                "ticker": plan.get("ticker"),
                "side": plan.get("side"),
                "entry_timestamp": payload.entry_timestamp,
            },
        )
        record = create_trade_record_file(
            build_execution_trade_payload(plan, payload.model_dump()),
            reports_dir=app_config.REPORTS_DIR,
        )
        generate_automatic_trade_reviews(
            record,
            output_language=preferred_output_language_from_request(request),
        )
        plan = mark_trade_plan_executed_file(
            plan_id, record["trade_id"], reports_dir=app_config.REPORTS_DIR
        )
        return {"plan": plan, "record": record}
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def link_trade_to_plan(
    trade_id: str,
    payload: TradePlanLinkPayload,
    request: Request | None = None,
) -> dict:
    try:
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
                trade_plan_entries.require_trade_plan_entry_for_owner(
                    db, payload.plan_id, user.id, tenant_id=user.tenant_id
                )
                record_journal_usage(db, user)
                record = get_trade_record_file(
                    trade_id, reports_dir=app_config.REPORTS_DIR
                )
                plan = get_trade_plan_file(
                    payload.plan_id, reports_dir=app_config.REPORTS_DIR
                )
                validate_plan_link(plan, record)
                if record.get("originating_plan_id") == payload.plan_id:
                    return {"plan": plan, "record": record}
                record = update_trade_record_file(
                    trade_id,
                    {
                        "originating_plan_id": payload.plan_id,
                        "originating_plan_snapshot": build_trade_plan_snapshot(plan),
                        "execution_note": payload.execution_note,
                    },
                    reports_dir=app_config.REPORTS_DIR,
                )
                plan = mark_trade_plan_executed_file(
                    payload.plan_id,
                    trade_id,
                    reports_dir=app_config.REPORTS_DIR,
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                sync_trade_plan_entry_metadata(db, plan, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.trade.linked_plan",
                    resource_type="trade",
                    resource_id=trade_id,
                    metadata={
                        "ticker": record.get("ticker"),
                        "plan_id": payload.plan_id,
                    },
                    request=request,
                )
                return {"plan": plan, "record": record}

        record = get_trade_record_file(trade_id, reports_dir=app_config.REPORTS_DIR)
        plan = get_trade_plan_file(payload.plan_id, reports_dir=app_config.REPORTS_DIR)
        validate_plan_link(plan, record)
        if record.get("originating_plan_id") == payload.plan_id:
            return {"plan": plan, "record": record}
        record = update_trade_record_file(
            trade_id,
            {
                "originating_plan_id": payload.plan_id,
                "originating_plan_snapshot": build_trade_plan_snapshot(plan),
                "execution_note": payload.execution_note,
            },
            reports_dir=app_config.REPORTS_DIR,
        )
        plan = mark_trade_plan_executed_file(
            payload.plan_id, trade_id, reports_dir=app_config.REPORTS_DIR
        )
        return {"plan": plan, "record": record}
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
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
                return list_trade_reviews_file(
                    trade_id, reports_dir=app_config.REPORTS_DIR
                )
        return list_trade_reviews_file(trade_id, reports_dir=app_config.REPORTS_DIR)
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def list_trade_review_activity(request: Request | None = None) -> list[dict]:
    try:
        tasks = journal_review_tasks.list_tasks()
        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                return [
                    task
                    for task in tasks
                    if access.can_access_owner(
                        user,
                        task.get("owner_user_id"),
                        tenant_id=task.get("tenant_id"),
                        allow_unowned=True,
                    )
                ]
        return tasks
    except HTTPException:
        raise
    except (ValueError, analysis_limits.WeeklyUsageLimitExceeded) as exc:
        raise translate_trade_feedback_error(exc) from exc


def generate_configured_trade_review(
    trade_id: str,
    review_type: str,
    payload: TradeReviewGeneratePayload,
    request: Request | None = None,
) -> dict:
    try:
        model_setting = _resolve_trade_review_model_setting(require_enabled=True)
        assert model_setting is not None
        _ensure_trade_review_provider_available(model_setting)
        analysis_references = (
            payload.model_dump()["analysis_references"]
            if payload.analysis_references is not None
            else None
        )
        output_language = (
            payload.output_language
            or preferred_output_language_from_request(request)
        )

        if auth.auth_enabled():
            with auth.db_session() as db:
                user = access.require_trade_request_user(db, request)
                assert user is not None
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
                record_journal_usage(db, user)
                review = _generate_trade_review_with_model_setting(
                    trade_id,
                    review_type,
                    model_setting,
                    analysis_date=payload.analysis_date,
                    analysis_references=analysis_references,
                    output_language=output_language,
                )
                record = get_trade_record_file(
                    trade_id, reports_dir=app_config.REPORTS_DIR
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.review.generated",
                    resource_type="trade",
                    resource_id=trade_id,
                    metadata={
                        "review_type": review_type,
                        "module": AUTO_REVIEW_MODULE,
                        "model_profile": model_setting.get("model_profile"),
                    },
                    request=request,
                )
                return review

        return _generate_trade_review_with_model_setting(
            trade_id,
            review_type,
            model_setting,
            analysis_date=payload.analysis_date,
            analysis_references=analysis_references,
            output_language=output_language,
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
                trade_entries.require_trade_entry_for_owner(
                    db,
                    trade_id,
                    user.id,
                    tenant_id=user.tenant_id,
                )
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
                record = get_trade_record_file(
                    trade_id, reports_dir=app_config.REPORTS_DIR
                )
                sync_trade_entry_metadata(db, record, user.id, user.tenant_id)
                audit.record_audit_event_safely(
                    db,
                    tenant_id=user.tenant_id,
                    actor_user_id=user.id,
                    action="journal.review.saved",
                    resource_type="trade",
                    resource_id=trade_id,
                    metadata={"review_type": review_type},
                    request=request,
                )
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
                    tenant_id=user.tenant_id,
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
