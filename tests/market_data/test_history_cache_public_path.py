from diverge.market_data.history_cache import (
    empty_history_frame,
    save_history_cache,
)
from diverge.screener.history_cache import (
    empty_history_frame as legacy_empty_history_frame,
)


def test_market_data_history_cache_public_path_and_legacy_import_match(tmp_path):
    frame = empty_history_frame()

    path = save_history_cache(tmp_path, "us", "AAPL", frame)

    assert path.name == "AAPL.csv"
    assert list(empty_history_frame().columns) == list(
        legacy_empty_history_frame().columns
    )
