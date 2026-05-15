"""
Diverge Report Viewer backend composition root and ASGI entrypoint.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web.backend import (
    analysis_limits,
    app_config,
    asset_entries,
    audit,
    auth,
    data_sources,
    job_records,
    llm_models,
    screener_results,
    report_metadata,
    screener_runs,
    search_quota,
    trade_entries,
)
from web.backend.routers import (
    admin as admin_router,
    assets as assets_router,
    auth as auth_router,
    config as config_router,
    data_sync as data_sync_router,
    health as health_router,
    market_briefs as market_briefs_router,
    market_resolution as market_resolution_router,
    reports as reports_router,
    screeners as screeners_router,
    tasks as tasks_router,
    ticker_history as ticker_history_router,
    trades as trades_router,
)
from web.backend.runtime.analysis_tasks import restore_persisted_active_tasks
from web.backend.runtime.data_sync_tasks import restore_persisted_data_sync_tasks
from web.backend.runtime.market_brief_tasks import restore_persisted_market_brief_tasks
from web.backend.runtime.screener_tasks import restore_persisted_screener_tasks
from web.backend.runtime import task_store
from web.backend.monitoring import initialize_sentry


initialize_sentry(default_service_name="backend")


@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    auth.initialize_auth_runtime()
    analysis_limits.initialize_analysis_limits_runtime()
    data_sources.initialize_data_source_runtime()
    llm_models.initialize_llm_model_runtime()
    search_quota.initialize_search_quota_runtime()
    report_metadata.initialize_report_metadata_runtime()
    screener_runs.initialize_screener_runtime()
    screener_results.initialize_screener_result_runtime()
    trade_entries.initialize_trade_entries_runtime()
    asset_entries.initialize_asset_runtime()
    audit.ensure_audit_tables()
    job_records.initialize_job_record_runtime()
    if not task_store.redis_task_backend_enabled():
        restore_persisted_active_tasks()
        restore_persisted_screener_tasks()
        restore_persisted_data_sync_tasks()
        restore_persisted_market_brief_tasks()
        job_records.recover_stale_running_job_records()
    yield


app = FastAPI(
    title="Diverge Report Viewer",
    version="1.1.0",
    lifespan=_app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    health_router.router,
    auth_router.router,
    admin_router.router,
    reports_router.router,
    market_briefs_router.router,
    market_resolution_router.router,
    trades_router.router,
    assets_router.router,
    tasks_router.router,
    data_sync_router.router,
    screeners_router.router,
    ticker_history_router.router,
    config_router.router,
):
    app.include_router(router)
