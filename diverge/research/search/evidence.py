from __future__ import annotations

from diverge.research.search.session import SearchSession


def build_search_evidence_artifact(session: SearchSession) -> dict | None:
    if not session.calls:
        return None

    result_count = sum(len(call.results) for call in session.calls)
    unique_results = session.unique_results()

    return {
        "type": "search_evidence",
        "schema_version": 1,
        "analysis_run_id": session.analysis_run_id,
        "ticker": session.ticker,
        "analysis_date": session.analysis_date,
        "budget": session.budget.model_dump(mode="json"),
        "summary": {
            "call_count": len(session.calls),
            "result_count": result_count,
            "unique_result_count": len(unique_results),
            "warning_count": sum(len(call.warnings) for call in session.calls),
            "cache_hit_count": sum(1 for call in session.calls if call.cache_hit),
        },
        "calls": [call.model_dump(mode="json") for call in session.calls],
        "results": [result.model_dump(mode="json") for result in unique_results],
        # TODO: add agent_evidence.json claim-to-source mapping in a later version.
    }
