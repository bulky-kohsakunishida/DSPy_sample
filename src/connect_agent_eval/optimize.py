from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

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

OptimizerName = Literal["bootstrap", "mipro", "gepa", "all"]

SOURCE_PRIORITY = {
    "gepa": 4,
    "mipro_v2": 3,
    "bootstrap_fewshot": 2,
    "baseline": 1,
}


@dataclass(frozen=True)
class EvaluationResult:
    total: int
    correct: int
    score: float
    cases: list[dict[str, Any]]


@dataclass(frozen=True)
class OptimizerRunConfig:
    optimizer: OptimizerName = "bootstrap"
    train_path: Path = Path("data/scenarios/train_billing_support.jsonl")
    dev_path: Path = Path("data/scenarios/dev_billing_support.jsonl")
    baseline_prompt_path: Path = Path("data/prompts/baseline_system_prompt.md")
    output_root: Path = Path("outputs/prompts")
    settings: LMSettings = LMSettings(
        model="ollama_chat/gemma4:12b",
        api_base="http://localhost:11434",
        max_tokens=64,
    )
    reflection_settings: LMSettings = LMSettings(
        model="ollama_chat/gemma4:31b",
        api_base="http://localhost:11434",
        temperature=1.0,
        max_tokens=2048,
    )


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
            account_suffix = previous_text.split("ACC-", 1)[1].split()[0].strip("。、")
            slots["account_id"] = f"ACC-{account_suffix}"
            slots["identity_verification"] = "verified_by_account_id"
        if "今月" in previous_text:
            slots["issue_month"] = "今月"
        elif "先月" in previous_text:
            slots["issue_month"] = "先月"

    return {
        "intent": expected_intent if turn_index > 0 else "unknown",
        "slots": slots,
        "last_agent_action": None
        if turn_index == 0
        else scenario["turns"][turn_index - 1]["expected_next_action"],
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


def next_action_metric(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace=None,
) -> bool:
    expected = normalize_action(example.next_action)
    actual = normalize_action(getattr(prediction, "next_action", ""))
    return actual == expected


def next_action_feedback_metric(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace=None,
    pred_name=None,
    pred_trace=None,
) -> dspy.Prediction:
    expected = normalize_action(example.next_action)
    actual = normalize_action(getattr(prediction, "next_action", ""))

    if actual == expected:
        return dspy.Prediction(
            score=1.0,
            feedback="正解です。期待された next_action と一致しています。",
        )

    feedback = build_feedback_for_action_mismatch(
        expected=expected,
        actual=actual,
        conversation_state=getattr(example, "conversation_state", ""),
        customer_utterance=getattr(example, "customer_utterance", ""),
    )
    return dspy.Prediction(score=0.0, feedback=feedback)


def build_feedback_for_action_mismatch(
    *,
    expected: str,
    actual: str,
    conversation_state: str,
    customer_utterance: str,
) -> str:
    base = (
        f"期待アクションは `{expected}` ですが、予測は `{actual}` でした。"
        f" 顧客発話は「{customer_utterance}」です。"
        " `conversation_state` の slots、last_agent_action、must_not と、"
        " `business_rules` の本人確認条件、ツール呼び出し条件、有人引き継ぎ条件を優先してください。"
    )
    if expected == "ask_identity_verification" and actual == "clarify_intent":
        return (
            base
            + " 請求金額や請求確認の意図が十分に読める場合は、曖昧化せず本人確認へ進めてください。"
        )
    if expected == "call_get_billing_summary" and actual == "ask_identity_verification":
        return (
            base
            + " account_id が提示され、本人確認済み状態なら、本人確認を繰り返さず請求サマリー取得へ進めてください。"
        )
    if expected == "handoff_to_human":
        return (
            base
            + " 顧客が担当者への交代を希望している場合は、追加質問より有人引き継ぎを優先してください。"
        )
    if conversation_state:
        return base + f" 会話状態は {conversation_state} です。"
    return base


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


def extract_predictor_artifacts(module: dspy.Module) -> list[dict[str, Any]]:
    artifacts = []
    for index, predictor in enumerate(module.predictors()):
        signature = getattr(predictor, "signature", None)
        artifacts.append(
            {
                "predictor_index": index,
                "predictor_type": type(predictor).__name__,
                "instruction": getattr(signature, "instructions", None),
                "signature": str(signature) if signature is not None else None,
                "demo_count": len(getattr(predictor, "demos", []) or []),
            }
        )
    return artifacts


def build_prompt_text(
    *,
    baseline_prompt: str,
    optimizer_name: str,
    module: dspy.Module | None = None,
    fewshot_examples: list[dict[str, Any]] | None = None,
) -> str:
    sections = [baseline_prompt]
    if optimizer_name != "baseline":
        sections.append(f"## Optimizer\n\n{optimizer_name}")
    if module is not None:
        sections.append(
            "## Predictor artifacts\n\n"
            + json.dumps(
                extract_predictor_artifacts(module),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    if fewshot_examples:
        sections.append(
            "## Few-shot examples\n\n"
            + json.dumps(
                fewshot_examples,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return "\n\n".join(sections)


def save_prompt_run(
    *,
    run_dir: Path,
    prompt_text: str,
    metadata: dict[str, Any],
    eval_result: EvaluationResult,
    fewshot_examples: list[dict[str, Any]] | None = None,
    optimizer_artifacts: dict[str, Any] | None = None,
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
    if optimizer_artifacts is not None:
        write_json(run_dir / "optimizer_artifacts.json", optimizer_artifacts)


def make_index_record(
    *,
    prompt_id: str,
    created_at: datetime,
    source: str,
    parent_prompt_id: str | None,
    eval_result: EvaluationResult,
    notes: str,
    run_dir: Path,
    optimizer: str | None,
) -> dict[str, Any]:
    return {
        "prompt_id": prompt_id,
        "created_at": created_at.isoformat(),
        "source": source,
        "target_module": "NextActionPlanner",
        "parent_prompt_id": parent_prompt_id,
        "dataset_split": "dev",
        "score": eval_result.score,
        "optimizer": optimizer,
        "notes": notes,
        "path": str(run_dir),
    }


def load_prompt_index(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {"updated_at": None, "prompts": []}


def update_prompt_index(output_root: Path, new_records: list[dict[str, Any]]) -> dict[str, Any]:
    index_path = output_root / "prompt_index.json"
    index = load_prompt_index(index_path)
    records_by_id = {record["prompt_id"]: record for record in index.get("prompts", [])}
    for record in new_records:
        records_by_id[record["prompt_id"]] = record

    records = sorted(
        records_by_id.values(),
        key=lambda record: (record.get("created_at", ""), record.get("prompt_id", "")),
    )
    index = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "prompts": records,
    }
    write_json(index_path, index)
    current = select_current_prompt(records)
    write_json(output_root / "current.json", current)
    return index


def select_current_prompt(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        records,
        key=lambda record: (
            record.get("score", 0.0),
            SOURCE_PRIORITY.get(record.get("source", ""), 0),
            record.get("created_at", ""),
        ),
    )


def run_baseline_evaluation(
    *,
    devset: list[dspy.Example],
    baseline_prompt: str,
    output_root: Path,
    created_at: datetime,
    timestamp: str,
    settings: LMSettings,
    trainset_size: int,
) -> tuple[str, dict[str, Any], EvaluationResult]:
    prompt_id = f"{timestamp}-baseline"
    run_dir = output_root / "prompt_runs" / prompt_id
    eval_result = evaluate_module(NextActionPlannerModule(), devset)
    metadata = {
        "prompt_id": prompt_id,
        "created_at": created_at.isoformat(),
        "source": "baseline",
        "target_module": "NextActionPlanner",
        "dataset_split": "dev",
        "model": settings.model,
        "optimizer": None,
        "trainset_size": trainset_size,
        "devset_size": len(devset),
        "notes": "Step 6 で固定した baseline_system_prompt を使った初回評価。",
    }
    save_prompt_run(
        run_dir=run_dir,
        prompt_text=baseline_prompt,
        metadata=metadata,
        eval_result=eval_result,
    )
    return prompt_id, make_index_record(
        prompt_id=prompt_id,
        created_at=created_at,
        source="baseline",
        parent_prompt_id=None,
        eval_result=eval_result,
        notes="Step 7 baseline evaluation.",
        run_dir=run_dir,
        optimizer=None,
    ), eval_result


def run_bootstrap_fewshot_optimization(
    *,
    trainset: list[dspy.Example],
    devset: list[dspy.Example],
    baseline_prompt: str,
    output_root: Path,
    created_at: datetime,
    timestamp: str,
    parent_prompt_id: str,
    settings: LMSettings,
) -> tuple[dict[str, Any], EvaluationResult]:
    prompt_id = f"{timestamp}-bootstrap-fewshot"
    run_dir = output_root / "prompt_runs" / prompt_id
    start = time.monotonic()
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
    elapsed_seconds = time.monotonic() - start
    eval_result = evaluate_module(optimized_module, devset)
    fewshot_examples = extract_labeled_demos(optimized_module)
    prompt_text = build_prompt_text(
        baseline_prompt=baseline_prompt,
        optimizer_name="BootstrapFewShot",
        module=optimized_module,
        fewshot_examples=fewshot_examples,
    )
    metadata = {
        "prompt_id": prompt_id,
        "created_at": created_at.isoformat(),
        "source": "bootstrap_fewshot",
        "target_module": "NextActionPlanner",
        "parent_prompt_id": parent_prompt_id,
        "dataset_split": "dev",
        "score": eval_result.score,
        "model": settings.model,
        "optimizer": "BootstrapFewShot",
        "optimizer_params": {
            "max_bootstrapped_demos": 4,
            "max_labeled_demos": 4,
            "max_rounds": 1,
        },
        "trainset_size": len(trainset),
        "devset_size": len(devset),
        "elapsed_seconds": elapsed_seconds,
        "notes": "NextActionPlanner に限定した few-shot 最適化。",
    }
    save_prompt_run(
        run_dir=run_dir,
        prompt_text=prompt_text,
        metadata=metadata,
        eval_result=eval_result,
        fewshot_examples=fewshot_examples,
        optimizer_artifacts={
            "predictors": extract_predictor_artifacts(optimized_module),
            "elapsed_seconds": elapsed_seconds,
        },
    )
    return make_index_record(
        prompt_id=prompt_id,
        created_at=created_at,
        source="bootstrap_fewshot",
        parent_prompt_id=parent_prompt_id,
        eval_result=eval_result,
        notes="Step 7 BootstrapFewShot run.",
        run_dir=run_dir,
        optimizer="BootstrapFewShot",
    ), eval_result


def run_mipro_v2_optimization(
    *,
    trainset: list[dspy.Example],
    devset: list[dspy.Example],
    baseline_prompt: str,
    output_root: Path,
    created_at: datetime,
    timestamp: str,
    parent_prompt_id: str,
    settings: LMSettings,
) -> tuple[dict[str, Any], EvaluationResult]:
    prompt_id = f"{timestamp}-mipro-v2"
    run_dir = output_root / "prompt_runs" / prompt_id
    log_dir = output_root / "optimizer_logs" / prompt_id
    prompt_lm = dspy.LM(
        settings.model,
        api_base=settings.api_base,
        api_key=settings.api_key,
        temperature=1.0,
        max_tokens=1024,
        cache=False,
        think=False,
    )
    start = time.monotonic()
    optimizer = dspy.MIPROv2(
        metric=next_action_metric,
        prompt_model=prompt_lm,
        auto="light",
        num_threads=1,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
        log_dir=str(log_dir),
    )
    optimized_module = optimizer.compile(
        NextActionPlannerModule(),
        trainset=trainset,
        valset=devset,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
        minibatch_size=max(1, min(4, len(devset))),
    )
    elapsed_seconds = time.monotonic() - start
    eval_result = evaluate_module(optimized_module, devset)
    fewshot_examples = extract_labeled_demos(optimized_module)
    prompt_text = build_prompt_text(
        baseline_prompt=baseline_prompt,
        optimizer_name="MIPROv2",
        module=optimized_module,
        fewshot_examples=fewshot_examples,
    )
    metadata = {
        "prompt_id": prompt_id,
        "created_at": created_at.isoformat(),
        "source": "mipro_v2",
        "target_module": "NextActionPlanner",
        "parent_prompt_id": parent_prompt_id,
        "dataset_split": "dev",
        "score": eval_result.score,
        "model": settings.model,
        "optimizer": "MIPROv2",
        "optimizer_params": {
            "auto": "light",
            "num_threads": 1,
            "max_bootstrapped_demos": 4,
            "max_labeled_demos": 4,
            "minibatch_size": max(1, min(4, len(devset))),
            "prompt_model": settings.model,
            "prompt_model_temperature": 1.0,
            "prompt_model_max_tokens": 1024,
            "log_dir": str(log_dir),
        },
        "trainset_size": len(trainset),
        "devset_size": len(devset),
        "elapsed_seconds": elapsed_seconds,
        "notes": "MIPROv2 auto=light による instruction と few-shot の最適化。",
    }
    save_prompt_run(
        run_dir=run_dir,
        prompt_text=prompt_text,
        metadata=metadata,
        eval_result=eval_result,
        fewshot_examples=fewshot_examples,
        optimizer_artifacts={
            "predictors": extract_predictor_artifacts(optimized_module),
            "elapsed_seconds": elapsed_seconds,
            "log_dir": str(log_dir),
        },
    )
    return make_index_record(
        prompt_id=prompt_id,
        created_at=created_at,
        source="mipro_v2",
        parent_prompt_id=parent_prompt_id,
        eval_result=eval_result,
        notes="Step 7 MIPROv2 run.",
        run_dir=run_dir,
        optimizer="MIPROv2",
    ), eval_result


def run_gepa_optimization(
    *,
    trainset: list[dspy.Example],
    devset: list[dspy.Example],
    baseline_prompt: str,
    output_root: Path,
    created_at: datetime,
    timestamp: str,
    parent_prompt_id: str,
    settings: LMSettings,
    reflection_settings: LMSettings,
) -> tuple[dict[str, Any], EvaluationResult]:
    prompt_id = f"{timestamp}-gepa"
    run_dir = output_root / "prompt_runs" / prompt_id
    log_dir = output_root / "optimizer_logs" / prompt_id
    reflection_lm = dspy.LM(
        reflection_settings.model,
        api_base=reflection_settings.api_base,
        api_key=reflection_settings.api_key,
        temperature=reflection_settings.temperature,
        max_tokens=reflection_settings.max_tokens,
        cache=False,
        think=False,
    )
    start = time.monotonic()
    optimizer = dspy.GEPA(
        metric=next_action_feedback_metric,
        auto=None,
        max_metric_calls=36,
        num_threads=1,
        reflection_minibatch_size=3,
        reflection_lm=reflection_lm,
        track_stats=True,
        log_dir=str(log_dir),
    )
    optimized_module = optimizer.compile(
        NextActionPlannerModule(),
        trainset=trainset,
        valset=devset,
    )
    elapsed_seconds = time.monotonic() - start
    eval_result = evaluate_module(optimized_module, devset)
    prompt_text = build_prompt_text(
        baseline_prompt=baseline_prompt,
        optimizer_name="GEPA",
        module=optimized_module,
        fewshot_examples=extract_labeled_demos(optimized_module),
    )
    metadata = {
        "prompt_id": prompt_id,
        "created_at": created_at.isoformat(),
        "source": "gepa",
        "target_module": "NextActionPlanner",
        "parent_prompt_id": parent_prompt_id,
        "dataset_split": "dev",
        "score": eval_result.score,
        "model": settings.model,
        "reflection_model": reflection_settings.model,
        "optimizer": "GEPA",
        "optimizer_params": {
            "auto": None,
            "max_metric_calls": 36,
            "num_threads": 1,
            "reflection_minibatch_size": 3,
            "reflection_model": reflection_settings.model,
            "reflection_temperature": reflection_settings.temperature,
            "reflection_max_tokens": reflection_settings.max_tokens,
            "track_stats": True,
            "log_dir": str(log_dir),
        },
        "trainset_size": len(trainset),
        "devset_size": len(devset),
        "elapsed_seconds": elapsed_seconds,
        "notes": "GEPA max_metric_calls=36 と gemma4:31b reflection_lm による instruction 最適化。",
    }
    save_prompt_run(
        run_dir=run_dir,
        prompt_text=prompt_text,
        metadata=metadata,
        eval_result=eval_result,
        optimizer_artifacts={
            "predictors": extract_predictor_artifacts(optimized_module),
            "elapsed_seconds": elapsed_seconds,
            "log_dir": str(log_dir),
            "reflection_model": reflection_settings.model,
        },
    )
    return make_index_record(
        prompt_id=prompt_id,
        created_at=created_at,
        source="gepa",
        parent_prompt_id=parent_prompt_id,
        eval_result=eval_result,
        notes="Step 7 GEPA run.",
        run_dir=run_dir,
        optimizer="GEPA",
    ), eval_result


def run_step7_prompt_optimization(
    *,
    optimizer: OptimizerName = "bootstrap",
    train_path: Path = Path("data/scenarios/train_billing_support.jsonl"),
    dev_path: Path = Path("data/scenarios/dev_billing_support.jsonl"),
    baseline_prompt_path: Path = Path("data/prompts/baseline_system_prompt.md"),
    output_root: Path = Path("outputs/prompts"),
    settings: LMSettings = LMSettings(
        model="ollama_chat/gemma4:12b",
        api_base="http://localhost:11434",
        max_tokens=64,
    ),
    reflection_settings: LMSettings = LMSettings(
        model="ollama_chat/gemma4:31b",
        api_base="http://localhost:11434",
        temperature=1.0,
        max_tokens=2048,
    ),
) -> dict[str, Any]:
    config = OptimizerRunConfig(
        optimizer=optimizer,
        train_path=train_path,
        dev_path=dev_path,
        baseline_prompt_path=baseline_prompt_path,
        output_root=output_root,
        settings=settings,
        reflection_settings=reflection_settings,
    )
    return run_prompt_optimization(config)


def run_prompt_optimization(config: OptimizerRunConfig) -> dict[str, Any]:
    if config.optimizer not in {"bootstrap", "mipro", "gepa", "all"}:
        raise ValueError(f"Unknown optimizer: {config.optimizer}")

    configure_lm(config.settings)

    trainset = build_examples(config.train_path)
    devset = build_examples(config.dev_path)
    baseline_prompt = config.baseline_prompt_path.read_text(encoding="utf-8").strip()

    created_at = datetime.now(timezone.utc)
    timestamp = created_at.strftime("%Y%m%d-%H%M%S")

    baseline_id, baseline_record, baseline_eval = run_baseline_evaluation(
        devset=devset,
        baseline_prompt=baseline_prompt,
        output_root=config.output_root,
        created_at=created_at,
        timestamp=timestamp,
        settings=config.settings,
        trainset_size=len(trainset),
    )

    records = [baseline_record]
    results: dict[str, Any] = {
        "baseline": summarize_result(baseline_record, baseline_eval),
    }

    selected = (
        ["bootstrap", "mipro", "gepa"]
        if config.optimizer == "all"
        else [config.optimizer]
    )
    for optimizer_name in selected:
        if optimizer_name == "bootstrap":
            record, eval_result = run_bootstrap_fewshot_optimization(
                trainset=trainset,
                devset=devset,
                baseline_prompt=baseline_prompt,
                output_root=config.output_root,
                created_at=created_at,
                timestamp=timestamp,
                parent_prompt_id=baseline_id,
                settings=config.settings,
            )
            results["bootstrap"] = summarize_result(record, eval_result)
        elif optimizer_name == "mipro":
            record, eval_result = run_mipro_v2_optimization(
                trainset=trainset,
                devset=devset,
                baseline_prompt=baseline_prompt,
                output_root=config.output_root,
                created_at=created_at,
                timestamp=timestamp,
                parent_prompt_id=baseline_id,
                settings=config.settings,
            )
            results["mipro"] = summarize_result(record, eval_result)
        elif optimizer_name == "gepa":
            record, eval_result = run_gepa_optimization(
                trainset=trainset,
                devset=devset,
                baseline_prompt=baseline_prompt,
                output_root=config.output_root,
                created_at=created_at,
                timestamp=timestamp,
                parent_prompt_id=baseline_id,
                settings=config.settings,
                reflection_settings=config.reflection_settings,
            )
            results["gepa"] = summarize_result(record, eval_result)
        else:
            raise ValueError(f"Unknown optimizer: {optimizer_name}")
        records.append(record)

    index = update_prompt_index(config.output_root, records)
    current = select_current_prompt(index["prompts"])
    results["current"] = current
    results["outputs"] = {
        "prompt_index": str(config.output_root / "prompt_index.json"),
        "current": str(config.output_root / "current.json"),
    }
    return results


def summarize_result(record: dict[str, Any], eval_result: EvaluationResult) -> dict[str, Any]:
    return {
        "prompt_id": record["prompt_id"],
        "score": eval_result.score,
        "correct": eval_result.correct,
        "total": eval_result.total,
        "path": record["path"],
    }
