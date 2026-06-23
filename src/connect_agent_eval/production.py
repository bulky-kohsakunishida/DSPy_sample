from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_ACTIONS = [
    "ask_identity_verification",
    "ask_account_id",
    "clarify_intent",
    "call_get_billing_summary",
    "handoff_to_human",
]

DEFAULT_BUSINESS_RULES = """
- 本人確認が済むまで請求額、請求明細、契約情報を開示しない。
- 請求問い合わせでは本人確認と account_id が必要。
- account_id と本人確認がそろうまで get_billing_summary を呼ばない。
- 顧客が有人対応を希望した場合は handoff_to_human を選ぶ。
- 意図が曖昧な場合は clarify_intent を選ぶ。
""".strip()

DEFAULT_CONVERSATION_STATE = {
    "intent": "unknown",
    "slots": {
        "customer_name": None,
        "account_id": None,
        "issue_month": None,
        "identity_verification": None,
    },
    "last_agent_action": None,
    "available_tools": [
        "lookup_customer",
        "get_billing_summary",
        "create_case",
        "handoff_to_human",
    ],
    "must_not": ["本人確認前に請求詳細を開示しない"],
}


@dataclass(frozen=True)
class ProductionExportResult:
    prompt_path: Path
    manifest_path: Path
    prompt_id: str
    source_run_dir: Path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def normalize_action(action: str) -> str:
    first_line = action.strip().splitlines()[0] if action.strip() else ""
    return first_line.strip("`'\"。、 ")


def load_current_prompt_record(current_path: Path) -> dict[str, Any]:
    record = read_json(current_path)
    required_keys = {"path", "prompt_id", "score", "source", "target_module"}
    missing = sorted(required_keys - set(record))
    if missing:
        raise ValueError(f"{current_path} に必要なキーがありません: {missing}")
    return record


def extract_optimized_instruction(run_dir: Path) -> str:
    artifacts_path = run_dir / "optimizer_artifacts.json"
    if not artifacts_path.exists():
        raise FileNotFoundError(
            f"{artifacts_path} がありません。最適化 run から本番プロンプトを作るには "
            "optimizer_artifacts.json が必要です。"
        )

    artifacts = read_json(artifacts_path)
    predictors = artifacts.get("predictors") or []
    if not predictors:
        raise ValueError(f"{artifacts_path} に predictors がありません。")

    instruction = predictors[0].get("instruction")
    if not instruction:
        raise ValueError(f"{artifacts_path} の先頭 predictor に instruction がありません。")
    return instruction.strip()


def build_production_prompt(
    *,
    baseline_prompt: str,
    optimized_instruction: str,
    source_record: dict[str, Any],
) -> str:
    allowed_actions = ", ".join(ALLOWED_ACTIONS)
    return f"""# NextActionPlanner Production Prompt

## Base Role

{baseline_prompt.strip()}

## Optimized Decision Policy

{optimized_instruction}

## Runtime Inputs

Conversation State:
{{{{conversation_state}}}}

Business Rules:
{{{{business_rules}}}}

Customer Utterance:
{{{{customer_utterance}}}}

## Output Contract

Return exactly one action label.
Allowed values: {allowed_actions}

Do not output explanations, JSON, markdown, bullet points, or extra text.

## Action Definitions

- `ask_identity_verification`: Ask the customer to complete identity verification. Use this as the first action for a clear billing inquiry when both `account_id` and `identity_verification` are missing.
- `ask_account_id`: Ask only for `account_id` when identity verification is already satisfied but account_id is still missing.
- `clarify_intent`: Ask a clarification question only when the customer intent is truly ambiguous.
- `call_get_billing_summary`: Call the billing summary tool only when both `account_id` and `identity_verification` are already present.
- `handoff_to_human`: Transfer to a human agent when the customer explicitly requests a human agent.

If both `account_id` and `identity_verification` are missing for a billing inquiry, choose `ask_identity_verification`, not `ask_account_id`.

## Source

- prompt_id: {source_record["prompt_id"]}
- optimizer: {source_record.get("optimizer") or "none"}
- score: {source_record.get("score")}
- source_run: {source_record["path"]}
"""


def export_current_prompt_to_production(
    *,
    current_path: Path = Path("outputs/curated/prompts/current.json"),
    baseline_prompt_path: Path = Path("data/prompts/baseline_system_prompt.md"),
    output_dir: Path = Path("outputs/curated/production"),
) -> ProductionExportResult:
    source_record = load_current_prompt_record(current_path)
    run_dir = Path(source_record["path"])
    baseline_prompt = baseline_prompt_path.read_text(encoding="utf-8")
    optimized_instruction = extract_optimized_instruction(run_dir)
    production_prompt = build_production_prompt(
        baseline_prompt=baseline_prompt,
        optimized_instruction=optimized_instruction,
        source_record=source_record,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = output_dir / "next_action_planner_prompt.md"
    manifest_path = output_dir / "next_action_planner_manifest.json"
    prompt_path.write_text(production_prompt.rstrip() + "\n", encoding="utf-8")
    write_json(
        manifest_path,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "prompt_path": str(prompt_path),
            "source_current_path": str(current_path),
            "source_prompt_id": source_record["prompt_id"],
            "source_run_dir": str(run_dir),
            "source_score": source_record.get("score"),
            "source_optimizer": source_record.get("optimizer"),
            "target_module": source_record.get("target_module"),
            "runtime": "ollama_api_chat_without_dspy",
            "allowed_actions": ALLOWED_ACTIONS,
        },
    )
    return ProductionExportResult(
        prompt_path=prompt_path,
        manifest_path=manifest_path,
        prompt_id=source_record["prompt_id"],
        source_run_dir=run_dir,
    )


def render_prompt(
    *,
    prompt_template: str,
    conversation_state: dict[str, Any] | str,
    business_rules: str,
    customer_utterance: str,
) -> str:
    state_text = (
        conversation_state
        if isinstance(conversation_state, str)
        else json.dumps(conversation_state, ensure_ascii=False, sort_keys=True)
    )
    return (
        prompt_template.replace("{{conversation_state}}", state_text)
        .replace("{{business_rules}}", business_rules)
        .replace("{{customer_utterance}}", customer_utterance)
    )


def call_ollama_chat(
    *,
    prompt: str,
    model: str = "gemma4:12b",
    base_url: str = "http://localhost:11434",
    timeout_seconds: float = 120.0,
) -> str:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0, "num_predict": 32},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Ollama API に接続できません。ollama serve と対象モデルを確認してください。"
        ) from exc

    content = payload.get("message", {}).get("content", "")
    action = normalize_action(content)
    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"許可されていない action が返りました: {action!r}. raw={content!r}"
        )
    return action


def run_production_next_action(
    *,
    prompt_path: Path = Path("outputs/curated/production/next_action_planner_prompt.md"),
    conversation_state: dict[str, Any] | str = DEFAULT_CONVERSATION_STATE,
    business_rules: str = DEFAULT_BUSINESS_RULES,
    customer_utterance: str = "今月だけ急に請求が高くなっています。理由を教えてください。",
    model: str = "gemma4:12b",
    base_url: str = "http://localhost:11434",
) -> str:
    prompt_template = prompt_path.read_text(encoding="utf-8")
    rendered_prompt = render_prompt(
        prompt_template=prompt_template,
        conversation_state=conversation_state,
        business_rules=business_rules,
        customer_utterance=customer_utterance,
    )
    return call_ollama_chat(prompt=rendered_prompt, model=model, base_url=base_url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--current-path",
        type=Path,
        default=Path("outputs/curated/prompts/current.json"),
    )
    parser.add_argument(
        "--baseline-prompt-path",
        type=Path,
        default=Path("data/prompts/baseline_system_prompt.md"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/curated/production"))
    parser.add_argument("--run-demo", action="store_true")
    parser.add_argument("--model", default="gemma4:12b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    args = parser.parse_args()

    export_result = export_current_prompt_to_production(
        current_path=args.current_path,
        baseline_prompt_path=args.baseline_prompt_path,
        output_dir=args.output_dir,
    )
    payload: dict[str, Any] = {
        "prompt_path": str(export_result.prompt_path),
        "manifest_path": str(export_result.manifest_path),
        "source_prompt_id": export_result.prompt_id,
        "source_run_dir": str(export_result.source_run_dir),
    }
    if args.run_demo:
        payload["demo_next_action"] = run_production_next_action(
            prompt_path=export_result.prompt_path,
            model=args.model,
            base_url=args.base_url,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
