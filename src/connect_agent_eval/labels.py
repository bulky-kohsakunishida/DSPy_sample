INTENT_DISPLAY_NAMES = {
    "billing_issue": "請求問い合わせ",
    "delivery_status": "配送状況確認",
    "cancel_request": "キャンセル依頼",
    "technical_support": "技術サポート",
    "human_handoff": "有人対応希望",
    "unknown": "不明",
}


def normalize_intent(intent: str) -> str:
    normalized = intent.strip()
    return normalized if normalized in INTENT_DISPLAY_NAMES else "unknown"


def intent_display_name(intent: str) -> str:
    return INTENT_DISPLAY_NAMES[normalize_intent(intent)]
