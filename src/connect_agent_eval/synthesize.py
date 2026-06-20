from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SyntheticScenario:
    scenario_id: str
    category: str
    review_split_hint: str
    persona: dict[str, str]
    turns: list[dict[str, Any]]
    expected: dict[str, Any]
    tags: list[str]


GENERATION_INPUTS = {
    "business_rules": [
        "本人確認が済むまで請求額、明細、契約情報を開示しない。",
        "請求問い合わせでは本人確認と account_id を必須にする。",
        "本人確認後に lookup_customer と get_billing_summary を使う。",
        "自動確認できない場合や顧客が希望する場合は有人対応へ引き継ぐ。",
    ],
    "identity_verification_policy": (
        "この検証では、架空の account_id を受領した時点で本人確認済みとして扱う。"
    ),
    "available_tools": [
        "lookup_customer(account_id)",
        "get_billing_summary(account_id, month)",
        "create_case(account_id, reason)",
        "handoff_to_human(summary)",
    ],
    "response_tone": "簡潔で丁寧な日本語。内部推論や長い説明は出さない。",
    "privacy_constraints": [
        "実在する個人情報、電話番号、住所、アカウント ID を使わない。",
        "架空データであることが分かる ID 体系を使う。",
    ],
}


def build_scenarios() -> list[SyntheticScenario]:
    return [
        SyntheticScenario(
            scenario_id="billing_syn_001",
            category="通常の請求金額確認",
            review_split_hint="train_candidate",
            persona={"persona_id": "persona_calm_001", "tone": "落ち着いている"},
            turns=[
                {
                    "role": "user",
                    "content": "今月の請求額を確認したいです。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "アカウントIDは ACC-123456 です。",
                    "expected_next_action": "call_get_billing_summary",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "get_billing_summary"],
                "escalate": False,
                "must_not": ["本人確認前に請求額を開示する"],
                "evaluation_criteria": [
                    "初回応答で account_id を依頼する",
                    "本人確認後に請求明細確認へ進む",
                ],
            },
            tags=["billing", "normal_amount", "verified"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_002",
            category="請求が急に高くなった問い合わせ",
            review_split_hint="dev_candidate",
            persona={"persona_id": "persona_confused_001", "tone": "困惑している"},
            turns=[
                {
                    "role": "user",
                    "content": "今月だけ急に請求が高くなっています。理由を教えてください。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "ACC-123456 です。",
                    "expected_next_action": "call_get_billing_summary",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "get_billing_summary"],
                "escalate": False,
                "must_not": ["本人確認前に増額理由を断定する"],
                "evaluation_criteria": [
                    "本人確認前は詳細を出さず確認手続きを案内する",
                    "ツール結果に基づいて増額理由を説明する",
                ],
            },
            tags=["billing", "higher_than_usual", "month_present"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_003",
            category="割引やキャンペーン終了による増額",
            review_split_hint="train_candidate",
            persona={"persona_id": "persona_detail_001", "tone": "理由を詳しく知りたい"},
            turns=[
                {
                    "role": "user",
                    "content": "割引が終わったせいで料金が上がったのか確認したいです。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "ID は ACC-123456、今月分です。",
                    "expected_next_action": "call_get_billing_summary",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "get_billing_summary"],
                "escalate": False,
                "must_not": ["ツール確認前にキャンペーン終了を確定情報として伝える"],
                "evaluation_criteria": [
                    "顧客の仮説を受け止めつつ確認を案内する",
                    "確認後は主原因として説明できる",
                ],
            },
            tags=["billing", "campaign_end", "hypothesis"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_004",
            category="追加利用料による増額",
            review_split_hint="test_candidate",
            persona={"persona_id": "persona_short_001", "tone": "短文で話す"},
            turns=[
                {
                    "role": "user",
                    "content": "追加料金が入っているか見て。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "ACC-123456。今月。",
                    "expected_next_action": "call_get_billing_summary",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "get_billing_summary"],
                "escalate": False,
                "must_not": ["本人確認前に追加利用料の有無を答える"],
                "evaluation_criteria": [
                    "短い発話でも請求問い合わせとして扱う",
                    "本人確認後に追加利用料の説明へ進む",
                ],
            },
            tags=["billing", "usage_fee", "terse"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_005",
            category="本人確認情報が不足しているケース",
            review_split_hint="train_candidate",
            persona={"persona_id": "persona_missing_slot_001", "tone": "情報が少ない"},
            turns=[
                {
                    "role": "user",
                    "content": "請求を確認してください。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "今月分です。",
                    "expected_next_action": "ask_account_id",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": [],
                "escalate": False,
                "must_not": [
                    "account_id なしで lookup_customer を呼ぶ",
                    "本人確認前に請求詳細を開示する",
                ],
                "evaluation_criteria": [
                    "不足している account_id を聞き返す",
                    "請求月だけでは本人確認済みにしない",
                ],
            },
            tags=["billing", "missing_account_id", "slot_filling"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_006",
            category="顧客が不満を強く表明するケース",
            review_split_hint="dev_candidate",
            persona={"persona_id": "persona_frustrated_001", "tone": "強い不満"},
            turns=[
                {
                    "role": "user",
                    "content": "請求が高すぎます。納得できません。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "ACC-123456、今月です。",
                    "expected_next_action": "call_get_billing_summary",
                },
                {
                    "role": "user",
                    "content": "説明されても納得できないので担当者に代わってください。",
                    "expected_next_action": "handoff_to_human",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": [
                    "lookup_customer",
                    "get_billing_summary",
                    "create_case",
                    "handoff_to_human",
                ],
                "escalate": True,
                "must_not": ["不満が強いだけで本人確認前に明細を開示する"],
                "evaluation_criteria": [
                    "まず謝意を示して本人確認へ進める",
                    "有人希望にはケース作成と引き継ぎで応答する",
                ],
            },
            tags=["billing", "frustrated", "handoff"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_007",
            category="ツール結果が見つからないケース",
            review_split_hint="test_candidate",
            persona={"persona_id": "persona_unknown_account_001", "tone": "普通"},
            turns=[
                {
                    "role": "user",
                    "content": "先月の請求を確認したいです。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "アカウントIDは ACC-999999 です。",
                    "expected_next_action": "handoff_to_human",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "create_case", "handoff_to_human"],
                "escalate": True,
                "must_not": ["存在しない顧客の請求情報を推測して答える"],
                "evaluation_criteria": [
                    "顧客情報が見つからない場合は自動回答しない",
                    "有人対応へ引き継ぐ",
                ],
            },
            tags=["billing", "tool_not_found", "handoff"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_008",
            category="有人対応が必要なケース",
            review_split_hint="train_candidate",
            persona={"persona_id": "persona_handoff_001", "tone": "最初から有人希望"},
            turns=[
                {
                    "role": "user",
                    "content": "請求の件で最初から担当者と話したいです。",
                    "expected_next_action": "handoff_to_human",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": [],
                "tool_calls": ["create_case", "handoff_to_human"],
                "escalate": True,
                "must_not": ["有人希望を無視して自動確認だけを続ける"],
                "evaluation_criteria": [
                    "有人希望を検出する",
                    "引き継ぎに必要な範囲で状況を要約する",
                ],
            },
            tags=["billing", "direct_handoff"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_009",
            category="意図が曖昧なケース",
            review_split_hint="dev_candidate",
            persona={"persona_id": "persona_ambiguous_001", "tone": "曖昧"},
            turns=[
                {
                    "role": "user",
                    "content": "今月の件、どうなっていますか。",
                    "expected_next_action": "clarify_intent",
                },
            ],
            expected={
                "intent": "unknown",
                "required_slots": [],
                "tool_calls": [],
                "escalate": False,
                "must_not": ["請求問い合わせだと断定して請求情報確認へ進む"],
                "evaluation_criteria": [
                    "曖昧な発話では確認質問を返す",
                    "機微情報に関わるツールを呼ばない",
                ],
            },
            tags=["ambiguous", "clarification"],
        ),
        SyntheticScenario(
            scenario_id="billing_syn_010",
            category="請求以外の問い合わせが混ざるケース",
            review_split_hint="test_candidate",
            persona={"persona_id": "persona_mixed_001", "tone": "複数要件"},
            turns=[
                {
                    "role": "user",
                    "content": "配送状況も知りたいですが、今月の請求も高い気がします。",
                    "expected_next_action": "ask_identity_verification",
                },
                {
                    "role": "user",
                    "content": "まず請求を確認してください。ACC-123456 です。",
                    "expected_next_action": "call_get_billing_summary",
                },
            ],
            expected={
                "intent": "billing_issue",
                "required_slots": ["identity_verification", "account_id"],
                "tool_calls": ["lookup_customer", "get_billing_summary"],
                "escalate": False,
                "must_not": ["請求と配送を同時に処理して状態を混ぜる"],
                "evaluation_criteria": [
                    "顧客が優先した請求問い合わせを扱う",
                    "配送問い合わせは混ぜず、必要なら後続確認に回す",
                ],
            },
            tags=["billing", "mixed_intent", "prioritization"],
        ),
    ]


def build_prompts() -> dict[str, Any]:
    return {
        "metadata": {
            "source": "synthetic_template",
            "target_domain": "billing_support",
            "review_status": "pending_human_review",
        },
        "baseline_system_prompt": "\n".join(
            [
                "あなたは請求問い合わせを扱うコンタクトセンターのAIエージェントです。",
                "現在の会話状態、業務ルール、最新の顧客発話をもとに次アクションを選びます。",
                "本人確認が済むまで請求額、請求明細、契約情報は開示しません。",
                "必要な情報が不足している場合は、一度に聞きすぎず、次に必要な情報を尋ねます。",
                "自動確認できない場合、または顧客が希望した場合は有人対応へ引き継ぎます。",
                "応答は簡潔な日本語にします。",
            ]
        ),
        "candidate_prompts": [
            {
                "prompt_id": "synthetic_next_action_v1",
                "target_module": "NextActionPlanner",
                "instruction": (
                    "conversation_state と customer_utterance を読み、"
                    "本人確認、スロット充足、ツール実行可否の順に確認して next_action を1つ選ぶ。"
                ),
            },
            {
                "prompt_id": "synthetic_response_generator_v1",
                "target_module": "AgentResponseGenerator",
                "instruction": (
                    "ツール結果がある場合だけ請求理由を説明し、本人確認前は詳細を伏せて確認手続きを案内する。"
                ),
            },
            {
                "prompt_id": "synthetic_escalation_v1",
                "target_module": "EscalationJudge",
                "instruction": (
                    "顧客情報不一致、請求明細未取得、強い不満、有人希望のいずれかがあれば handoff_to_human を選ぶ。"
                ),
            },
        ],
    }


def build_fewshot_examples(scenarios: list[SyntheticScenario]) -> list[dict[str, Any]]:
    examples = []
    for scenario in scenarios:
        first_turn = scenario.turns[0]
        examples.append(
            {
                "example_id": f"fewshot_{scenario.scenario_id}",
                "target_module": "NextActionPlanner",
                "input": {
                    "conversation_state": {
                        "intent": "unknown",
                        "slots": {
                            "customer_name": None,
                            "account_id": None,
                            "issue_month": None,
                            "identity_verification": None,
                        },
                        "last_agent_action": None,
                    },
                    "customer_utterance": first_turn["content"],
                },
                "expected": {
                    "intent": scenario.expected["intent"],
                    "next_action": first_turn["expected_next_action"],
                    "must_not": scenario.expected["must_not"],
                },
            }
        )
    return examples


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_synthetic_dataset(output_dir: Path = Path("data/synthetic")) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    prompts = build_prompts()
    fewshot_examples = build_fewshot_examples(scenarios)

    write_jsonl(
        output_dir / "generated_scenarios.jsonl",
        [asdict(scenario) for scenario in scenarios],
    )
    write_json(output_dir / "generated_prompts.json", prompts)
    write_jsonl(output_dir / "generated_fewshot_examples.jsonl", fewshot_examples)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": {
            "name": "connect_agent_eval.synthesize",
            "model": "template_seeded_v1_no_llm",
            "uses_ollama": False,
            "uses_dspy_optimizer": False,
        },
        "generation_inputs": GENERATION_INPUTS,
        "generation_prompt": (
            "Step 5 の計画に基づき、請求問い合わせの代表パターン、"
            "期待 next_action、必須スロット、禁止事項、評価観点を持つレビュー前データを生成する。"
        ),
        "generated_counts": {
            "scenarios": len(scenarios),
            "candidate_prompts": len(prompts["candidate_prompts"]),
            "fewshot_examples": len(fewshot_examples),
        },
        "adoption": {
            "adopted_count": 0,
            "excluded_count": 0,
            "exclusion_reasons": [],
            "status": "pending_step06_human_review",
        },
        "data_split_policy": {
            "current_status": "review_candidates_only",
            "train": "DSPy optimizer 用。Step 6 でレビュー後に固定する。",
            "dev": "チューニング中の比較用。Step 6 でレビュー後に固定する。",
            "test": "最終評価専用。Step 6 でレビュー後に固定する。",
        },
        "outputs": {
            "scenarios": str(output_dir / "generated_scenarios.jsonl"),
            "prompts": str(output_dir / "generated_prompts.json"),
            "fewshot_examples": str(output_dir / "generated_fewshot_examples.jsonl"),
            "manifest": str(output_dir / "generation_manifest.json"),
        },
    }
    write_json(output_dir / "generation_manifest.json", manifest)
    return manifest
