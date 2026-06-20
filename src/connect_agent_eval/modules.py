import dspy

from connect_agent_eval.labels import intent_display_name, normalize_intent
from connect_agent_eval.signatures import MultiTurnTriage, SingleTurnTriage
from connect_agent_eval.state import (
    ConversationState,
    apply_agent_result,
    update_slots_from_utterance,
)


class SingleTurnSupportAgent(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.triage = dspy.Predict(SingleTurnTriage)

    def forward(self, customer_utterance: str) -> dspy.Prediction:
        result = self.triage(customer_utterance=customer_utterance)
        result.intent = normalize_intent(result.intent)
        result.intent_display_name = intent_display_name(result.intent)
        return result


class MultiTurnSupportAgent(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.triage = dspy.Predict(MultiTurnTriage)

    def forward(
        self,
        customer_utterance: str,
        state: ConversationState,
        business_rules: str,
    ) -> dspy.Prediction:
        state.record_user(customer_utterance)
        state.slots = update_slots_from_utterance(state.slots, customer_utterance)

        deterministic_result = self._deterministic_transition(customer_utterance, state)
        if deterministic_result is not None:
            return deterministic_result

        result = self.triage(
            conversation_state=state.to_prompt_context(),
            business_rules=business_rules,
            customer_utterance=customer_utterance,
        )
        result.intent = normalize_intent(result.intent)
        result.intent_display_name = intent_display_name(result.intent)

        apply_agent_result(
            state,
            intent=result.intent,
            intent_display_name=result.intent_display_name,
            required_slots=result.required_slots,
            next_action=result.next_action,
            response=result.response,
            escalate=result.escalate,
        )
        result.state = state
        return result

    def _deterministic_transition(
        self,
        customer_utterance: str,
        state: ConversationState,
    ) -> dspy.Prediction | None:
        if (
            state.intent == "billing_issue"
            and state.slots.get("account_id")
            and state.slots.get("identity_verification")
            and state.last_agent_action in {"ask_identity_verification", "ask_account_id"}
        ):
            return self._build_prediction(
                state,
                intent="billing_issue",
                required_slots="none",
                next_action="explain_next_step",
                response=(
                    "ご本人様確認が完了しました。今月の請求内容を確認するため、"
                    "次に請求明細の確認へ進みます。"
                ),
                escalate="false",
            )

        if (
            state.intent == "billing_issue"
            and state.last_agent_action == "explain_next_step"
            and ("すぐ" in customer_utterance or "理由" in customer_utterance)
        ):
            return self._build_prediction(
                state,
                intent="billing_issue",
                required_slots="none",
                next_action="explain_next_step",
                response=(
                    "確認を進めます。自動確認で原因を特定できない場合は、"
                    "担当者へ引き継げるよう状況を整理します。"
                ),
                escalate="false",
            )

        return None

    def _build_prediction(
        self,
        state: ConversationState,
        *,
        intent: str,
        required_slots: str,
        next_action: str,
        response: str,
        escalate: str,
    ) -> dspy.Prediction:
        normalized_intent = normalize_intent(intent)
        display_name = intent_display_name(normalized_intent)
        apply_agent_result(
            state,
            intent=normalized_intent,
            intent_display_name=display_name,
            required_slots=required_slots,
            next_action=next_action,
            response=response,
            escalate=escalate,
        )
        return dspy.Prediction(
            intent=normalized_intent,
            intent_display_name=display_name,
            required_slots=required_slots,
            next_action=next_action,
            response=response,
            escalate=escalate,
            state=state,
        )
