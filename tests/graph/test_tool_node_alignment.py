from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_fundamentals_tool_node_includes_prompted_insider_transactions_tool():
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    tool_nodes = graph._create_tool_nodes()

    assert "get_insider_transactions" in tool_nodes["fundamentals"].tools_by_name
