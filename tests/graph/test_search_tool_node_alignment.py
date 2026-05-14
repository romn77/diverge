from diverge.graph.trading_graph import DivergeGraph


def test_web_search_tool_is_only_attached_to_news_and_social_tool_nodes():
    graph = DivergeGraph.__new__(DivergeGraph)
    tool_nodes = graph._create_tool_nodes()

    assert "web_search_evidence" in tool_nodes["news"].tools_by_name
    assert "web_search_evidence" in tool_nodes["social"].tools_by_name
    assert "web_search_evidence" not in tool_nodes["market"].tools_by_name
    assert "web_search_evidence" not in tool_nodes["fundamentals"].tools_by_name
