import json

from diverge.common import read_json_file, write_json_atomic


def test_write_json_atomic_creates_parent_and_round_trips_utf8(tmp_path):
    target = tmp_path / "nested" / "state.json"
    payload = {"ticker": "600519.SH", "name": "贵州茅台"}

    write_json_atomic(target, payload)

    assert read_json_file(target) == payload
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_write_json_atomic_removes_temporary_file(tmp_path):
    target = tmp_path / "state.json"

    write_json_atomic(target, {"ok": True})

    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_write_json_atomic_can_sort_keys(tmp_path):
    target = tmp_path / "state.json"

    write_json_atomic(target, {"b": 2, "a": 1}, sort_keys=True)

    assert target.read_text(encoding="utf-8").splitlines()[:3] == [
        "{",
        '  "a": 1,',
        '  "b": 2',
    ]
