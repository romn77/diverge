from __future__ import annotations

__all__ = ["OpportunityDataNotReady", "run_opportunity_radar"]


def __getattr__(name: str):
    if name in __all__:
        from diverge.opportunity import radar

        return getattr(radar, name)
    raise AttributeError(name)
