"""Step 2: 単発問い合わせ用の DSPy Signature / Module を実行する。"""

import json

from connect_agent_eval.lm import configure_lm
from connect_agent_eval.modules import SingleTurnSupportAgent


def main() -> None:
    configure_lm()
    agent = SingleTurnSupportAgent()
    result = agent(
        customer_utterance=(
            "今月の請求が急に高くなっています。理由を確認してもらえますか？"
        )
    )

    print(
        json.dumps(
            {
                "intent": result.intent,
                "intent_display_name": result.intent_display_name,
                "required_slots": result.required_slots,
                "response": result.response,
                "escalate": result.escalate,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
