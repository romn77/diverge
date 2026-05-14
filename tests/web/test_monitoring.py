from __future__ import annotations

import sys
import types

from web.backend import monitoring


def test_before_send_scrubs_sensitive_keys_and_values():
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer raw-token",
                "Cookie": "session=abc",
            },
            "url": "https://app.local/api?api_key=abc123&symbol=NVDA",
        },
        "extra": {
            "prompt": "buy everything",
            "portfolio": {"cash": 100, "positions": ["NVDA"]},
            "message": "key sk-abcdefghijklmnopqrstuvwxyz123456 and postgresql://user:pass@db/app",
        },
    }

    scrubbed = monitoring.before_send(event, None)

    assert scrubbed["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert scrubbed["request"]["headers"]["Cookie"] == "[REDACTED]"
    assert "api_key=[REDACTED]" in scrubbed["request"]["url"]
    assert "symbol=NVDA" in scrubbed["request"]["url"]
    assert scrubbed["extra"]["prompt"] == "[REDACTED]"
    assert scrubbed["extra"]["portfolio"] == "[REDACTED]"
    assert "[REDACTED_OPENAI_KEY]" in scrubbed["extra"]["message"]
    assert "postgresql://[REDACTED]" in scrubbed["extra"]["message"]


def test_initialize_sentry_uses_privacy_preserving_defaults(monkeypatch):
    calls = []
    tags = []

    sentry_sdk = types.ModuleType("sentry_sdk")
    sentry_sdk.init = lambda **kwargs: calls.append(kwargs)
    sentry_sdk.set_tag = lambda key, value: tags.append((key, value))

    logging_mod = types.ModuleType("sentry_sdk.integrations.logging")

    class LoggingIntegration:
        def __init__(self, *, level, event_level):
            self.level = level
            self.event_level = event_level

    logging_mod.LoggingIntegration = LoggingIntegration

    fastapi_mod = types.ModuleType("sentry_sdk.integrations.fastapi")

    class FastApiIntegration:
        pass

    fastapi_mod.FastApiIntegration = FastApiIntegration

    arq_mod = types.ModuleType("sentry_sdk.integrations.arq")

    class ArqIntegration:
        pass

    arq_mod.ArqIntegration = ArqIntegration

    monkeypatch.setitem(sys.modules, "sentry_sdk", sentry_sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.logging", logging_mod)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.fastapi", fastapi_mod)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.arq", arq_mod)
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("SENTRY_SERVICE", raising=False)
    monkeypatch.setattr(monitoring, "_INITIALIZED", False)

    assert monitoring.initialize_sentry(default_service_name="backend") is True

    options = calls[0]
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["traces_sample_rate"] == 0.05
    assert options["sample_rate"] == 1.0
    assert options["environment"] == "production"
    assert options["before_send"] is monitoring.before_send
    assert ("service", "backend") in tags
    assert ("component", "web-backend") in tags
