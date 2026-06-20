"""Step 6: 合成データをレビューし、評価データセットとして固定する。"""

import json

from connect_agent_eval.curate import review_and_freeze_dataset


def main() -> None:
    review_report = review_and_freeze_dataset()
    print(json.dumps(review_report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
