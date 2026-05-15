from __future__ import annotations

import argparse
import json

from diverge.opportunity.radar import run_opportunity_radar


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m diverge.opportunity.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run-radar")
    run_parser.add_argument("--trade-date")
    run_parser.add_argument("--market", default="cn")
    run_parser.add_argument("--factor-snapshot-path")
    run_parser.add_argument("--price-history-path")
    run_parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "run-radar":
        result = run_opportunity_radar(
            {
                "trade_date": args.trade_date,
                "market": args.market,
                "factor_snapshot_path": args.factor_snapshot_path,
                "price_history_path": args.price_history_path,
                "force": args.force,
            }
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
