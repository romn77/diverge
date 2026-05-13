from __future__ import annotations

import logging
import os

from fastapi import HTTPException

from diverge.dataflows import vendor_usage
from diverge.trade_feedback import (
    generate_trade_review as generate_trade_review_file,
    list_trade_reviews as list_trade_reviews_file,
)
from web.backend import app_config, llm_models
from web.backend.runtime import journal_review_tasks
from web.backend.services.config import (
    get_provider_availability,
    hydrate_provider_credentials,
)

logger = logging.getLogger(__name__)
AUTO_REVIEW_MODULE = "trade_journal_review"


def external_news_enabled() -> bool:
    return os.environ.get("TRADE_REVIEW_EXTERNAL_NEWS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def review_types_for_auto_generation(
    record: dict, existing_reviews: list[dict]
) -> list[str]:
    saved_review_types = {review.get("review_type") for review in existing_reviews}
    review_types: list[str] = []
    has_entry_fact = bool(
        record.get("entry_timestamp") or record.get("entry_price") is not None
    )
    has_exit_fact = bool(
        str(record.get("status", "")).strip().lower() == "closed"
        or record.get("exit_timestamp")
        or record.get("exit_price") is not None
    )
    if has_entry_fact and "entry_review" not in saved_review_types:
        review_types.append("entry_review")
    if has_exit_fact and "exit_review" not in saved_review_types:
        review_types.append("exit_review")
    return review_types


def resolve_trade_review_model_setting(*, require_enabled: bool) -> dict | None:
    try:
        model_setting = llm_models.resolve_module_model_selection(AUTO_REVIEW_MODULE)
    except Exception as exc:
        if require_enabled:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.info(
            "skip trade review generation module=%s reason=%s",
            AUTO_REVIEW_MODULE,
            exc,
        )
        return None
    if model_setting is None and require_enabled:
        raise HTTPException(
            status_code=400,
            detail="Trade journal AI review generation is not enabled by admin.",
        )
    return model_setting


def ensure_trade_review_provider_available(model_setting: dict) -> None:
    hydrate_provider_credentials(str(model_setting["llm_provider"]))
    provider_availability = get_provider_availability(
        str(model_setting["llm_provider"])
    )
    if not provider_availability["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=str(provider_availability["disabled_reason"]),
        )


def generate_trade_review_with_model_setting(
    trade_id: str,
    review_type: str,
    model_setting: dict,
    *,
    analysis_date: str | None = None,
    analysis_references: list[dict] | None = None,
    output_language: str | None = None,
) -> dict:
    language = (
        output_language.strip().lower()
        if output_language
        else str(model_setting["output_language"])
    )
    with vendor_usage.data_source_usage_context("trade_journal"):
        review = generate_trade_review_file(
            trade_id,
            review_type=review_type,
            llm_provider=str(model_setting["llm_provider"]),
            model=str(model_setting["model"]),
            output_language=language,
            google_thinking_level=model_setting.get("google_thinking_level"),
            openai_reasoning_effort=model_setting.get("openai_reasoning_effort"),
            analysis_date=analysis_date,
            analysis_references=analysis_references,
            history_dir=app_config.STOCK_HISTORY_DIR,
            include_external_news=external_news_enabled(),
            reports_dir=app_config.REPORTS_DIR,
        )
    llm_models.record_model_usage(
        str(model_setting["llm_provider"]),
        str(model_setting["model"]),
        module="trade_journal",
    )
    return review


def generate_automatic_trade_reviews(
    record: dict,
    *,
    owner_user_id: str | None = None,
    tenant_id: str | None = None,
) -> list[dict]:
    existing_reviews = list_trade_reviews_file(
        record["trade_id"],
        reports_dir=app_config.REPORTS_DIR,
    )
    review_types = review_types_for_auto_generation(record, existing_reviews)
    if not review_types:
        return []

    activity_task_id = journal_review_tasks.create_auto_review_task(
        record,
        review_types,
        owner_user_id=owner_user_id,
        tenant_id=tenant_id,
    )

    model_setting = resolve_trade_review_model_setting(require_enabled=False)
    if model_setting is None:
        journal_review_tasks.complete_task(
            activity_task_id,
            {
                "trade_id": record.get("trade_id"),
                "ticker": record.get("ticker"),
                "review_types": review_types,
                "generated_count": 0,
                "skipped": True,
                "reason": "admin_module_disabled",
            },
            "Trade journal AI review skipped because the admin module is disabled.",
        )
        return []

    try:
        journal_review_tasks.mark_running(
            activity_task_id,
            "Trade journal AI review generation started.",
        )
        ensure_trade_review_provider_available(model_setting)
    except HTTPException as exc:
        logger.info(
            "skip automatic trade review generation trade_id=%s provider=%s reason=%s",
            record.get("trade_id"),
            model_setting["llm_provider"],
            exc.detail,
        )
        journal_review_tasks.complete_task(
            activity_task_id,
            {
                "trade_id": record.get("trade_id"),
                "ticker": record.get("ticker"),
                "review_types": review_types,
                "generated_count": 0,
                "skipped": True,
                "reason": str(exc.detail),
            },
            "Trade journal AI review skipped because the provider is unavailable.",
        )
        return []

    generated: list[dict] = []
    failures: list[dict] = []
    for review_type in review_types:
        try:
            review = generate_trade_review_with_model_setting(
                record["trade_id"],
                review_type,
                model_setting,
            )
            generated.append(review)
        except Exception as exc:
            failures.append({"review_type": review_type, "error": str(exc)})
            logger.warning(
                "automatic trade review generation failed trade_id=%s review_type=%s: %s",
                record.get("trade_id"),
                review_type,
                exc,
            )
    result = {
        "trade_id": record.get("trade_id"),
        "ticker": record.get("ticker"),
        "review_types": review_types,
        "generated_count": len(generated),
        "generated_review_types": [review.get("review_type") for review in generated],
        "failures": failures,
    }
    if generated or not failures:
        journal_review_tasks.complete_task(
            activity_task_id,
            result,
            f"Trade journal AI review generation completed ({len(generated)}/{len(review_types)} reviews).",
        )
    else:
        journal_review_tasks.fail_task(
            activity_task_id,
            failures[0]["error"]
            if failures
            else "Trade journal AI review generation failed.",
            "Trade journal AI review generation failed.",
        )
    return generated
