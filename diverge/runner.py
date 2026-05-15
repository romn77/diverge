import datetime
import copy
import json
import os
from collections.abc import Collection
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Generator, Optional

from diverge.analysis.options import ANALYST_AGENT_NAMES, ANALYST_ORDER, AnalystType
from diverge.default_config import DEFAULT_CONFIG
from diverge.llm_clients.model_config import (
    PROVIDER_OPTIONS,
    get_provider_base_url,
)
from diverge.llm_clients.validators import validate_model
from diverge.common.market_calendar import resolve_market_trading_date
from diverge.common.symbols import detect_market, normalize_analysis_ticker_symbol
from diverge.agents.managers.summary_agent import sanitize_report_summary_output
from diverge.research.thesis_tracker import build_thesis_artifact
from diverge.runtime.analysis_context import (
    AnalysisContextPackAdapters,
    AnalysisContextPackRequest,
    build_analysis_context_pack,
    use_search_context,
)
from diverge.runtime.analysis_schema import trade_feedback_artifact_from_state
from diverge.runtime.state import Propagator
from diverge.trade_feedback import get_trade_feedback_payload


SECTION_FILE_MAP = {
    "market_report": ("1_analysts", "market.md"),
    "sentiment_report": ("1_analysts", "sentiment.md"),
    "news_report": ("1_analysts", "news.md"),
    "fundamentals_report": ("1_analysts", "fundamentals.md"),
    "investment_plan": ("2_research", "manager.md"),
    "trader_investment_plan": ("3_trading", "trader.md"),
    "final_trade_decision": ("5_portfolio", "decision.md"),
}
RESEARCH_TEAM = ["Bull Researcher", "Bear Researcher", "Research Manager"]
RISK_TEAM = ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"]
STAGE_AGENT_MAP = {
    "Analysts": tuple(ANALYST_AGENT_NAMES.values()),
    "Research": tuple(RESEARCH_TEAM),
    "Trading": ("Trader",),
    "Risk": tuple(RISK_TEAM),
    "Portfolio": ("Portfolio Manager",),
    "Summary": ("Summary Agent",),
}
VALID_PROVIDERS = {provider for provider, _label, _base_url in PROVIDER_OPTIONS}
VALID_RESEARCH_DEPTHS = {1, 3, 5}
VALID_OUTPUT_LANGUAGES = {"en", "cn"}
OPENAI_REASONING_EFFORTS = {"low", "medium", "high"}
GOOGLE_THINKING_LEVELS = {"high", "minimal"}
MARKET_DATA_SOURCES = {"yfinance", "massive"}
ANALYSIS_RUNTIME_ENV = "DIVERGE_ANALYSIS_RUNTIME"
ADK_NATIVE_ANALYSIS_RUNTIME = "adk_native"


def _coerce_analyst_key(value: str | AnalystType) -> str:
    return str(value).strip().lower()


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def resolve_analysis_runtime(raw_value: str | None = None) -> str:
    runtime = (raw_value or os.environ.get(ANALYSIS_RUNTIME_ENV) or "").strip().lower()
    if not runtime:
        return ADK_NATIVE_ANALYSIS_RUNTIME
    if runtime != ADK_NATIVE_ANALYSIS_RUNTIME:
        raise ValueError(
            f"Unsupported {ANALYSIS_RUNTIME_ENV}={runtime!r}; "
            f"expected {ADK_NATIVE_ANALYSIS_RUNTIME!r}"
        )
    return runtime


def extract_content_string(content):
    """Extract string content from various message formats."""
    import ast

    def is_empty(value):
        if value is None or value == "":
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            try:
                return not bool(ast.literal_eval(stripped))
            except (ValueError, SyntaxError):
                return False
        return not bool(value)

    if is_empty(content):
        return None

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None

    if isinstance(content, list):
        parts = [
            item.get("text", "").strip()
            if isinstance(item, dict) and item.get("type") == "text"
            else (item.strip() if isinstance(item, str) else "")
            for item in content
        ]
        result = " ".join(part for part in parts if part and not is_empty(part))
        return result if result else None

    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message) -> tuple[str, str | None]:
    """Classify LangChain message into a compact event payload."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, "content", None))

    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)

    if isinstance(message, ToolMessage):
        return ("Data", content)

    if isinstance(message, AIMessage):
        return ("Agent", content)

    return ("System", content)


def _shorten_message(
    message_type: str, content: str | None, limit: int = 280
) -> str | None:
    if not content:
        return None
    compact = " ".join(content.split())
    if len(compact) > limit:
        compact = compact[: limit - 3] + "..."
    return f"{message_type}: {compact}"


@dataclass
class AnalysisRequest:
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    quick_think_llm: str
    deep_think_llm: str
    output_language: str
    model_profile: Optional[str] = None
    backend_url: Optional[str] = None
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    portfolio_context: Optional[str] = None
    opportunity_context: Optional[dict] = None
    market_data_source: str = "massive"
    ticker_exchange: Optional[str] = None

    def __post_init__(self) -> None:
        self.ticker = normalize_analysis_ticker_symbol(
            self.ticker,
            ticker_exchange=self.ticker_exchange,
        )

        try:
            analysis_date = datetime.datetime.strptime(self.analysis_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("analysis_date must use YYYY-MM-DD format") from exc

        if analysis_date.date() > datetime.datetime.now().date():
            raise ValueError("analysis_date cannot be in the future")

        market = detect_market(self.ticker)
        if market not in {"cn", "us"}:
            market = "us"
        trading_date = resolve_market_trading_date(
            market,
            analysis_date.date(),
        )
        if trading_date is not None:
            self.analysis_date = trading_date

        self.analysts = [_coerce_analyst_key(analyst) for analyst in self.analysts]
        if not self.analysts:
            raise ValueError("At least one analyst is required")
        if any(analyst not in ANALYST_ORDER for analyst in self.analysts):
            raise ValueError("Unsupported analyst selection")

        if self.research_depth not in VALID_RESEARCH_DEPTHS:
            raise ValueError("Unsupported research_depth")

        self.llm_provider = self.llm_provider.strip().lower()
        if self.llm_provider not in VALID_PROVIDERS:
            raise ValueError("Unsupported llm_provider")

        if not validate_model(self.llm_provider, self.quick_think_llm):
            raise ValueError("Unsupported quick_think_llm for provider")
        if not validate_model(self.llm_provider, self.deep_think_llm):
            raise ValueError("Unsupported deep_think_llm for provider")

        self.output_language = self.output_language.strip().lower()
        if self.output_language not in VALID_OUTPUT_LANGUAGES:
            raise ValueError("Unsupported output_language")

        if self.llm_provider == "openai":
            if self.openai_reasoning_effort not in OPENAI_REASONING_EFFORTS:
                raise ValueError("openai_reasoning_effort is required for openai")
        elif self.openai_reasoning_effort is not None:
            raise ValueError("openai_reasoning_effort is only valid for openai")

        if self.llm_provider == "google":
            if self.google_thinking_level not in GOOGLE_THINKING_LEVELS:
                raise ValueError("google_thinking_level is required for google")
        elif self.google_thinking_level is not None:
            raise ValueError("google_thinking_level is only valid for google")

        if self.portfolio_context is not None:
            normalized_portfolio_context = self.portfolio_context.strip()
            self.portfolio_context = normalized_portfolio_context or None

        self.market_data_source = self.market_data_source.strip().lower()
        if self.market_data_source not in MARKET_DATA_SOURCES:
            raise ValueError("Unsupported market_data_source")


@dataclass
class AnalysisProgress:
    timestamp: str
    status: str
    stage_status: dict[str, str]
    agent_status: dict[str, str]
    current_agent: Optional[str]
    message: Optional[str] = None
    warnings: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisTracker:
    selected_analysts: list[str]
    temp_dir: Path
    agent_status: dict[str, str] = field(init=False)
    current_agent: Optional[str] = field(default=None, init=False)
    report_sections: dict[str, Optional[str]] = field(init=False)
    _last_message_id: Optional[str] = field(default=None, init=False)
    _seen_runtime_progress_ids: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        normalized = []
        for analyst in self.selected_analysts:
            analyst_key = _coerce_analyst_key(analyst)
            if analyst_key in ANALYST_ORDER and analyst_key not in normalized:
                normalized.append(analyst_key)

        self.selected_analysts = normalized
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.agent_status = {}
        for analyst_key in self.selected_analysts:
            self.agent_status[ANALYST_AGENT_NAMES[analyst_key]] = "pending"

        for agent_name in RESEARCH_TEAM:
            self.agent_status[agent_name] = "pending"
        self.agent_status["Trader"] = "pending"
        for agent_name in RISK_TEAM:
            self.agent_status[agent_name] = "pending"
        self.agent_status["Portfolio Manager"] = "pending"
        self.agent_status["Summary Agent"] = "pending"

        self.report_sections = {}
        for analyst_key in self.selected_analysts:
            report_key = {
                "market": "market_report",
                "social": "sentiment_report",
                "news": "news_report",
                "fundamentals": "fundamentals_report",
            }[analyst_key]
            self.report_sections[report_key] = None

        self.report_sections["investment_plan"] = None
        self.report_sections["trader_investment_plan"] = None
        self.report_sections["final_trade_decision"] = None
        self.runtime_warnings: list[dict[str, str]] = []

    def mark_started(self) -> None:
        if not self.selected_analysts:
            return
        first_agent = ANALYST_AGENT_NAMES[self.selected_analysts[0]]
        self.update_agent_status(first_agent, "in_progress")

    def update_agent_status(self, agent: str, status: str) -> bool:
        if agent not in self.agent_status:
            return False
        if self.agent_status[agent] == status:
            return False
        self.agent_status[agent] = status
        self.current_agent = agent
        return True

    def update_report_section(self, section_name: str, content: str) -> bool:
        if section_name not in self.report_sections:
            return False
        if self.report_sections[section_name] == content:
            return False
        self.report_sections[section_name] = content
        self._write_partial_artifact(section_name, content)
        return True

    def consume_chunk(self, chunk: dict, status: str) -> Optional[AnalysisProgress]:
        dirty = False
        message = self._extract_message(chunk)
        if message:
            dirty = True

        warning_message = self._consume_runtime_warnings(chunk)
        if warning_message:
            message = warning_message
            dirty = True

        runtime_message = self._consume_runtime_progress_events(chunk)
        if runtime_message:
            message = runtime_message
            dirty = True

        if self._update_analyst_statuses(chunk):
            dirty = True

        if self._update_research_status(chunk):
            dirty = True

        if self._update_trading_status(chunk):
            dirty = True

        if self._update_risk_status(chunk):
            dirty = True

        if self._update_summary_status(chunk):
            dirty = True

        if not dirty:
            return None

        return self.to_progress(status=status, message=message)

    def to_progress(self, status: str, message: Optional[str]) -> AnalysisProgress:
        return AnalysisProgress(
            timestamp=_timestamp(),
            status=status,
            stage_status=self._build_stage_status(),
            agent_status=dict(self.agent_status),
            current_agent=self.current_agent,
            message=message,
            warnings=list(self.runtime_warnings),
        )

    def _consume_runtime_warnings(self, chunk: dict) -> Optional[str]:
        incoming = chunk.get("runtime_warnings")
        if not isinstance(incoming, list):
            return None

        latest_message = None
        for warning in incoming:
            if not isinstance(warning, dict):
                continue
            normalized = {str(key): str(value) for key, value in warning.items()}
            if normalized in self.runtime_warnings:
                continue
            self.runtime_warnings.append(normalized)
            latest_message = normalized.get("message") or "Runtime warning recorded."

        return f"Warning: {latest_message}" if latest_message else None

    def _consume_runtime_progress_events(self, chunk: dict) -> Optional[str]:
        incoming = chunk.get("runtime_progress_events")
        if not isinstance(incoming, list):
            return None

        latest_message = None
        for event in incoming:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            if event_id and event_id in self._seen_runtime_progress_ids:
                continue
            if event_id:
                self._seen_runtime_progress_ids.add(event_id)

            current_agent = str(event.get("current_agent") or "").strip()
            if current_agent in self.agent_status:
                self.current_agent = current_agent
            message = str(event.get("message") or "").strip()
            if message:
                latest_message = message

        return latest_message

    def _build_stage_status(self) -> dict[str, str]:
        stage_status = {}
        for stage_name, stage_agents in STAGE_AGENT_MAP.items():
            active_agents = [
                agent for agent in stage_agents if agent in self.agent_status
            ]
            if not active_agents:
                stage_status[stage_name] = "not_started"
                continue

            statuses = [self.agent_status[agent] for agent in active_agents]
            if all(status == "pending" for status in statuses):
                stage_status[stage_name] = "not_started"
            elif all(status == "completed" for status in statuses):
                stage_status[stage_name] = "completed"
            else:
                stage_status[stage_name] = "processing"

        return stage_status

    def _extract_message(self, chunk: dict) -> Optional[str]:
        messages = chunk.get("messages", [])
        if not messages:
            return None

        last_message = messages[-1]
        message_id = getattr(last_message, "id", None)
        if message_id == self._last_message_id:
            return None

        self._last_message_id = message_id
        message_type, content = classify_message_type(last_message)
        return _shorten_message(message_type, content)

    def _update_analyst_statuses(self, chunk: dict) -> bool:
        dirty = False
        found_active = False
        report_map = {
            "market": "market_report",
            "social": "sentiment_report",
            "news": "news_report",
            "fundamentals": "fundamentals_report",
        }

        for analyst_key in ANALYST_ORDER:
            if analyst_key not in self.selected_analysts:
                continue

            agent_name = ANALYST_AGENT_NAMES[analyst_key]
            report_key = report_map[analyst_key]
            has_report = bool(chunk.get(report_key))

            if has_report:
                dirty = self.update_agent_status(agent_name, "completed") or dirty
                dirty = (
                    self.update_report_section(report_key, chunk[report_key]) or dirty
                )
            elif not found_active:
                dirty = self.update_agent_status(agent_name, "in_progress") or dirty
                found_active = True
            else:
                dirty = self.update_agent_status(agent_name, "pending") or dirty

        if not found_active and self.selected_analysts:
            dirty = self.update_agent_status("Bull Researcher", "in_progress") or dirty

        return dirty

    def _update_research_status(self, chunk: dict) -> bool:
        debate_state = chunk.get("investment_debate_state")
        if not debate_state:
            return False

        dirty = False
        bull_history = debate_state.get("bull_history", "").strip()
        bear_history = debate_state.get("bear_history", "").strip()
        judge = debate_state.get("judge_decision", "").strip()

        if bull_history or bear_history:
            for agent in RESEARCH_TEAM:
                dirty = self.update_agent_status(agent, "in_progress") or dirty

        if bull_history:
            dirty = (
                self.update_report_section(
                    "investment_plan", f"### Bull Researcher Analysis\n{bull_history}"
                )
                or dirty
            )
        if bear_history:
            dirty = (
                self.update_report_section(
                    "investment_plan", f"### Bear Researcher Analysis\n{bear_history}"
                )
                or dirty
            )
        if judge:
            dirty = (
                self.update_report_section(
                    "investment_plan", f"### Research Manager Decision\n{judge}"
                )
                or dirty
            )
            for agent in RESEARCH_TEAM:
                dirty = self.update_agent_status(agent, "completed") or dirty
            dirty = self.update_agent_status("Trader", "in_progress") or dirty

        return dirty

    def _update_trading_status(self, chunk: dict) -> bool:
        if not chunk.get("trader_investment_plan"):
            return False

        dirty = self.update_report_section(
            "trader_investment_plan", chunk["trader_investment_plan"]
        )
        dirty = self.update_agent_status("Trader", "completed") or dirty
        dirty = self.update_agent_status("Aggressive Analyst", "in_progress") or dirty
        return dirty

    def _update_risk_status(self, chunk: dict) -> bool:
        risk_state = chunk.get("risk_debate_state")
        if not risk_state:
            return False

        dirty = False
        aggressive = risk_state.get("aggressive_history", "").strip()
        conservative = risk_state.get("conservative_history", "").strip()
        neutral = risk_state.get("neutral_history", "").strip()
        judge = risk_state.get("judge_decision", "").strip()

        if aggressive:
            dirty = (
                self.update_agent_status("Aggressive Analyst", "in_progress") or dirty
            )
            dirty = (
                self.update_report_section(
                    "final_trade_decision",
                    f"### Aggressive Analyst Analysis\n{aggressive}",
                )
                or dirty
            )
        if conservative:
            dirty = (
                self.update_agent_status("Conservative Analyst", "in_progress") or dirty
            )
            dirty = (
                self.update_report_section(
                    "final_trade_decision",
                    f"### Conservative Analyst Analysis\n{conservative}",
                )
                or dirty
            )
        if neutral:
            dirty = self.update_agent_status("Neutral Analyst", "in_progress") or dirty
            dirty = (
                self.update_report_section(
                    "final_trade_decision",
                    f"### Neutral Analyst Analysis\n{neutral}",
                )
                or dirty
            )
        if judge:
            dirty = (
                self.update_agent_status("Portfolio Manager", "in_progress") or dirty
            )
            dirty = (
                self.update_report_section(
                    "final_trade_decision",
                    f"### Portfolio Manager Decision\n{judge}",
                )
                or dirty
            )
            for agent in RISK_TEAM:
                dirty = self.update_agent_status(agent, "completed") or dirty
            dirty = self.update_agent_status("Portfolio Manager", "completed") or dirty
            dirty = self.update_agent_status("Summary Agent", "in_progress") or dirty

        return dirty

    def _update_summary_status(self, chunk: dict) -> bool:
        if not chunk.get("report_summary"):
            return False
        return self.update_agent_status("Summary Agent", "completed")

    def _write_partial_artifact(self, section_name: str, content: str) -> None:
        stage_dir_name, file_name = SECTION_FILE_MAP[section_name]
        stage_dir = self.temp_dir / stage_dir_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        (stage_dir / file_name).write_text(content, encoding="utf-8")


def build_analysis_config(request: AnalysisRequest) -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["max_debate_rounds"] = request.research_depth
    config["max_risk_discuss_rounds"] = request.research_depth
    config["quick_think_llm"] = request.quick_think_llm
    config["deep_think_llm"] = request.deep_think_llm
    config["backend_url"] = request.backend_url or get_provider_base_url(
        request.llm_provider
    )
    config["llm_provider"] = request.llm_provider
    config["model_profile"] = request.model_profile
    config["output_language"] = request.output_language
    config["google_thinking_level"] = request.google_thinking_level
    config["openai_reasoning_effort"] = request.openai_reasoning_effort
    us_overrides = config.setdefault("market_overrides", {}).setdefault("us", {})
    if request.market_data_source == "massive":
        us_overrides["core_stock_apis"] = "massive"
    else:
        us_overrides["core_stock_apis"] = "yfinance"
    us_overrides["technical_indicators"] = "local"
    us_overrides["fundamental_data"] = "fmp,alpha_vantage,yfinance"
    us_overrides["news_data"] = "fmp,alpha_vantage,yfinance"
    return config


def run_analysis_streaming(
    request: AnalysisRequest,
    temp_dir: Path,
    *,
    reports_dir: Path | None = None,
    visible_trade_ids: Collection[str] | None = None,
    analysis_run_id: str | None = None,
) -> Generator[AnalysisProgress, None, dict]:
    config = build_analysis_config(request)
    selected_analysts = [key for key in ANALYST_ORDER if key in request.analysts]
    tracker = AnalysisTracker(selected_analysts, temp_dir)
    tracker.mark_started()
    context_pack = build_analysis_context_pack(
        AnalysisContextPackRequest(
            ticker=request.ticker,
            analysis_date=request.analysis_date,
            output_language=request.output_language,
            portfolio_context=request.portfolio_context,
            opportunity_context=request.opportunity_context,
            reports_dir=reports_dir,
            visible_trade_ids=visible_trade_ids,
            analysis_run_id=analysis_run_id,
        ),
        adapters=AnalysisContextPackAdapters(
            get_trade_feedback_payload=get_trade_feedback_payload,
        ),
    )

    with use_search_context(context_pack):
        resolve_analysis_runtime()
        from diverge.runtime.adk_native.runner import stream_analysis_state_chunks

        propagator = Propagator(
            max_recur_limit=config.get(
                "max_recur_limit",
                DEFAULT_CONFIG["max_recur_limit"],
            )
        )
        init_agent_state = propagator.create_initial_state(
            request.ticker,
            request.analysis_date,
            request.output_language,
            **context_pack.initial_state_kwargs(),
        )
        args = propagator.get_graph_args()

        yield tracker.to_progress(
            status="running",
            message=f"System: Analyzing {request.ticker} on {request.analysis_date}",
        )

        trace = []
        for chunk in stream_analysis_state_chunks(
            selected_analysts=selected_analysts,
            config=config,
            init_agent_state=init_agent_state,
            graph_args=args,
        ):
            trace.append(chunk)
            progress = tracker.consume_chunk(chunk, status="running")
            if progress is not None:
                yield progress

        if not trace:
            raise RuntimeError("Analysis completed without producing a final state")

        final_state = trace[-1]
        for agent in list(tracker.agent_status):
            tracker.update_agent_status(agent, "completed")

        yield tracker.to_progress(
            status="completed",
            message=f"System: Completed analysis for {request.analysis_date}",
        )
        return final_state


def save_report_to_disk(final_state, ticker: str, save_path: Path):
    """Save complete analysis report to disk with organized subfolders."""
    save_path.mkdir(parents=True, exist_ok=True)
    sections = []

    analysts_dir = save_path / "1_analysts"
    analyst_parts = []
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(
            final_state["market_report"], encoding="utf-8"
        )
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(
            final_state["sentiment_report"], encoding="utf-8"
        )
        analyst_parts.append(("Social Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(
            final_state["news_report"], encoding="utf-8"
        )
        analyst_parts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(
            final_state["fundamentals_report"], encoding="utf-8"
        )
        analyst_parts.append(
            ("Fundamentals Analyst", final_state["fundamentals_report"])
        )
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    if final_state.get("investment_debate_state"):
        research_dir = save_path / "2_research"
        debate = final_state["investment_debate_state"]
        research_parts = []
        if debate.get("bull_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bull.md").write_text(
                debate["bull_history"], encoding="utf-8"
            )
            research_parts.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "bear.md").write_text(
                debate["bear_history"], encoding="utf-8"
            )
            research_parts.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_dir.mkdir(exist_ok=True)
            (research_dir / "manager.md").write_text(
                debate["judge_decision"], encoding="utf-8"
            )
            research_parts.append(("Research Manager", debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(
                f"### {name}\n{text}" for name, text in research_parts
            )
            sections.append(f"## II. Research Team Decision\n\n{content}")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(
            final_state["trader_investment_plan"], encoding="utf-8"
        )
        sections.append(
            f"## III. Trading Team Plan\n\n### Trader\n{final_state['trader_investment_plan']}"
        )

    if final_state.get("risk_debate_state"):
        risk_dir = save_path / "4_risk"
        risk = final_state["risk_debate_state"]
        risk_parts = []
        if risk.get("aggressive_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "aggressive.md").write_text(
                risk["aggressive_history"], encoding="utf-8"
            )
            risk_parts.append(("Aggressive Analyst", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "conservative.md").write_text(
                risk["conservative_history"], encoding="utf-8"
            )
            risk_parts.append(("Conservative Analyst", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_dir.mkdir(exist_ok=True)
            (risk_dir / "neutral.md").write_text(
                risk["neutral_history"], encoding="utf-8"
            )
            risk_parts.append(("Neutral Analyst", risk["neutral_history"]))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")

        if risk.get("judge_decision"):
            portfolio_dir = save_path / "5_portfolio"
            portfolio_dir.mkdir(exist_ok=True)
            (portfolio_dir / "decision.md").write_text(
                risk["judge_decision"], encoding="utf-8"
            )
            sections.append(
                f"## V. Portfolio Manager Decision\n\n### Portfolio Manager\n{risk['judge_decision']}"
            )

    runtime_warnings = final_state.get("runtime_warnings")
    if isinstance(runtime_warnings, list) and runtime_warnings:
        warning_lines = []
        for warning in runtime_warnings:
            if not isinstance(warning, dict):
                continue
            stage = str(warning.get("stage") or "Runtime").strip()
            message = str(warning.get("message") or warning).strip()
            warning_lines.append(f"- **{stage}**: {message}")
        if warning_lines:
            sections.append("## Runtime Warnings\n\n" + "\n".join(warning_lines))

    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    (save_path / "complete_report.md").write_text(
        header + "\n\n".join(sections), encoding="utf-8"
    )

    thesis_artifact = build_thesis_artifact(final_state, ticker=ticker)
    artifacts_dir = save_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "thesis.json").write_text(
        json.dumps(thesis_artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if final_state.get("report_summary"):
        summary_text = sanitize_report_summary_output(final_state["report_summary"])
        summary_artifact = {
            "type": "summary",
            "ticker": ticker,
            "summary": summary_text,
        }
        (artifacts_dir / "summary.json").write_text(
            json.dumps(summary_artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    trade_feedback_artifact = trade_feedback_artifact_from_state(
        final_state,
        ticker=ticker,
    )
    if trade_feedback_artifact is not None:
        (artifacts_dir / "trade_feedback.json").write_text(
            json.dumps(trade_feedback_artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if isinstance(runtime_warnings, list) and runtime_warnings:
        runtime_warning_artifact = {
            "type": "runtime_warnings",
            "ticker": ticker,
            "warnings": runtime_warnings,
        }
        (artifacts_dir / "runtime_warnings.json").write_text(
            json.dumps(runtime_warning_artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return save_path / "complete_report.md"
