from __future__ import annotations

from diverge.decision_card.schema import (
    ActionPlaybook,
    DataQualityLevel,
    DecisionCard,
    PositionGuidance,
    TradeReadiness,
    WhyNot,
)


BANNED_POSITION_PHRASES = (
    "你当前仓位",
    "你的组合",
    "当前仓位",
    "组合敞口",
    "portfolio exposure",
    "your current position",
    "your portfolio",
    "current exposure",
)

DATA_QUALITY_SUMMARIES: dict[DataQualityLevel, tuple[str, str]] = {
    "complete": (
        "核心证据和执行信息较完整，当前卡片可直接用于决策复核。",
        "Core evidence and execution context are complete enough for decision review.",
    ),
    "partial": (
        "存在部分数据缺口，但主要判断仍可用于决策参考。",
        "Some data gaps remain, but the main decision is still usable.",
    ),
    "weak": (
        "关键证据或价格上下文偏弱，应降低执行激进度。",
        "Key evidence or price context is weak; execution should stay conservative.",
    ),
    "insufficient": (
        "结构化证据不足，当前卡片只能作为低置信度参考。",
        "Structured evidence is insufficient; treat the card as low-confidence context.",
    ),
}

READINESS_REASONS: dict[TradeReadiness, tuple[str, str]] = {
    "READY": (
        "行动条件基本满足，但仍应按执行计划分批控制风险。",
        "Action conditions are broadly met, with staged risk control still required.",
    ),
    "WAITING_FOR_TRIGGER": (
        "当前裁决需要等待更明确的价格、基本面或风险触发条件。",
        "The ruling needs a clearer price, fundamental, or risk trigger first.",
    ),
    "BLOCKED_BY_RISK": (
        "风险条件优先，当前不适合扩大风险暴露。",
        "Risk conditions dominate; avoid increasing risk exposure for now.",
    ),
    "DATA_INSUFFICIENT": (
        "结构化证据不足，暂不能形成可靠执行判断。",
        "Structured evidence is insufficient for a reliable execution call.",
    ),
    "NO_ACTION_REQUIRED": (
        "当前不需要新增动作，继续复核关键观察项即可。",
        "No new action is required; continue monitoring the key watch items.",
    ),
}


def _is_cn(output_language: str | None) -> bool:
    return (output_language or "en").strip().lower() == "cn"


def _localized(output_language: str | None, pair: tuple[str, str]) -> str:
    return pair[0] if _is_cn(output_language) else pair[1]


def _clean_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _trim_list(values: list[str], *, max_items: int = 3) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned is None or cleaned in seen:
            continue
        result.append(cleaned)
        seen.add(cleaned)
        if len(result) >= max_items:
            break
    return result


def _append_note(card: DecisionCard, note: str) -> None:
    if note not in card.data_quality_notes:
        card.data_quality_notes.append(note)


def _append_blocking_item(card: DecisionCard, item: str) -> None:
    card.blocking_items = _trim_list([*card.blocking_items, item], max_items=5)


def resolve_data_quality_level(card: DecisionCard) -> DataQualityLevel:
    notes = " ".join(card.data_quality_notes).lower()
    has_fallback_note = "fallback" in notes or "could not derive" in notes
    has_reasons = bool(card.key_reasons)
    has_concrete_evidence = any(
        bool(_clean_text(reason.evidence)) for reason in card.key_reasons
    )
    positive_without_risks = card.rating in {"BUY", "OVERWEIGHT"} and not card.key_risks
    price_sensitive_action = card.action in {"OPEN", "ADD", "TRIM", "EXIT"}
    missing_price = card.price_plan.current_price is None

    if has_fallback_note or not has_reasons:
        return "insufficient"

    if (
        not has_concrete_evidence
        or positive_without_risks
        or (price_sensitive_action and missing_price)
    ):
        return "weak"

    if (
        card.data_quality_notes
        or missing_price
        or not card.price_plan.invalidation
        or not (card.price_plan.add_condition or card.price_plan.entry_zone)
    ):
        return "partial"

    return "complete"


def _data_quality_summary(level: DataQualityLevel, output_language: str | None) -> str:
    return _localized(output_language, DATA_QUALITY_SUMMARIES[level])


def _readiness_for_card(card: DecisionCard) -> TradeReadiness:
    if card.data_quality_level == "insufficient":
        return "DATA_INSUFFICIENT"
    if card.action in {"OPEN", "ADD"}:
        return "READY" if card.confidence != "low" else "WAITING_FOR_TRIGGER"
    if card.action == "WATCH":
        return "WAITING_FOR_TRIGGER"
    if card.action in {"NO_ACTION", "MAINTAIN"}:
        return "NO_ACTION_REQUIRED"
    return "BLOCKED_BY_RISK"


def _readiness_reason(
    readiness: TradeReadiness, card: DecisionCard, output_language: str | None
) -> str:
    return _localized(output_language, READINESS_REASONS[readiness])


def validate_trade_readiness(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    previous = card.trade_readiness
    resolved = _readiness_for_card(card)
    card.trade_readiness = resolved
    if previous != resolved or not _clean_text(card.trade_readiness_reason):
        card.trade_readiness_reason = _readiness_reason(resolved, card, output_language)

    if card.data_quality_level == "weak":
        _append_blocking_item(
            card,
            "数据质量偏弱，执行前需要额外确认。"
            if _is_cn(output_language)
            else "Data quality is weak; confirm inputs before execution.",
        )
    if card.action == "WATCH" and card.price_plan.add_condition:
        _append_blocking_item(card, card.price_plan.add_condition)
    elif card.action == "WATCH" and card.watch_items:
        _append_blocking_item(card, card.watch_items[0])
    return card


def _why_not_fallbacks(card: DecisionCard, output_language: str | None) -> WhyNot:
    if _is_cn(output_language):
        return WhyNot(
            why_not_more_bullish=(
                "当前证据仍不足以支持更激进的结论，需等待安全边际或触发条件改善。"
                if card.rating in {"BUY", "OVERWEIGHT", "HOLD"}
                else "主要风险仍未解除，暂不应上调为更积极的判断。"
            ),
            why_not_more_bearish=(
                "核心投资假设尚未被证伪，现有风险不足以支持更悲观的裁决。"
            ),
            why_not_act_now=(
                "当前行动条件尚未完全满足，应等待执行计划中的触发或失效信号。"
            ),
        )
    return WhyNot(
        why_not_more_bullish=(
            "The evidence does not yet justify a more aggressive stance without better margin of safety or trigger confirmation."
            if card.rating in {"BUY", "OVERWEIGHT", "HOLD"}
            else "The main risk objections remain unresolved, so the stance should not be upgraded yet."
        ),
        why_not_more_bearish=(
            "The core thesis has not been invalidated, so the available risks do not justify a more bearish ruling."
        ),
        why_not_act_now=(
            "The execution conditions are not fully satisfied; wait for the playbook trigger or invalidation signal."
        ),
    )


def ensure_why_not(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    fallback = _why_not_fallbacks(card, output_language)
    current = card.why_not or WhyNot()
    card.why_not = WhyNot(
        why_not_more_bullish=_clean_text(current.why_not_more_bullish)
        or fallback.why_not_more_bullish,
        why_not_more_bearish=_clean_text(current.why_not_more_bearish)
        or fallback.why_not_more_bearish,
        why_not_act_now=_clean_text(current.why_not_act_now)
        or fallback.why_not_act_now,
    )
    return card


def _first_available(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _playbook_fallbacks(
    card: DecisionCard, output_language: str | None
) -> ActionPlaybook:
    add_condition = _first_available(
        card.price_plan.add_condition,
        card.watch_items[0] if card.watch_items else None,
    )
    invalidation = card.price_plan.invalidation[:3]
    cn = _is_cn(output_language)
    trigger_default = (
        "等待新的基本面、价格或风险证据。"
        if cn
        else "Wait for new fundamental, price, or risk evidence."
    )
    templates = {
        "act": (
            "仅在入场或加仓条件满足时分批执行。"
            if cn
            else "Use staged execution only when the entry or add condition is met.",
            add_condition
            or (
                "等待价格和风险信号确认。"
                if cn
                else "Wait for price and risk confirmation."
            ),
            "若核心趋势或基本面假设被破坏，则暂停执行。"
            if cn
            else "Pause execution if the core trend or fundamental thesis breaks.",
        ),
        "watch": (
            "加入观察，不追价。"
            if cn
            else "Keep on watch; do not chase before confirmation.",
            add_condition
            or (
                "等待明确的价格、成交量或基本面触发条件。"
                if cn
                else "Wait for a clear price, volume, or fundamental trigger."
            ),
            "若风险收益比继续恶化，则维持观望或回避。"
            if cn
            else "Stay on watch or avoid if the risk/reward setup deteriorates.",
        ),
        "risk": (
            "优先降低或回避新增风险暴露。"
            if cn
            else "Reduce or avoid new risk exposure first.",
            "等待风险条件改善后再重新评估。"
            if cn
            else "Reassess only after the risk condition improves.",
            "若风险继续扩大，则保持防御性裁决。"
            if cn
            else "Keep the defensive ruling if the risk condition expands.",
        ),
        "steady": (
            "不需要新增动作，继续复核关键观察项。"
            if cn
            else "No new action is required; keep monitoring watch items.",
            add_condition or trigger_default,
            "若核心假设被破坏，则重新分析。"
            if cn
            else "Re-analyze if the core thesis breaks.",
        ),
    }
    key = (
        "act"
        if card.action in {"OPEN", "ADD"}
        else "watch"
        if card.action == "WATCH"
        else "risk"
        if card.action in {"TRIM", "EXIT", "AVOID"}
        else "steady"
    )
    do_now, trigger, fallback_invalidation = templates[key]

    return ActionPlaybook(
        do_now=[do_now],
        trigger_to_act=[trigger],
        invalidation=invalidation or [fallback_invalidation],
    )


def ensure_action_playbook(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    fallback = _playbook_fallbacks(card, output_language)
    current = card.action_playbook or ActionPlaybook()
    card.action_playbook = ActionPlaybook(
        do_now=_trim_list(current.do_now or fallback.do_now),
        trigger_to_act=_trim_list(current.trigger_to_act or fallback.trigger_to_act),
        invalidation=_trim_list(current.invalidation or fallback.invalidation),
        execution_notes=_trim_list(current.execution_notes),
    )

    if card.action == "WATCH" and not card.action_playbook.trigger_to_act:
        _append_note(card, "WATCH card lacks action playbook trigger_to_act.")
    if card.action in {"OPEN", "ADD"} and not card.action_playbook.invalidation:
        _append_note(card, "OPEN/ADD card lacks action playbook invalidation.")
    return card


def _has_banned_position_phrase(value: str | None) -> bool:
    text = (value or "").lower()
    return any(phrase.lower() in text for phrase in BANNED_POSITION_PHRASES)


def _sanitize_position_guidance(card: DecisionCard) -> None:
    guidance = card.position_guidance
    if guidance is None:
        return
    changed = False
    for field in (
        "suggested_exposure",
        "max_exposure",
        "sizing_rationale",
        "risk_budget_note",
    ):
        value = getattr(guidance, field)
        if _has_banned_position_phrase(value):
            setattr(guidance, field, None)
            changed = True
        elif isinstance(value, str):
            setattr(guidance, field, _clean_text(value))
    if changed:
        _append_note(
            card,
            "Position guidance removed user-specific portfolio exposure wording.",
        )


def _position_guidance_fallback(
    card: DecisionCard, output_language: str | None
) -> PositionGuidance:
    cn = _is_cn(output_language)
    fallback = (
        "维持当前决策节奏，不需要新增资金动作。"
        if cn
        else "No new capital action is required for this decision stance."
    )
    suggested = {
        "READY": "触发条件满足时可考虑小比例、分批执行。"
        if cn
        else "Consider small staged exposure only after trigger confirmation.",
        "WAITING_FOR_TRIGGER": "触发条件确认前不建议扩大风险暴露。"
        if cn
        else "Do not increase risk exposure before trigger confirmation.",
        "BLOCKED_BY_RISK": "风险解除前应避免新增风险暴露。"
        if cn
        else "Avoid adding risk exposure until the blocking risk improves.",
        "DATA_INSUFFICIENT": "数据不足时不应给出激进仓位建议。"
        if cn
        else "Do not use aggressive sizing while data is insufficient.",
    }.get(card.trade_readiness, fallback)
    return PositionGuidance(
        suggested_exposure=suggested,
        risk_budget_note=(
            "该建议为通用风险控制提示，不基于用户真实持仓。"
            if cn
            else "Generic risk guidance; not based on the user's actual holdings."
        ),
    )


def ensure_position_guidance(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    if card.position_guidance is None and _clean_text(card.suggested_position):
        card.position_guidance = PositionGuidance(
            suggested_exposure=card.suggested_position
        )

    _sanitize_position_guidance(card)
    fallback = _position_guidance_fallback(card, output_language)
    current = card.position_guidance or PositionGuidance()
    card.position_guidance = PositionGuidance(
        suggested_exposure=_clean_text(current.suggested_exposure)
        or fallback.suggested_exposure,
        max_exposure=_clean_text(current.max_exposure),
        sizing_rationale=_clean_text(current.sizing_rationale),
        risk_budget_note=_clean_text(current.risk_budget_note)
        or fallback.risk_budget_note,
    )
    return card


def apply_decision_intelligence(
    card: DecisionCard, *, output_language: str | None = None
) -> DecisionCard:
    card.card_version = "1.2"
    previous_quality_level = card.data_quality_level
    card.data_quality_level = resolve_data_quality_level(card)
    if previous_quality_level != card.data_quality_level or not _clean_text(
        card.data_quality_summary
    ):
        card.data_quality_summary = _data_quality_summary(
            card.data_quality_level, output_language
        )
    card = validate_trade_readiness(card, output_language=output_language)
    card = ensure_why_not(card, output_language=output_language)
    card = ensure_action_playbook(card, output_language=output_language)
    card = ensure_position_guidance(card, output_language=output_language)
    card.blocking_items = _trim_list(card.blocking_items, max_items=5)
    return card
