"""Step 7: DSPy optimizer で NextActionPlanner の few-shot を最適化する。"""

import argparse
import json

from connect_agent_eval.optimize import run_step7_prompt_optimization


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--optimizer",
        choices=["bootstrap", "mipro", "gepa", "all"],
        default="bootstrap",
        help="実行する optimizer。デフォルトは既存互換の bootstrap。",
    )
    parser.add_argument(
        "--gepa-max-metric-calls",
        type=int,
        default=36,
        help="GEPA の max_metric_calls。--optimizer gepa または all のときに使う。",
    )
    args = parser.parse_args()
    summary = run_step7_prompt_optimization(
        optimizer=args.optimizer,
        gepa_max_metric_calls=args.gepa_max_metric_calls,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
