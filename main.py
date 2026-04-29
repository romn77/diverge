import sys

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def run_demo() -> None:
    from diverge.default_config import DEFAULT_CONFIG
    from diverge.graph.trading_graph import DivergeGraph

    # Create a custom config
    config = DEFAULT_CONFIG.copy()
    config["deep_think_llm"] = "gpt-5.4-mini"  # Use a different model
    config["quick_think_llm"] = "gpt-5.4-mini"  # Use a different model
    config["max_debate_rounds"] = 1  # Increase debate rounds

    # Configure data vendors (default uses yfinance, no extra API keys needed)
    config["data_vendors"] = {
        "core_stock_apis": "yfinance",  # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",  # Options: alpha_vantage, yfinance
        "news_data": "yfinance",  # Options: alpha_vantage, yfinance
    }

    # Initialize with custom config
    ta = DivergeGraph(debug=True, config=config)

    # forward propagate
    _, decision = ta.propagate("NVDA", "2024-05-10")
    print(decision)

    # Memorize mistakes and reflect
    # ta.reflect_and_remember(1000) # parameter is the position returns


def main() -> None:
    if len(sys.argv) > 1:
        from cli.main import app

        app()
        return

    run_demo()


if __name__ == "__main__":
    main()
