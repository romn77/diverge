from diverge.runtime.state import Propagator


def test_create_initial_state_initializes_v3_metadata_fields():
    state = Propagator().create_initial_state("MSFT", "2026-03-20")

    assert "earnings_event" in state
    assert "instrument_type" in state
    assert "valuation_applicability" in state
    assert "valuation_applicability_reason" in state
    assert state["earnings_event"] is None
    assert state["instrument_type"] is None
    assert state["valuation_applicability"] is None
    assert state["valuation_applicability_reason"] is None
