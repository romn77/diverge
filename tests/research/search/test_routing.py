from diverge.research.search.routing import (
    available_provider_chain,
    provider_order_for_context,
)


def _summary():
    return {
        "global": {"enabled": True},
        "providers": [
            {
                "provider": "brave",
                "enabled": True,
                "key_status": "configured",
                "hard_cap_reached": False,
                "remaining_to_hard_cap": 10,
            },
            {
                "provider": "tavily",
                "enabled": True,
                "key_status": "configured",
                "hard_cap_reached": False,
                "remaining_to_hard_cap": 10,
            },
            {
                "provider": "bocha",
                "enabled": True,
                "key_status": "configured",
                "hard_cap_reached": False,
                "remaining_to_hard_cap": 10,
            },
        ],
        "requested_provider": "bocha",
    }


def test_us_english_routes_brave_then_tavily():
    assert provider_order_for_context(market="us", language="en") == [
        "brave",
        "tavily",
    ]


def test_cn_hk_or_chinese_routes_bocha_first():
    assert provider_order_for_context(market="cn", language="en") == [
        "bocha",
        "brave",
        "tavily",
    ]
    assert provider_order_for_context(market="hk", language="en") == [
        "bocha",
        "brave",
        "tavily",
    ]
    assert provider_order_for_context(market="us", language="cn") == [
        "bocha",
        "brave",
        "tavily",
    ]


def test_available_provider_chain_skips_unavailable_providers():
    summary = _summary()
    summary["providers"][0]["enabled"] = False
    summary["providers"][1]["key_status"] = "missing"
    summary["providers"][2]["hard_cap_reached"] = True

    assert available_provider_chain(["brave", "tavily", "bocha"], summary) == []


def test_agent_requested_provider_is_ignored():
    summary = _summary()

    chain = available_provider_chain(["brave", "tavily"], summary)

    assert chain == ["brave", "tavily"]
