from __future__ import annotations

from diverge.research.search.schema import SearchPurpose


def _is_chinese_context(market: str | None, language: str | None) -> bool:
    normalized_market = str(market or "").lower()
    normalized_language = str(language or "").lower()
    return normalized_language in {"cn", "zh", "zh-cn"} or normalized_market in {
        "cn",
        "hk",
    }


def build_search_query(
    query: str | None,
    *,
    ticker: str,
    market: str,
    language: str | None,
    purpose: SearchPurpose,
) -> str:
    candidate = " ".join(str(query or "").split())
    if len(candidate) < 4:
        candidate = str(ticker).strip()

    if _is_chinese_context(market, language):
        if purpose == "sentiment":
            terms = "最新 舆情 情绪 消息"
        elif purpose == "risk":
            terms = "最新 风险 公告 消息"
        elif purpose == "catalyst":
            terms = "最新 催化 公告 消息"
        else:
            terms = "最新 消息 公告 股票"
        return f"{candidate} {terms}".strip()

    if purpose == "sentiment":
        terms = "latest stock sentiment investor reaction news"
    elif purpose == "risk":
        terms = "latest stock risk news regulatory catalyst"
    elif purpose == "catalyst":
        terms = "latest stock catalyst news earnings guidance"
    else:
        terms = "latest news stock"
    return f"{candidate} {terms}".strip()
