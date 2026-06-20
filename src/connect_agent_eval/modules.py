import dspy

from connect_agent_eval.labels import intent_display_name, normalize_intent
from connect_agent_eval.signatures import MultiTurnTriage, SingleTurnTriage
from connect_agent_eval.state import (
    ConversationState,
    apply_agent_result,
    update_slots_from_utterance,
)
from connect_agent_eval.tools import (
    create_case,
    get_billing_summary,
    handoff_to_human,
    lookup_customer,
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
        if state.intent == "unknown" and self._looks_like_billing_issue(customer_utterance):
            return self._build_prediction(
                state,
                intent="billing_issue",
                required_slots="identity_verification, account_id",
                next_action="ask_identity_verification",
                response=(
                    "請求についてお困りの状況を承知しました。詳細確認の前に、"
                    "ご本人様確認のためアカウントIDをお知らせください。"
                ),
                escalate="false",
            )

        if (
            state.intent == "billing_issue"
            and self._wants_human_handoff(customer_utterance)
        ):
            return self._handoff_for_billing(state, "顧客が有人対応を希望")

        if (
            state.intent == "billing_issue"
            and state.slots.get("account_id")
            and state.slots.get("identity_verification")
            and state.last_agent_action in {"ask_identity_verification", "ask_account_id"}
        ):
            customer = lookup_customer(state.slots["account_id"])
            state.tool_results["lookup_customer"] = customer
            if not customer["found"]:
                return self._handoff_for_billing(
                    state,
                    "アカウントIDに一致する顧客が見つからない",
                )

            state.slots["customer_name"] = customer["customer_name"]
            if not state.slots.get("issue_month"):
                return self._build_prediction(
                    state,
                    intent="billing_issue",
                    required_slots="issue_month",
                    next_action="confirm_issue_month",
                    response="ご本人様確認が完了しました。確認したい請求月をお知らせください。",
                    escalate="false",
                    tool_name="lookup_customer",
                    tool_result=customer,
                )

            return self._explain_billing_summary(state)

        if (
            state.intent == "billing_issue"
            and state.slots.get("account_id")
            and state.slots.get("identity_verification")
            and state.slots.get("issue_month")
            and state.last_agent_action == "confirm_issue_month"
        ):
            return self._explain_billing_summary(state)

        if (
            state.intent == "billing_issue"
            and state.last_agent_action == "explain_billing_summary"
            and self._shows_strong_frustration(customer_utterance)
        ):
            return self._handoff_for_billing(state, "請求説明後も顧客不満が強い")

        if (
            state.intent == "billing_issue"
            and state.last_agent_action == "explain_billing_summary"
        ):
            return self._build_prediction(
                state,
                intent="billing_issue",
                required_slots="none",
                next_action="explain_next_step",
                response=(
                    "ほかに確認したい請求項目があればお知らせください。"
                    "必要に応じて担当者への引き継ぎも可能です。"
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

    def _looks_like_billing_issue(self, utterance: str) -> bool:
        return any(keyword in utterance for keyword in ["請求", "料金", "明細", "高く"])

    def _wants_human_handoff(self, utterance: str) -> bool:
        return any(keyword in utterance for keyword in ["担当者", "有人", "オペレーター"])

    def _shows_strong_frustration(self, utterance: str) -> bool:
        return any(keyword in utterance for keyword in ["納得できない", "おかしい", "困る", "不満"])

    def _explain_billing_summary(self, state: ConversationState) -> dspy.Prediction:
        account_id = state.slots["account_id"]
        month = state.slots["issue_month"]
        summary = get_billing_summary(account_id, month)
        state.tool_results["get_billing_summary"] = summary

        if not summary["found"] or summary["requires_human_review"]:
            return self._handoff_for_billing(
                state,
                f"{month}の請求明細を自動確認できない",
            )

        difference = summary["amount_yen"] - summary["previous_amount_yen"]
        response = (
            f"{month}の請求は{summary['amount_yen']}円で、前回より{difference}円高くなっています。"
            f"主な理由は{summary['main_reason']}です。"
        )
        return self._build_prediction(
            state,
            intent="billing_issue",
            required_slots="none",
            next_action="explain_billing_summary",
            response=response,
            escalate="false",
            tool_name="get_billing_summary",
            tool_result=summary,
        )

    def _handoff_for_billing(
        self,
        state: ConversationState,
        reason: str,
    ) -> dspy.Prediction:
        account_id = state.slots.get("account_id") or "UNKNOWN"
        case = create_case(account_id, reason)
        handoff = handoff_to_human(
            summary=(
                f"intent={state.intent}, account_id={account_id}, "
                f"issue_month={state.slots.get('issue_month')}, reason={reason}"
            )
        )
        state.tool_results["create_case"] = case
        state.tool_results["handoff_to_human"] = handoff
        return self._build_prediction(
            state,
            intent="billing_issue",
            required_slots="none",
            next_action="handoff_to_human",
            response=(
                "自動確認だけでは対応が難しいため、請求担当者へ引き継ぎます。"
                f"受付番号は{case['case_id']}です。"
            ),
            escalate="true",
            tool_name="handoff_to_human",
            tool_result=handoff,
        )

    def _build_prediction(
        self,
        state: ConversationState,
        *,
        intent: str,
        required_slots: str,
        next_action: str,
        response: str,
        escalate: str,
        tool_name: str | None = None,
        tool_result: dict | None = None,
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
            tool_name=tool_name,
            tool_result=tool_result,
            state=state,
        )
