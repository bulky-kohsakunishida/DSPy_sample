"""Step 4: 請求問い合わせシナリオとモックツール呼び出しを実行する。"""

import json

from connect_agent_eval.simulator import run_conversation


def main() -> None:
    transcript = run_conversation(
        turns=[
            "今月の請求が急に高くなっています。理由を確認してもらえますか？",
            "アカウントIDは ACC-123456 です。",
            "詳しく分かりました。ありがとう。",
        ],
    )
    print(json.dumps(transcript, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
