"""Step 1: DSPy から Ollama gemma4:12b へ接続できるか確認する。"""

import json

import dspy


def main() -> None:
    lm = dspy.LM(
        "openai/gemma4:12b",
        api_base="http://localhost:11434/v1",
        api_key="ollama",
        temperature=0.0,
        max_tokens=4096,
        cache=False,
        extra_body={"think": False},
    )
    dspy.configure(lm=lm)

    classify = dspy.Predict(
        "customer_utterance -> intent, required_slots, response, escalate"
    )
    result = classify(
        customer_utterance=(
            "今月の請求が急に高くなっています。理由を確認してもらえますか？"
        )
    )

    print(
        json.dumps(
            {
                "intent": result.intent,
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
