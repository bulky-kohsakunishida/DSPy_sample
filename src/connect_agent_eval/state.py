from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    role: str
    content: str


@dataclass
class ConversationState:
    intent: str = "unknown"
    intent_display_name: str = "不明"
    slots: dict[str, str | None] = field(
        default_factory=lambda: {
            "customer_name": None,
            "account_id": None,
            "issue_month": None,
            "identity_verification": None,
        }
    )
    history: list[ConversationTurn] = field(default_factory=list)
    last_agent_action: str | None = None
    handoff_required: bool = False
    tool_results: dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        payload: dict[str, Any] = asdict(self)
        payload["history"] = [
            {"role": turn.role, "content": turn.content}
            for turn in self.history[-6:]
        ]
        return str(payload)

    def record_user(self, content: str) -> None:
        self.history.append(ConversationTurn(role="user", content=content))

    def record_agent(self, content: str) -> None:
        self.history.append(ConversationTurn(role="agent", content=content))


def update_slots_from_utterance(
    slots: dict[str, str | None],
    utterance: str,
) -> dict[str, str | None]:
    updated = dict(slots)

    account_match = re.search(r"(?:ACC|acct|account)[-_]?\d{4,}", utterance, re.I)
    if account_match:
        updated["account_id"] = account_match.group(0)
        updated["identity_verification"] = "verified_by_account_id"

    if "今月" in utterance:
        updated["issue_month"] = "今月"
    elif "先月" in utterance:
        updated["issue_month"] = "先月"
    else:
        month_match = re.search(r"(\d{1,2})月", utterance)
        if month_match:
            updated["issue_month"] = f"{month_match.group(1)}月"

    return updated


def apply_agent_result(
    state: ConversationState,
    *,
    intent: str,
    intent_display_name: str,
    required_slots: str,
    next_action: str,
    response: str,
    escalate: str,
) -> ConversationState:
    state.intent = intent
    state.intent_display_name = intent_display_name
    state.last_agent_action = next_action
    state.handoff_required = escalate.strip().lower() == "true"

    for slot in [slot.strip() for slot in required_slots.split(",")]:
        if slot and slot != "none" and slot not in state.slots:
            state.slots[slot] = None

    state.record_agent(response)
    return state
