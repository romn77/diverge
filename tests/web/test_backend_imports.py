import importlib


def test_backend_main_imports_without_agent_state_cycle():
    module = importlib.import_module("web.backend.main")

    assert module is not None
