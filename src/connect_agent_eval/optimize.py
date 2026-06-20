from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dspy

from connect_agent_eval.lm import configure_lm
from connect_agent_eval.settings import LMSettings
from connect_agent_eval.signatures import NextActionPlanner


BUSINESS_RULES = """
- 本人確認が済むまで請求額、請求明細、契約情報を開示しない。
- 請求問い合わせでは本人確認と account_id が必要。
- account_id と本人確認がそろうまで get_billing_summary を呼ばない。
- 顧客が有人対応を希望した場合は handoff_to_human を選ぶ。
- 意図が曖昧な場合は clarify_intent を選ぶ。
""".strip()


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    correct: int
    score: float
    cases: list[dict[str, Any]]


class NextActionPlannerModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.plan = dspy.Predict(NextActionPlanner)

    def forward(
        self,
        conversation_state: str,
        business_rules: str,
        customer_utterance: str,
    ) -> dspy.Prediction:
        return self.plan(
            conversation_state=conversation_state,
            business_rules=business_rules,
            customer_utterance=customer_utterance,
        )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def normalize_action(action: str) -> str:
    return action.strip().splitlines()[0].strip("`'\"。、 ")


def expected_intent_for_turn(scenario: dict[str, Any]) -> str:
    return scenario["expected"]["intent"]


def build_state_for_turn(scenario: dict[str, Any], turn_index: int) -> dict[str, Any]:
    expected_intent = expected_intent_for_turn(scenario)
    slots = {
        "customer_name": None,
        "account_id": None,
        "issue_month": None,
        "identity_verification": None,
    }

    if turn_index > 0:
        previous_text = " ".join(
            turn["content"] for turn in scenario["turns"][:turn_index]
        )
        if "ACC-" in previous_text:
            slots["account_id"] = previous_text.split("ACC-", 1)[1].split()[0].strip("。、")
            slots["account_id"] = f"ACC-{slots['account_id']}"
            slots["identity_verification"] = "verified_by_account_id"
        if "今月" in previous_text:
            slots["issue_month"] = "今月"
        elif "先月" in previous_text:
            slots["issue_month"] = "先月"

    return {
        "intent": expected_intent if turn_index > 0 else "unknown",
        "slots": slots,
        "last_agent_action": None if turn_index == 0 else scenario["turns"][turn_index - 1]["expected_next_action"],
        "available_tools": [
            "lookup_customer",
            "get_billing_summary",
            "create_case",
            "handoff_to_human",
        ],
        "must_not": scenario["expected"]["must_not"],
    }


def build_examples(path: Path) -> list[dspy.Example]:
    scenarios = read_jsonl(path)
    examples: list[dspy.Example] = []
    for scenario in scenarios:
        for turn_index, turn in enumerate(scenario["turns"]):
            examples.append(
                dspy.Example(
                    scenario_id=scenario["scenario_id"],
                    turn_index=turn_index + 1,
                    conversation_state=json.dumps(
                        build_state_for_turn(scenario, turn_index),
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    business_rules=BUSINESS_RULES,
                    customer_utterance=turn["content"],
                    next_action=turn["expected_next_action"],
                ).with_inputs(
                    "conversation_state",
                    "business_rules",
                    "customer_utterance",
                )
            )
    return examples


def next_action_metric(example: dspy.Example, prediction: dspy.Prediction, trace=None) -> bool:
    expected = normalize_action(example.next_action)
    actual = normalize_action(getattr(prediction, "next_action", ""))
    return actual == expected


def evaluate_module(module: dspy.Module, examples: list[dspy.Example]) -> EvaluationResult:
    cases = []
    correct = 0
    for example in examples:
        try:
            prediction = module(
                conversation_state=example.conversation_state,
                business_rules=example.business_rules,
                customer_utterance=example.customer_utterance,
            )
            actual = normalize_action(getattr(prediction, "next_action", ""))
            error = None
        except Exception as exc:  # noqa: BLE001
            actual = ""
            error = f"{type(exc).__name__}: {exc}"

        expected = normalize_action(example.next_action)
        is_correct = actual == expected
        correct += int(is_correct)
        cases.append(
            {
                "scenario_id": example.scenario_id,
                "turn_index": example.turn_index,
                "customer_utterance": example.customer_utterance,
                "expected_next_action": expected,
                "actual_next_action": actual,
                "correct": is_correct,
                "error": error,
            }
        )

    total = len(examples)
    return EvaluationResult(
        total=total,
        correct=correct,
        score=correct / total if total else 0.0,
        cases=cases,
    )


def extract_labeled_demos(module: dspy.Module) -> list[dict[str, Any]]:
    demos = []
    for predictor in module.predictors():
        for demo in getattr(predictor, "demos", []):
            demos.append(
                {
                    "conversation_state": getattr(demo, "conversation_state", None),
                    "business_rules": getattr(demo, "business_rules", None),
                    "customer_utterance": getattr(demo, "customer_utterance", None),
                    "next_action": getattr(demo, "next_action", None),
                }
            )
    return demos


def save_prompt_run(
    *,
    run_dir: Path,
    prompt_text: str,
    metadata: dict[str, Any],
    eval_result: EvaluationResult,
    fewshot_examples: list[dict[str, Any]] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.md").write_text(prompt_text + "\n", encoding="utf-8")
    write_json(run_dir / "metadata.json", metadata)
    write_json(
        run_dir / "eval_summary.json",
        {
            "total": eval_result.total,
            "correct": eval_result.correct,
            "score": eval_result.score,
            "cases": eval_result.cases,
        },
    )
    if fewshot_examples is not None:
        write_jsonl(run_dir / "fewshot_examples.jsonl", fewshot_examples)


def run_step7_prompt_optimization(
    *,
    train_path: Path = Path("data/scenarios/train_billing_support.jsonl"),
    dev_path: Path = Path("data/scenarios/dev_billing_support.jsonl"),
    baseline_prompt_path: Path = Path("data/prompts/baseline_system_prompt.md"),
    output_root: Path = Path("outputs/prompts"),
    settings: LMSettings = LMSettings(
        model="ollama_chat/gemma4:12b",
        api_base="http://localhost:11434",
        max_tokens=64,
    ),
) -> dict[str, Any]:
    configure_lm(settings)

    trainset = build_examples(train_path)
    devset = build_examples(dev_path)
    baseline_prompt = baseline_prompt_path.read_text(encoding="utf-8").strip()

    created_at = datetime.now(timezone.utc)
    timestamp = created_at.strftime("%Y%m%d-%H%M%S")
    baseline_id = f"{timestamp}-baseline"
    optimized_id = f"{timestamp}-bootstrap-fewshot"

    baseline_module = NextActionPlannerModule()
    baseline_eval = evaluate_module(baseline_module, devset)
    baseline_dir = output_root / "prompt_runs" / baseline_id
    save_prompt_run(
        run_dir=baseline_dir,
        prompt_text=baseline_prompt,
        metadata={
            "prompt_id": baseline_id,
            "created_at": created_at.isoformat(),
            "source": "baseline",
            "target_module": "NextActionPlanner",
            "dataset_split": "dev",
            "model": settings.model,
            "optimizer": None,
            "trainset_size": len(trainset),
            "devset_size": len(devset),
            "notes": "Step 6 で固定した baseline_system_prompt を使った初回評価。",
        },
        eval_result=baseline_eval,
    )

    optimizer = dspy.BootstrapFewShot(
        metric=next_action_metric,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
        max_rounds=1,
    )
    optimized_module = optimizer.compile(
        NextActionPlannerModule(),
        trainset=trainset,
    )
    optimized_eval = evaluate_module(optimized_module, devset)
    fewshot_examples = extract_labeled_demos(optimized_module)
    optimized_dir = output_root / "prompt_runs" / optimized_id
    optimized_prompt = "\n\n".join(
        [
            baseline_prompt,
            "## Few-shot examples selected by BootstrapFewShot",
            json.dumps(fewshot_examples, ensure_ascii=False, indent=2, sort_keys=True),
        ]
    )
    save_prompt_run(
        run_dir=optimized_dir,
        prompt_text=optimized_prompt,
        metadata={
            "prompt_id": optimized_id,
            "created_at": created_at.isoformat(),
            "source": "bootstrap_fewshot",
            "target_module": "NextActionPlanner",
            "parent_prompt_id": baseline_id,
            "dataset_split": "dev",
            "score": optimized_eval.score,
            "model": settings.model,
            "optimizer": "BootstrapFewShot",
            "optimizer_params": {
                "max_bootstrapped_demos": 4,
                "max_labeled_demos": 4,
                "max_rounds": 1,
            },
            "trainset_size": len(trainset),
            "devset_size": len(devset),
            "notes": "NextActionPlanner に限定した few-shot 最適化。",
        },
        eval_result=optimized_eval,
        fewshot_examples=fewshot_examples,
    )

    index = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "prompts": [
            {
                "prompt_id": baseline_id,
                "created_at": created_at.isoformat(),
                "source": "baseline",
                "target_module": "NextActionPlanner",
                "parent_prompt_id": None,
                "dataset_split": "dev",
                "score": baseline_eval.score,
                "notes": "Step 7 baseline evaluation.",
                "path": str(baseline_dir),
            },
            {
                "prompt_id": optimized_id,
                "created_at": created_at.isoformat(),
                "source": "bootstrap_fewshot",
                "target_module": "NextActionPlanner",
                "parent_prompt_id": baseline_id,
                "dataset_split": "dev",
                "score": optimized_eval.score,
                "notes": "Step 7 BootstrapFewShot run.",
                "path": str(optimized_dir),
            },
        ],
    }
    write_json(output_root / "prompt_index.json", index)

    current = index["prompts"][1] if optimized_eval.score >= baseline_eval.score else index["prompts"][0]
    write_json(output_root / "current.json", current)

    return {
        "baseline": {
            "prompt_id": baseline_id,
            "score": baseline_eval.score,
            "correct": baseline_eval.correct,
            "total": baseline_eval.total,
            "path": str(baseline_dir),
        },
        "optimized": {
            "prompt_id": optimized_id,
            "score": optimized_eval.score,
            "correct": optimized_eval.correct,
            "total": optimized_eval.total,
            "fewshot_count": len(fewshot_examples),
            "path": str(optimized_dir),
        },
        "current": current,
        "outputs": {
            "prompt_index": str(output_root / "prompt_index.json"),
            "current": str(output_root / "current.json"),
        },
    }
