from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CustomerRecord:
    account_id: str
    customer_name: str
    plan_name: str
    status: str


@dataclass(frozen=True)
class BillingSummary:
    account_id: str
    month: str
    amount_yen: int
    previous_amount_yen: int
    main_reason: str
    line_items: list[str]
    requires_human_review: bool = False


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    account_id: str
    reason: str
    status: str


MOCK_CUSTOMERS = {
    "ACC-123456": CustomerRecord(
        account_id="ACC-123456",
        customer_name="テスト太郎",
        plan_name="スタンダードプラン",
        status="active",
    ),
}


MOCK_BILLING_SUMMARIES = {
    ("ACC-123456", "今月"): BillingSummary(
        account_id="ACC-123456",
        month="今月",
        amount_yen=12800,
        previous_amount_yen=7800,
        main_reason="キャンペーン割引の終了とデータ追加利用料の発生",
        line_items=[
            "キャンペーン割引終了: +3000円",
            "データ追加利用料: +2000円",
        ],
    ),
    ("ACC-123456", "先月"): BillingSummary(
        account_id="ACC-123456",
        month="先月",
        amount_yen=7800,
        previous_amount_yen=7800,
        main_reason="通常請求",
        line_items=["月額基本料金: 7800円"],
    ),
}


def lookup_customer(account_id: str) -> dict:
    record = MOCK_CUSTOMERS.get(account_id)
    if record is None:
        return {"found": False, "account_id": account_id}
    return {"found": True, **asdict(record)}


def get_billing_summary(account_id: str, month: str) -> dict:
    summary = MOCK_BILLING_SUMMARIES.get((account_id, month))
    if summary is None:
        return {
            "found": False,
            "account_id": account_id,
            "month": month,
            "requires_human_review": True,
        }
    return {"found": True, **asdict(summary)}


def create_case(account_id: str, reason: str) -> dict:
    suffix = account_id.replace("-", "")[-6:]
    record = CaseRecord(
        case_id=f"CASE-{suffix}",
        account_id=account_id,
        reason=reason,
        status="open",
    )
    return asdict(record)


def handoff_to_human(summary: str) -> dict:
    return {
        "handoff": True,
        "queue": "billing_support",
        "summary": summary,
    }
