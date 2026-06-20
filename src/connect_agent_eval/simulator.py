from __future__ import annotations

from dataclasses import asdict

from connect_agent_eval.modules import MultiTurnSupportAgent
from connect_agent_eval.state import ConversationState


DEFAULT_BUSINESS_RULES = """
- あなたは請求問い合わせを扱うコンタクトセンターのAIエージェント。
- 本人確認が済むまで、請求額、明細、契約情報などの機微情報を開示しない。
- 請求問い合わせでは、本人確認と account_id が必要。
- 本人確認後に lookup_customer と get_billing_summary を使って請求内容を確認する。
- 自動確認できない請求、顧客情報不一致、強い不満、有人希望は create_case と handoff_to_human の対象にする。
- 顧客が強い不満を示しても、まず謝意を示し、確認に必要な情報を一つずつ集める。
- 自動対応で判断できない場合のみ有人対応へエスカレーションする。
- 応答は簡潔な日本語にする。
""".strip()


DEFAULT_TURNS = [
    "今月の請求が急に高くなっています。理由を確認してもらえますか？",
    "アカウントIDは ACC-123456 です。",
    "今月分です。できればすぐ理由を知りたいです。",
]


def run_conversation(
    turns: list[str] | None = None,
    business_rules: str = DEFAULT_BUSINESS_RULES,
) -> list[dict]:
    state = ConversationState()
    agent = MultiTurnSupportAgent()
    transcript = []

    for index, utterance in enumerate(turns or DEFAULT_TURNS, start=1):
        result = agent(
            customer_utterance=utterance,
            state=state,
            business_rules=business_rules,
        )
        transcript.append(
            {
                "turn": index,
                "user": utterance,
                "agent": {
                    "intent": result.intent,
                    "intent_display_name": result.intent_display_name,
                    "required_slots": result.required_slots,
                    "next_action": result.next_action,
                    "response": result.response,
                    "escalate": result.escalate,
                    "tool_name": getattr(result, "tool_name", None),
                    "tool_result": getattr(result, "tool_result", None),
                },
                "state": asdict(state),
            }
        )

    return transcript
