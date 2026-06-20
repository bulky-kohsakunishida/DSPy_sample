import argparse
import json

from connect_agent_eval.lm import configure_lm
from connect_agent_eval.modules import SingleTurnSupportAgent


DEFAULT_UTTERANCE = "今月の請求が急に高くなっています。理由を確認してもらえますか？"


def run(utterance: str) -> dict[str, str]:
    configure_lm()
    agent = SingleTurnSupportAgent()
    result = agent(customer_utterance=utterance)
    return {
        "intent": result.intent,
        "intent_display_name": result.intent_display_name,
        "required_slots": result.required_slots,
        "response": result.response,
        "escalate": result.escalate,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--utterance", default=DEFAULT_UTTERANCE)
    args = parser.parse_args()

    print(json.dumps(run(args.utterance), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
