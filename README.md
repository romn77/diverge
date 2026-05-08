<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=de">Deutsch</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=es">Espanol</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=fr">francais</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=ja">Japanese</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=ko">Korean</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=pt">Portugues</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=ru">Russian</a> |
  <a href="https://www.readme-i18n.com/TauricResearch/Diverge?lang=zh">Chinese</a>
</div>

---

# Diverge: Multi-Agent LLM Financial Analysis Framework

> This repository is a Diverge-branded modified fork of an Apache-2.0 licensed multi-agent financial trading research framework by Tauric Research and contributors.
>
> The fork keeps the original attribution, citation, assets, and Apache-2.0 license, and adds project-specific changes around data-source routing, CN/US screening, valuation inputs, web operations, authentication, and deployment.

Diverge models the workflow of a trading desk with specialized LLM-powered agents: fundamentals, sentiment, news, technical analysis, bullish and bearish researchers, trader, risk analysts, and portfolio manager. The framework is intended for research, education, and internal decision-support workflows. It is not financial, investment, legal, tax, or trading advice.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

## Current Implementation

This fork currently includes:

- Google ADK-backed multi-agent analysis runtime with Web Workbench and package entry points.
- Multi-provider LLM support through OpenAI, Google, Anthropic, xAI, OpenRouter, DeepSeek, Xiaohumini, and local Ollama-compatible settings.
- Vendor-routed market data under `diverge/dataflows/vendors/`, grouped by source: `akshare`, `alpha_vantage`, `fmp`, `massive`, `tushare`, `yfinance`, and `local`.
- Market-aware routing for `core_stock_apis`, `technical_indicators`, `fundamental_data`, and `news_data`, with fallback chains, usage tracking, and admin-configurable route policies.
- CN/US screener pipeline with manifest loading, source fallbacks, cached OHLCV history, breakout filters, hard-filter replay, and run artifacts.
- Market-routed valuation input builders for US and CN instruments, DCF/multiples helpers, and generated valuation report sections.
- Web Workbench for reports, analysis tasks, screener tasks, candidate review, assets, trades, feedback loops, and ticker history.
- Optional auth and admin operations backed by PostgreSQL, including tenant-scoped users, module permissions, role limits, audit events, data-source enablement, daily/hourly source limits, and route policy editing.
- Local single-host deployment plus production-style Docker Compose with Postgres, Redis worker, Nginx, backup service, and optional Tencent Cloud COS storage.

## Repository Layout

```text
diverge/agents/        Analyst, researcher, trader, risk, and manager agents
diverge/dataflows/     Router, vendor registry, shared errors, and market utilities
diverge/dataflows/vendors/
                             Source-specific adapters grouped by vendor
diverge/screener/      CN/US screener pipeline, filters, history cache, and replay
diverge/valuation/     DCF, FCFF, multiples, assumptions, and schemas
web/backend/                 FastAPI backend, auth, admin, tasks, storage, and workers
web/frontend/                Next.js Workbench frontend
data/                        Runtime data, reports, screener runs, cache, and history
docs/                        Plans, deployment notes, and feature documentation
scripts/                     Deployment, database checks, backup, and restore helpers
```

## Installation

Clone this fork or your own fork:

```bash
git clone https://github.com/romn77/Diverge.git
cd Diverge
```

Create a Python environment and install the package:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

For development with optional web dependencies:

```bash
pip install -e ".[web]"
```

If you use `uv`:

```bash
uv sync
```

## Configuration

Copy the sample environment file and fill in the providers you need:

```bash
cp .env.example .env
```

Common environment variables:

```bash
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
OPENROUTER_API_KEY=
DEEPSEEK_API_KEY=
XIAOHUMINI_API_KEY=
ALPHA_VANTAGE_API_KEY=
MASSIVE_API_KEY=
MASSIVE_BASE_URL=
FMP_API_KEY=
TUSHARE_TOKEN=
DATA_SYNC_TUSHARE_READY_TIME=18:10
DATA_SYNC_MASSIVE_READY_TIME=21:10
```

Web/auth/deployment variables are also documented in `.env.example`, including `DATABASE_URL`, `AUTH_ENABLED`, `AUTH_MODE`, `FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_BASE_URL`, `TASK_BACKEND`, `REDIS_URL`, `STORAGE_BACKEND`, and Tencent COS settings.

The default runtime configuration lives in `diverge/default_config.py`. Data-source priority can be configured by:

- `tool_vendors`: method-specific override, highest precedence.
- `market_overrides[market][category]`: market/category override.
- `data_vendors[category]`: global category default.
- Web admin data-source routes when auth/database-backed admin features are enabled.

## Web Workbench Usage

The primary runtime is the Web Workbench. It launches analysis and screener tasks through the FastAPI backend, streams task progress, and writes report artifacts.

```bash
cd web
./start.sh
```

Manifest helpers:

```bash
python -m diverge.data.us_manifest
python -m diverge.data.cn_manifest
```

US screening requires `SCREEN_US_MANIFEST_PATH` for web launches. CN screening can use `SCREEN_CN_MANIFEST_PATH`; if omitted, the screener falls back to live CN universe loading through the configured CN source chain.

## Python Usage

```python
from diverge.default_config import DEFAULT_CONFIG
from diverge.graph.trading_graph import DivergeGraph

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.5"
config["quick_think_llm"] = "gpt-5.4-mini"
config["market"] = "auto"
config["output_language"] = "en"

ta = DivergeGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

## Data Sources

Source-specific adapters live under `diverge/dataflows/vendors/`:

```text
akshare/        CN/US price helpers, CN fundamentals/news, rate limiting, valuation inputs
alpha_vantage/  Price, indicators, fundamentals, news, and rate-limit handling
fmp/            Financial Modeling Prep fundamentals and news
massive/        Massive price data client and rate limiting
tushare/        CN stock, fundamentals, indicators, and metadata helpers
yfinance/       Yahoo Finance stock, news, indicators, and valuation inputs
local/          Cached-history stock and indicator analysis
```

Legacy import paths such as `diverge.dataflows.akshare_stock` and `diverge.dataflows.y_finance` are kept as compatibility aliases, but new code should import from the vendor packages directly.

## Web Workbench

The web app is split into a FastAPI backend and a Next.js frontend.

```bash
cd web
./start.sh
```

Defaults:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Reports: `data/reports/`
- Analysis runtime output: `data/eval_results/`
- Screener runs: `data/screener/runs/`
- Screener tasks: `data/screener/tasks/`
- Screener cache: `data/cache/screener/`
- Stock history: `data/history/`

Production-style local Redis worker mode:

```bash
cd web
TASK_BACKEND=redis \
REDIS_URL=redis://127.0.0.1:6379/0 \
START_REDIS_DOCKER=true \
./start.sh
```

Auth rollout is controlled by:

- `AUTH_ENABLED=false`: legacy filesystem-readable workbench.
- `AUTH_ENABLED=true` and `AUTH_MODE=optional`: enable auth and metadata while leaving only low-sensitivity compatibility routes public during migration; report listing and report content still require login.
- `AUTH_ENABLED=true` and `AUTH_MODE=required`: require login for protected routes.

When auth/database mode is enabled:

```bash
scripts/check-database.sh
scripts/check-database.sh --upgrade --bootstrap-admin
```

Database migrations create a default tenant, backfill `tenant_id` on workbench metadata, and then add append-only `audit_events`. Existing `admin`, `operator`, and `viewer` roles remain presets, but route checks use module permissions such as `analysis:create`, `screener:read`, `assets:write`, `journal:write`, `admin:users`, `admin:settings`, and `admin:audit`.

See `web/README.md` for backend endpoints, auth rollout, metadata backfill, and development commands.

## Docker Deployment

Single-host development/preview deployment:

```bash
cp .env.example .env
./scripts/deploy-single-host.sh
```

Production MVP compose stack:

```bash
docker compose -f compose.prod.yml build
docker compose -f compose.prod.yml up -d
```

`compose.prod.yml` adds Nginx, Redis, a dedicated worker, PostgreSQL, backup service, and optional Tencent COS object storage. See `docs/deployment/tencent-cloud-production.md` for the deployment checklist and backup/restore notes.

## Testing

Useful focused checks:

```bash
python -m pytest -q tests/dataflows tests/test_akshare.py tests/test_yfinance.py tests/screener/test_market_data.py tests/screener/test_universe.py
python -m pytest -q tests/web/test_backend_main.py tests/web/test_runner.py
```

Frontend checks are under `web/frontend`:

```bash
cd web/frontend
npm test
npm run build
```

## Apache-2.0 License And Attribution

This repository is distributed under the Apache License, Version 2.0. The full license text is in `LICENSE`.

Apache-2.0 compliance notes for this modified fork:

- The original upstream project is an Apache-2.0 licensed multi-agent financial trading research framework by Tauric Research and contributors.
- This repository contains modifications to the upstream work, including data-source routing, screener, valuation, Web Workbench, auth/admin, deployment, and project-operations changes.
- Keep the `LICENSE` file and this attribution section when redistributing source or object forms.
- Retain upstream copyright, patent, trademark, attribution, citation, and asset notices that apply to the original work.
- The current checkout does not include a separate upstream `NOTICE` file. If one is added upstream and relevant notices apply, include a readable copy as required by Apache-2.0 section 4(d).
- Unless explicitly stated otherwise, contributions submitted to this repository are provided under Apache-2.0.

The upstream framework is research software. Use of Tauric Research names, marks, and badges is limited to attribution and origin description; the Apache-2.0 license does not grant trademark rights beyond that.

## Citation

Please cite the original upstream research if this project helps your research or implementation:

```bibtex
@misc{xiao2025multiagentsllmfinancial,
      title={Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```
