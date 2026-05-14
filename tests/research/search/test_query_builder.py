from diverge.research.search.query_builder import build_search_query


def test_empty_us_fresh_news_query_uses_ticker_latest_news_stock_terms():
    query = build_search_query(
        "",
        ticker="AAPL",
        market="us",
        language="en",
        purpose="fresh_news",
    )

    assert "AAPL" in query
    assert "latest" in query.lower()
    assert "news" in query.lower()
    assert "stock" in query.lower()


def test_cn_query_uses_chinese_market_terms():
    query = build_search_query(
        None,
        ticker="000001.SZ",
        market="cn",
        language="cn",
        purpose="fresh_news",
    )

    assert "000001.SZ" in query
    assert "最新" in query
    assert "消息" in query or "公告" in query


def test_sentiment_purpose_builds_sentiment_query():
    query = build_search_query(
        "AAPL",
        ticker="AAPL",
        market="us",
        language="en",
        purpose="sentiment",
    )

    assert "sentiment" in query.lower()


def test_cn_sentiment_query_uses_public_opinion_terms():
    query = build_search_query(
        "宁德时代",
        ticker="300750.SZ",
        market="cn",
        language="cn",
        purpose="sentiment",
    )

    assert "舆情" in query or "情绪" in query
