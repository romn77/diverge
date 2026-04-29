from diverge.graph.trading_graph import DivergeGraph


def test_fundamentals_tool_node_includes_prompted_insider_transactions_tool():
    graph = DivergeGraph.__new__(DivergeGraph)
    tool_nodes = graph._create_tool_nodes()

    assert "get_insider_transactions" in tool_nodes["fundamentals"].tools_by_name
