from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any


_IDS = itertools.count(1)


@dataclass
class AdkMessage:
    content: str
    role: str = "assistant"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"adk-message-{next(_IDS)}")

    def pretty_print(self) -> None:
        print(self.content)


@dataclass(frozen=True)
class AdkPrompt:
    """Small prompt envelope consumed by the ADK model adapter."""

    system_message: str
    messages: tuple[Any, ...] = ()

    def to_messages(self) -> list[Any]:
        return [{"role": "system", "content": self.system_message}, *self.messages]

    def to_string(self) -> str:
        lines = [f"System: {self.system_message}"]
        for message in self.messages:
            role = message_role(message).title()
            content = message_content(message)
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_string()

    def __contains__(self, value: object) -> bool:
        return str(value) in self.to_string()

    def __iter__(self):
        return iter(self.to_messages())

    def __getitem__(self, index):
        return self.to_messages()[index]

    def __len__(self) -> int:
        return len(self.to_messages())

    def lower(self) -> str:
        return self.to_string().lower()


def message_content(message: Any) -> str:
    if isinstance(message, tuple) and len(message) >= 2:
        return str(message[1])
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "content", message))


def message_role(message: Any) -> str:
    if isinstance(message, tuple) and len(message) >= 1:
        role = str(message[0]).lower()
    elif isinstance(message, dict):
        role = str(message.get("role", "user")).lower()
    else:
        class_name = message.__class__.__name__.lower()
        if "system" in class_name:
            role = "system"
        elif "ai" in class_name or "assistant" in class_name:
            role = "assistant"
        else:
            role = "user"

    if role in {"human", "user"}:
        return "user"
    if role in {"ai", "assistant", "model"}:
        return "model"
    if role == "system":
        return "system"
    return "user"
