from enum import Enum


class AnalystType(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"


ANALYST_OPTIONS = (
    ("Market Analyst", AnalystType.MARKET),
    ("Social Media Analyst", AnalystType.SOCIAL),
    ("News Analyst", AnalystType.NEWS),
    ("Fundamentals Analyst", AnalystType.FUNDAMENTALS),
)

ANALYST_ORDER = [analyst.value for _label, analyst in ANALYST_OPTIONS]

ANALYST_AGENT_NAMES = {
    AnalystType.MARKET.value: "Market Analyst",
    AnalystType.SOCIAL.value: "Social Analyst",
    AnalystType.NEWS.value: "News Analyst",
    AnalystType.FUNDAMENTALS.value: "Fundamentals Analyst",
}
