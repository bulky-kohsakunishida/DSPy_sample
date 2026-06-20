from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_INTENTS = {
    "billing_issue",
    "delivery_status",
    "cancel_request",
    "technical_support",
    "human_handoff",
    "unknown",
}

VALID_NEXT_ACTIONS = {
    "ask_identity_verification",
    "ask_account_id",
    "clarify_intent",
    "call_get_billing_summary",
    "handoff_to_human",
}

REVIEW_CRITERIA = [
    "intent が許可ラベルに含まれる",
    "各 turn に role、content、expected_next_action がある",
    "expected_next_action が許可アクションに含まれる",
    "請求問い合わせには本人確認前の禁止事項が明示されている",
    "tool_calls が本人確認と account_id の制約に反していない",
    "実在しそうな電話番号や住所を含まない",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def has_realistic_phone_number(text: str) -> bool:
    return re.search(r"\b0\d{1,4}-\d{1,4}-\d{3,4}\b", text) is not None


def has_address_like_text(text: str) -> bool:
    return any(keyword in text for keyword in ["東京都", "大阪府", "北海道", "丁目", "番地"])


def review_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    issues = []
    expected = scenario.get("expected", {})
    turns = scenario.get("turns", [])
    all_text = json.dumps(scenario, ensure_ascii=False)

    if expected.get("intent") not in VALID_INTENTS:
        issues.append("invalid_intent")

    if not turns:
        issues.append("missing_turns")

    for index, turn in enumerate(turns, start=1):
        if not turn.get("role") or not turn.get("content"):
            issues.append(f"turn_{index}_missing_role_or_content")
        if turn.get("expected_next_action") not in VALID_NEXT_ACTIONS:
            issues.append(f"turn_{index}_invalid_next_action")

    if expected.get("intent") == "billing_issue":
        must_not = expected.get("must_not", [])
        if not any("本人確認前" in item for item in must_not):
            issues.append("missing_pre_verification_disclosure_guard")

        tool_calls = set(expected.get("tool_calls", []))
        required_slots = set(expected.get("required_slots", []))
        can_call_billing_tool = {
            "identity_verification",
            "account_id",
        }.issubset(required_slots)
        if "get_billing_summary" in tool_calls and not can_call_billing_tool:
            issues.append("billing_tool_without_required_identity_slots")

    if has_realistic_phone_number(all_text):
        issues.append("contains_phone_number_like_text")

    if has_address_like_text(all_text):
        issues.append("contains_address_like_text")

    return {
        "scenario_id": scenario.get("scenario_id"),
        "accepted": not issues,
        "issues": issues,
    }


def freeze_scenario(scenario: dict[str, Any], split: str) -> dict[str, Any]:
    frozen = dict(scenario)
    frozen["scenario_id"] = scenario["scenario_id"].replace("billing_syn_", "billing_")
    frozen["source_scenario_id"] = scenario["scenario_id"]
    frozen["split"] = split
    frozen["review_status"] = "accepted_step06"
    frozen["review_notes"] = [
        "Step 5 の合成候補を機械的レビューで確認し、初期評価データとして固定した。",
        "本データセットは Step 7 の optimizer 前に必要に応じて人手レビューで更新する。",
    ]
    return frozen


def split_for_scenario(scenario: dict[str, Any]) -> str:
    hint = scenario.get("review_split_hint", "")
    if hint.startswith("train"):
        return "train"
    if hint.startswith("dev"):
        return "dev"
    if hint.startswith("test"):
        return "test"
    return "train"


def freeze_prompts(source_path: Path, output_dir: Path) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    prompts_dir = output_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = prompts_dir / "baseline_system_prompt.md"
    baseline_path.write_text(source["baseline_system_prompt"] + "\n", encoding="utf-8")

    candidate_payload = {
        "metadata": {
            **source["metadata"],
            "review_status": "accepted_step06",
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        },
        "candidate_prompts": source["candidate_prompts"],
    }
    candidate_path = prompts_dir / "candidate_prompts.json"
    write_json(candidate_path, candidate_payload)

    return {
        "baseline_system_prompt": str(baseline_path),
        "candidate_prompts": str(candidate_path),
        "candidate_prompt_count": len(source["candidate_prompts"]),
    }


def review_and_freeze_dataset(
    synthetic_dir: Path = Path("data/synthetic"),
    output_root: Path = Path("data"),
) -> dict[str, Any]:
    scenarios = read_jsonl(synthetic_dir / "generated_scenarios.jsonl")
    reviews = [review_scenario(scenario) for scenario in scenarios]
    accepted_ids = {review["scenario_id"] for review in reviews if review["accepted"]}
    rejected_reviews = [review for review in reviews if not review["accepted"]]

    frozen_by_split: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "dev": [],
        "test": [],
    }
    for scenario in scenarios:
        if scenario["scenario_id"] not in accepted_ids:
            continue
        split = split_for_scenario(scenario)
        frozen_by_split[split].append(freeze_scenario(scenario, split))

    scenario_dir = output_root / "scenarios"
    write_jsonl(scenario_dir / "train_billing_support.jsonl", frozen_by_split["train"])
    write_jsonl(scenario_dir / "dev_billing_support.jsonl", frozen_by_split["dev"])
    write_jsonl(scenario_dir / "test_billing_support.jsonl", frozen_by_split["test"])

    prompt_outputs = freeze_prompts(
        synthetic_dir / "generated_prompts.json",
        output_root,
    )

    review_report = {
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "scenarios": str(synthetic_dir / "generated_scenarios.jsonl"),
            "prompts": str(synthetic_dir / "generated_prompts.json"),
        },
        "review_criteria": REVIEW_CRITERIA,
        "counts": {
            "reviewed": len(scenarios),
            "accepted": len(accepted_ids),
            "rejected": len(rejected_reviews),
            "train": len(frozen_by_split["train"]),
            "dev": len(frozen_by_split["dev"]),
            "test": len(frozen_by_split["test"]),
        },
        "reviews": reviews,
        "rejected": rejected_reviews,
        "outputs": {
            "train": str(scenario_dir / "train_billing_support.jsonl"),
            "dev": str(scenario_dir / "dev_billing_support.jsonl"),
            "test": str(scenario_dir / "test_billing_support.jsonl"),
            "review_report": str(scenario_dir / "review_report.json"),
            **prompt_outputs,
        },
    }
    write_json(scenario_dir / "review_report.json", review_report)
    return review_report
