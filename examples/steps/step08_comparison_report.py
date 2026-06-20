"""Step 8: Step 7 の結果から改善前後の比較レポートを作成する。"""

import json

from connect_agent_eval.report import run_step8_comparison_report


def main() -> None:
    summary = run_step8_comparison_report()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
