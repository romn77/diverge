from __future__ import annotations

from fastapi import Request

UI_LANGUAGE_HEADER = "x-diverge-ui-language"
OUTPUT_LANGUAGE_HEADER = "x-diverge-output-language"
UI_LANGUAGE_COOKIE = "diverge.ui.language"


def normalize_output_language_preference(value: str | None) -> str | None:
    normalized = (value or "").strip().lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "cn", "chinese", "simplified-chinese"}:
        return "cn"
    if normalized in {"en", "en-us", "english"}:
        return "en"
    return None


def preferred_output_language_from_request(request: Request | None) -> str | None:
    if request is None:
        return None

    for value in (
        request.headers.get(OUTPUT_LANGUAGE_HEADER),
        request.headers.get(UI_LANGUAGE_HEADER),
        request.cookies.get(UI_LANGUAGE_COOKIE),
    ):
        language = normalize_output_language_preference(value)
        if language is not None:
            return language
    return None
