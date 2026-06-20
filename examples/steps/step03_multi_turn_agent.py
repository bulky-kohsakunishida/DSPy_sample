"""Step 3: 会話状態を持つマルチターンエージェントを実行する。"""

import json

from connect_agent_eval.lm import configure_lm
from connect_agent_eval.settings import LMSettings
from connect_agent_eval.simulator import run_conversation


def main() -> None:
    configure_lm(LMSettings(max_tokens=1024))
    transcript = run_conversation()
    print(json.dumps(transcript, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
