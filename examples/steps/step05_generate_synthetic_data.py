"""Step 5: レビュー前の合成データと候補プロンプトを生成する。"""

import json

from connect_agent_eval.synthesize import write_synthetic_dataset


def main() -> None:
    manifest = write_synthetic_dataset()
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
