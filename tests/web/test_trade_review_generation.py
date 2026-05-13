from unittest.mock import patch

from web.backend.services import trade_review_generation


def test_review_types_for_auto_generation_skips_existing_reviews():
    record = {
        "trade_id": "trade-1",
        "entry_price": 100.0,
        "exit_price": 110.0,
        "status": "closed",
    }

    assert trade_review_generation.review_types_for_auto_generation(
        record,
        [{"review_type": "entry_review"}],
    ) == ["exit_review"]


def test_automatic_generation_records_skipped_activity_when_module_disabled():
    record = {
        "trade_id": "trade-1",
        "ticker": "MSFT",
        "entry_price": 100.0,
        "status": "open",
    }

    with (
        patch.object(
            trade_review_generation,
            "list_trade_reviews_file",
            return_value=[],
        ),
        patch.object(
            trade_review_generation.journal_review_tasks,
            "create_auto_review_task",
            return_value="activity-1",
        ) as create_task,
        patch.object(
            trade_review_generation,
            "resolve_trade_review_model_setting",
            return_value=None,
        ),
        patch.object(
            trade_review_generation.journal_review_tasks,
            "complete_task",
        ) as complete_task,
    ):
        generated = trade_review_generation.generate_automatic_trade_reviews(
            record,
            owner_user_id="user-1",
            tenant_id="tenant-1",
        )

    assert generated == []
    create_task.assert_called_once_with(
        record,
        ["entry_review"],
        owner_user_id="user-1",
        tenant_id="tenant-1",
    )
    complete_task.assert_called_once()
    activity_task_id, result, message = complete_task.call_args.args
    assert activity_task_id == "activity-1"
    assert result["skipped"] is True
    assert result["reason"] == "admin_module_disabled"
    assert "admin module is disabled" in message
