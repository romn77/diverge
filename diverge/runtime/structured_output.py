from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, TypeAdapter

from diverge.runtime.messages import message_content


def parse_structured_output(content: Any, schema: Any) -> Any:
    """Validate model JSON output against a Pydantic-compatible schema."""

    payload = _coerce_json_payload(content)
    return TypeAdapter(schema).validate_python(payload)


def _coerce_json_payload(content: Any) -> Any:
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, dict | list):
        return content
    if isinstance(content, tuple):
        return _coerce_json_payload(message_content(content))
    if isinstance(content, list):
        text = "\n".join(_text_part(item) for item in content).strip()
    else:
        text = str(content or "").strip()
    if not text:
        raise ValueError("Structured model response was empty.")

    fenced = _strip_json_fence(text)
    try:
        return json.loads(fenced)
    except json.JSONDecodeError:
        return _first_json_value(text)


def _text_part(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("text") or item.get("content") or "")
    return str(getattr(item, "text", getattr(item, "content", "")) or "")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _first_json_value(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return payload
    raise ValueError("Structured model response did not contain valid JSON.")
