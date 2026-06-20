"""Step 7: DSPy optimizer で NextActionPlanner の few-shot を最適化する。"""

import json

from connect_agent_eval.optimize import run_step7_prompt_optimization


def main() -> None:
    summary = run_step7_prompt_optimization()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
