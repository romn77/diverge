from __future__ import annotations

import pytest
from fastapi import HTTPException

from web.backend.services import opportunities


def test_opportunity_service_returns_404_when_feature_flag_disabled(monkeypatch):
    monkeypatch.delenv("OPPORTUNITY_RADAR_ENABLED", raising=False)

    with pytest.raises(HTTPException) as excinfo:
        opportunities.require_enabled()

    assert excinfo.value.status_code == 404
