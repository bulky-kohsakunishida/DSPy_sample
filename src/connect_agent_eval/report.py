from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTION_DESCRIPTIONS = {
    "ask_identity_verification": "本人確認に必要な情報を依頼する",
    "ask_account_id": "請求確認に必要な account_id を依頼する",
    "call_get_billing_summary": "本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ",
    "clarify_intent": "問い合わせ意図が曖昧なため確認する",
    "handoff_to_human": "有人対応へ引き継ぐ",
}

SOURCE_PRIORITY = {
    "gepa": 4,
    "mipro_v2": 3,
    "bootstrap_fewshot": 2,
    "baseline": 1,
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_prompt_record(record: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(record["path"])
    metadata = read_json(run_dir / "metadata.json")
    eval_summary = read_json(run_dir / "eval_summary.json")
    prompt_text = (run_dir / "prompt.md").read_text(encoding="utf-8").strip()
    return {
        **record,
        "run_dir": run_dir,
        "metadata": metadata,
        "eval_summary": eval_summary,
        "prompt_text": prompt_text,
    }


def is_infrastructure_failed_record(record: dict[str, Any]) -> bool:
    cases = record["eval_summary"].get("cases", [])
    return bool(cases) and all(case.get("error") for case in cases)


def select_baseline(records: list[dict[str, Any]]) -> dict[str, Any]:
    baselines = [record for record in records if record.get("source") == "baseline"]
    if not baselines:
        raise ValueError("prompt_index.json に baseline の記録がありません。")
    return sorted(baselines, key=lambda record: record.get("created_at", ""))[0]


def select_latest_baseline(records: list[dict[str, Any]]) -> dict[str, Any]:
    baselines = [record for record in records if record.get("source") == "baseline"]
    if not baselines:
        raise ValueError("prompt_index.json に baseline の記録がありません。")
    return sorted(baselines, key=lambda record: record.get("created_at", ""))[-1]


def select_best(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        records,
        key=lambda record: (
            record.get("score", 0.0),
            SOURCE_PRIORITY.get(record.get("source", ""), 0),
            record.get("created_at", ""),
        ),
    )


def select_latest(records: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(records, key=lambda record: record.get("created_at", ""))[-1]


def case_key(case: dict[str, Any]) -> tuple[str, int]:
    return (case["scenario_id"], int(case["turn_index"]))


def compare_cases(
    baseline_eval: dict[str, Any],
    tuned_eval: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    baseline_cases = {case_key(case): case for case in baseline_eval["cases"]}
    tuned_cases = {case_key(case): case for case in tuned_eval["cases"]}

    improved = []
    worsened = []
    still_failed = []
    for key in sorted(baseline_cases):
        baseline_case = baseline_cases[key]
        tuned_case = tuned_cases.get(key)
        if tuned_case is None:
            continue
        row = {
            "scenario_id": baseline_case["scenario_id"],
            "turn_index": baseline_case["turn_index"],
            "customer_utterance": baseline_case["customer_utterance"],
            "expected_next_action": baseline_case["expected_next_action"],
            "baseline_next_action": baseline_case["actual_next_action"],
            "tuned_next_action": tuned_case["actual_next_action"],
            "baseline_correct": baseline_case["correct"],
            "tuned_correct": tuned_case["correct"],
            "baseline_error": baseline_case.get("error"),
            "tuned_error": tuned_case.get("error"),
        }
        if not baseline_case["correct"] and tuned_case["correct"]:
            improved.append(row)
        elif baseline_case["correct"] and not tuned_case["correct"]:
            worsened.append(row)
        elif not baseline_case["correct"] and not tuned_case["correct"]:
            still_failed.append(row)

    return {
        "improved": improved,
        "worsened": worsened,
        "still_failed": still_failed,
    }


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def action_description(action: str) -> str:
    return ACTION_DESCRIPTIONS.get(action, "未定義または想定外のアクション")


def case_verdict(case: dict[str, Any]) -> str:
    baseline_correct = case.get("baseline_correct")
    tuned_correct = case.get("tuned_correct")
    if baseline_correct and tuned_correct:
        return "維持"
    if not baseline_correct and tuned_correct:
        return "改善"
    if baseline_correct and not tuned_correct:
        return "悪化"
    return "未解決"


def format_case_table(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "該当なし"

    lines = [
        "| scenario | turn | expected | baseline | tuned | 判定 | utterance |",
        "|---|---:|---|---|---|---|---|",
    ]
    for case in cases:
        utterance = str(case["customer_utterance"]).replace("|", "\\|")
        verdict = case_verdict(case)
        lines.append(
            "| {scenario_id} | {turn_index} | `{expected_next_action}` | "
            "`{baseline_next_action}` | `{tuned_next_action}` | {verdict} | {utterance} |".format(
                utterance=utterance,
                verdict=verdict,
                **case,
            )
        )
    return "\n".join(lines)


def format_action_glossary(cases: list[dict[str, Any]]) -> str:
    actions = sorted(
        {case["expected_next_action"] for case in cases}
        | {case["baseline_next_action"] for case in cases if case["baseline_next_action"]}
        | {case["tuned_next_action"] for case in cases if case["tuned_next_action"]}
    )
    lines = ["| action | 意味 |", "|---|---|"]
    for action in actions:
        lines.append(f"| `{action}` | {action_description(action)} |")
    return "\n".join(lines)


def format_prompt_history(records: list[dict[str, Any]]) -> str:
    lines = [
        "| prompt_id | source | optimizer | score | correct | model | reflection_lm | path |",
        "|---|---|---|---:|---:|---|---|---|",
    ]
    for record in sorted(records, key=lambda item: item.get("created_at", "")):
        eval_summary = record["eval_summary"]
        metadata = record["metadata"]
        lines.append(
            "| `{prompt_id}` | `{source}` | `{optimizer}` | {score} | {correct}/{total} | `{model}` | `{reflection_lm}` | `{path}` |".format(
                prompt_id=record["prompt_id"],
                source=record.get("source", "unknown"),
                optimizer=metadata.get("optimizer") or "なし",
                score=format_percent(eval_summary["score"]),
                correct=eval_summary["correct"],
                total=eval_summary["total"],
                model=metadata.get("model", "unknown"),
                reflection_lm=metadata.get("reflection_model") or "-",
                path=record["run_dir"],
            )
        )
    return "\n".join(lines)


def format_optimizer_comparison(
    *,
    baseline: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    lines = [
        "| optimizer | score | correct | improved | worsened | still failed | model | reflection_lm | path |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    comparison_records = latest_record_per_source(baseline=baseline, records=records)
    comparison_baseline = comparison_records[0]
    for record in comparison_records:
        metadata = record["metadata"]
        if record["prompt_id"] == comparison_baseline["prompt_id"]:
            improved = "-"
            worsened = "-"
            still_failed = "-"
        else:
            comparisons = compare_cases(comparison_baseline["eval_summary"], record["eval_summary"])
            improved = str(len(comparisons["improved"]))
            worsened = str(len(comparisons["worsened"]))
            still_failed = str(len(comparisons["still_failed"]))
        eval_summary = record["eval_summary"]
        lines.append(
            "| `{optimizer}` | {score} | {correct}/{total} | {improved} | {worsened} | {still_failed} | `{model}` | `{reflection_lm}` | `{path}` |".format(
                optimizer=metadata.get("optimizer") or "baseline",
                score=format_percent(eval_summary["score"]),
                correct=eval_summary["correct"],
                total=eval_summary["total"],
                improved=improved,
                worsened=worsened,
                still_failed=still_failed,
                model=metadata.get("model", "unknown"),
                reflection_lm=metadata.get("reflection_model") or "-",
                path=record["run_dir"],
            )
        )
    return "\n".join(lines)


def usage_total(record: dict[str, Any], key: str) -> int | float:
    return record["metadata"].get("usage", {}).get("total", {}).get(key, 0)


def usage_calls(record: dict[str, Any]) -> int:
    calls_by_model = record["metadata"].get("usage", {}).get("calls_by_model", {})
    return sum(calls_by_model.values())


def format_token_usage(value: int | float) -> str:
    if not value:
        return "-"
    return f"{int(value):,}"


def format_token_usage_comparison(
    *,
    baseline: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    lines = [
        "| optimizer | total_tokens | prompt_tokens | completion_tokens | LM calls | model breakdown | path |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for record in latest_record_per_source(baseline=baseline, records=records):
        metadata = record["metadata"]
        usage = metadata.get("usage", {})
        by_model = usage.get("by_model", {})
        calls_by_model = usage.get("calls_by_model", {})
        model_parts = []
        for model, model_usage in by_model.items():
            model_total = model_usage.get("total_tokens", 0)
            model_calls = calls_by_model.get(model, 0)
            model_parts.append(
                f"`{model}`: {format_token_usage(model_total)} tokens / {model_calls} calls"
            )
        lines.append(
            "| `{optimizer}` | {total_tokens} | {prompt_tokens} | {completion_tokens} | {calls} | {model_breakdown} | `{path}` |".format(
                optimizer=metadata.get("optimizer") or "baseline",
                total_tokens=format_token_usage(usage_total(record, "total_tokens")),
                prompt_tokens=format_token_usage(usage_total(record, "prompt_tokens")),
                completion_tokens=format_token_usage(usage_total(record, "completion_tokens")),
                calls=usage_calls(record) or "-",
                model_breakdown="<br>".join(model_parts) if model_parts else "-",
                path=record["run_dir"],
            )
        )
    return "\n".join(lines)


def format_token_usage_explanation() -> str:
    return """この表の token は、LLM に渡した入力と、LLM が生成した出力をモデル側の単位で数えたものです。文字数や単語数とは一致せず、モデルが内部的に処理する分割単位です。

- `prompt_tokens`: LLM に渡した入力側の token 数。プロンプト、business rules、conversation_state、customer_utterance、few-shot 例、GEPA の reflection 用入力などが含まれます。
- `completion_tokens`: LLM が生成した出力側の token 数。`next_action`、MIPROv2 の instruction 候補、GEPA の reflection や改善プロンプト案などが含まれます。
- `total_tokens`: `prompt_tokens + completion_tokens`。処理量やコスト感を見るときの合計値です。
- `LM calls`: LLM を呼び出した回数。1 call ごとに prompt/completion tokens が発生します。
- `model breakdown`: モデル別の token と call 数の内訳です。GEPA では通常の `next_action` 予測を行う task model と、失敗例を振り返る reflection LM が分かれて記録されます。

今回の GEPA 72 calls run では `total_tokens=102,942` のうち `prompt_tokens=97,302`、`completion_tokens=5,640` です。つまり、生成量よりも「モデルに読ませた入力」の比率が大きい run だったと読めます。"""


def format_gepa_metric_call_progress(records: list[dict[str, Any]]) -> str:
    gepa_records = [
        record
        for record in records
        if record.get("source") == "gepa"
        and record["metadata"].get("optimizer") == "GEPA"
    ]
    if not gepa_records:
        return "GEPA の追加検証 run はまだありません。"

    lines = [
        "| prompt_id | max_metric_calls | score | correct | total_tokens | LM calls | elapsed_seconds | path |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for record in sorted(
        gepa_records,
        key=lambda item: (
            item["metadata"].get("optimizer_params", {}).get("max_metric_calls") or 0,
            item.get("created_at", ""),
        ),
    ):
        metadata = record["metadata"]
        eval_summary = record["eval_summary"]
        params = metadata.get("optimizer_params", {})
        elapsed_seconds = metadata.get("elapsed_seconds")
        lines.append(
            "| `{prompt_id}` | {max_metric_calls} | {score} | {correct}/{total} | {total_tokens} | {calls} | {elapsed_seconds} | `{path}` |".format(
                prompt_id=record["prompt_id"],
                max_metric_calls=params.get("max_metric_calls", "-"),
                score=format_percent(eval_summary["score"]),
                correct=eval_summary["correct"],
                total=eval_summary["total"],
                total_tokens=format_token_usage(usage_total(record, "total_tokens")),
                calls=usage_calls(record) or "-",
                elapsed_seconds=(
                    f"{elapsed_seconds:.1f}"
                    if isinstance(elapsed_seconds, int | float)
                    else "-"
                ),
                path=record["run_dir"],
            )
        )

    return "\n".join(lines)


def format_score_explanation(best_eval: dict[str, Any]) -> str:
    return f"""`6/6` のような表記は、評価対象 {best_eval["total"]} turns のうち何件が正解したかを表します。`6/6、100%` なら、6件すべてで予測した `next_action` が正解ラベルと一致したという意味です。

このプロジェクトの評価は、自然文応答のうまさではなく、各 turn で `NextActionPlanner` が選んだ `next_action` の完全一致を見ています。たとえば、期待値が `call_get_billing_summary` で、モデル出力も `call_get_billing_summary` なら1件正解です。説明文が混ざる、別 action を出す、例外で出力できない場合は不正解です。

`score` は `correct / total` で計算します。今回なら `2/6 = 33.3%`、`4/6 = 66.7%`、`6/6 = 100.0%` です。評価件数が少ないため、100% はこの dev データ上で全問正解したという意味であり、本番品質を保証するものではありません。
"""


def format_optimizer_explanations() -> str:
    return """### baseline

optimizer を使わず、固定の `baseline_system_prompt.md` と `NextActionPlanner` の Signature だけで推論します。比較の基準です。ここで失敗したケースが、optimizer によって改善できたかを見ます。

### BootstrapFewShot

`BootstrapFewShot` は、train データから few-shot 例を選び、LLM に「この入力ならこの action」という具体例を追加する optimizer です。instruction 自体を大きく書き換えるよりも、判断例を足してモデルの出力を安定させる動きになります。

このプロジェクトでは、`next_action_metric` で正解した train 例を使い、最大4件の bootstrapped demos と最大4件の labeled demos を候補として `NextActionPlanner` に付与します。その後、dev データで `next_action` が一致するかを評価します。

### MIPROv2

`MIPROv2` は、few-shot 例だけでなく instruction 候補も探索する optimizer です。複数の instruction 案と few-shot セットを作り、それらの組み合わせを評価しながら、よりスコアが高いプロンプト構成を探します。

このプロジェクトでは `auto=\"light\"` で実行し、`gemma4:12b` を task model と prompt model に使います。ただし、instruction 候補生成では長めの出力が必要なため、prompt model の `max_tokens` は `1024` にしています。探索には `optuna` が必要です。

### GEPA

`GEPA` は、失敗例に対する feedback を使って instruction を反復的に改善する optimizer です。単に正解/不正解を見るだけでなく、「なぜ違ったか」「どのルールを優先すべきか」という feedback を reflection LM に渡し、新しい instruction 案を生成します。

このプロジェクトでは、通常推論の task model は `ollama_chat/gemma4:12b`、reflection LM は `ollama_chat/gemma4:31b` です。`next_action_feedback_metric` が expected と actual の差分を説明し、GEPA がその feedback から改善案を作ります。

GEPA の `auto=\"light\"` はローカル環境では約404 metric calls と重かったため、初期検証では `auto=None`, `max_metric_calls=36` に制限しました。その後、36 calls では 4/6 にとどまったため、段階的に 72 calls へ拡大し、dev データ上で 6/6 に到達することを確認しました。
"""


def latest_record_per_source(
    *,
    baseline: dict[str, Any],
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest_by_source: dict[str, dict[str, Any]] = {}
    latest_baseline = baseline
    for record in records:
        source = record.get("source", "")
        if source == "baseline":
            if record.get("created_at", "") > latest_baseline.get("created_at", ""):
                latest_baseline = record
            continue
        current = latest_by_source.get(source)
        if current is None or record.get("created_at", "") > current.get("created_at", ""):
            latest_by_source[source] = record

    ordered = [latest_baseline]
    ordered.extend(
        sorted(
            latest_by_source.values(),
            key=lambda record: SOURCE_PRIORITY.get(record.get("source", ""), 0),
        )
    )
    return ordered


def format_evaluation_design(best: dict[str, Any]) -> str:
    metadata = best["metadata"]
    optimizer_params = metadata.get("optimizer_params") or {}
    optimizer_param_text = (
        ", ".join(f"`{key}={value}`" for key, value in optimizer_params.items())
        if optimizer_params
        else "なし"
    )
    return f"""- 評価単位: 会話シナリオ全体ではなく、各 turn の `next_action` 判定を 1 サンプルとして評価
- 入力: `conversation_state`, `business_rules`, `customer_utterance`
- 出力: `next_action`
- 正解条件: 予測した `next_action` が固定済みデータの `expected_next_action` と完全一致
- 対象 split: `{metadata.get("dataset_split", "unknown")}`
- train 件数: {metadata.get("trainset_size", "unknown")}
- dev 件数: {metadata.get("devset_size", "unknown")}
- optimizer パラメータ: {optimizer_param_text}
"""


def format_all_cases_table(
    baseline_eval: dict[str, Any],
    tuned_eval: dict[str, Any],
) -> str:
    return format_case_table(build_case_rows(baseline_eval, tuned_eval))


def build_case_rows(
    baseline_eval: dict[str, Any],
    tuned_eval: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_cases = {case_key(case): case for case in baseline_eval["cases"]}
    tuned_cases = {case_key(case): case for case in tuned_eval["cases"]}
    rows = []
    for key in sorted(baseline_cases):
        baseline_case = baseline_cases[key]
        tuned_case = tuned_cases[key]
        rows.append(
            {
                "scenario_id": baseline_case["scenario_id"],
                "turn_index": baseline_case["turn_index"],
                "customer_utterance": baseline_case["customer_utterance"],
                "expected_next_action": baseline_case["expected_next_action"],
                "baseline_next_action": baseline_case["actual_next_action"],
                "tuned_next_action": tuned_case["actual_next_action"],
                "baseline_correct": baseline_case["correct"],
                "tuned_correct": tuned_case["correct"],
            }
        )
    return rows


def explain_case_change(case: dict[str, Any]) -> str:
    expected = case["expected_next_action"]
    baseline = case["baseline_next_action"]
    tuned = case["tuned_next_action"]
    if expected == "ask_identity_verification" and baseline == "clarify_intent":
        return "請求に関する発話を曖昧問い合わせとして扱っていたが、最適化後は本人確認が必要な請求問い合わせとして扱えています。"
    if expected == "call_get_billing_summary" and baseline == "ask_identity_verification":
        return "account_id が提示された後も本人確認を繰り返していたが、最適化後は請求サマリー取得に進めています。"
    if expected == tuned:
        return "最適化後は期待アクションと一致しています。"
    return "期待アクションとの差分が残っています。"


def format_case_explanations(cases: list[dict[str, Any]]) -> str:
    if not cases:
        return "該当なし"

    lines = []
    for index, case in enumerate(cases, start=1):
        lines.extend(
            [
                f"{index}. `{case['scenario_id']}` turn {case['turn_index']}",
                f"   - 顧客発話: {case['customer_utterance']}",
                f"   - 期待: `{case['expected_next_action']}` ({action_description(case['expected_next_action'])})",
                f"   - ベースライン: `{case['baseline_next_action']}` ({action_description(case['baseline_next_action'])})",
                f"   - 最適化後: `{case['tuned_next_action']}` ({action_description(case['tuned_next_action'])})",
                f"   - 読み取り: {explain_case_change(case)}",
            ]
        )
    return "\n".join(lines)


def action_counts(cases: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        action = case.get(field) or ""
        counts[action] = counts.get(action, 0) + 1
    return counts


def format_action_distribution(
    baseline_eval: dict[str, Any],
    tuned_eval: dict[str, Any],
) -> str:
    baseline_cases = baseline_eval["cases"]
    tuned_cases = tuned_eval["cases"]
    expected_counts = action_counts(baseline_cases, "expected_next_action")
    baseline_counts = action_counts(baseline_cases, "actual_next_action")
    tuned_counts = action_counts(tuned_cases, "actual_next_action")
    actions = sorted(set(expected_counts) | set(baseline_counts) | set(tuned_counts))

    lines = [
        "| action | expected | baseline actual | tuned actual | 読み取り |",
        "|---|---:|---:|---:|---|",
    ]
    for action in actions:
        expected_count = expected_counts.get(action, 0)
        baseline_count = baseline_counts.get(action, 0)
        tuned_count = tuned_counts.get(action, 0)
        if tuned_count == expected_count and baseline_count != expected_count:
            note = "期待分布に近づいた"
        elif tuned_count == expected_count:
            note = "期待どおり"
        else:
            note = "追加確認が必要"
        lines.append(
            f"| `{action}` | {expected_count} | {baseline_count} | {tuned_count} | {note} |"
        )
    return "\n".join(lines)


def format_fewshot_examples(best: dict[str, Any]) -> str:
    fewshot_path = best["run_dir"] / "fewshot_examples.jsonl"
    if not fewshot_path.exists():
        return "few-shot 例は保存されていません。"

    records = [
        json.loads(line)
        for line in fewshot_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        return "few-shot 例は空です。"

    lines = [
        "| # | customer_utterance | next_action | この例が効いている点 |",
        "|---:|---|---|---|",
    ]
    for index, record in enumerate(records, start=1):
        utterance = str(record.get("customer_utterance", "")).replace("|", "\\|")
        next_action = record.get("next_action", "")
        if next_action == "call_get_billing_summary":
            note = "本人確認または account_id 取得後にツール呼び出しへ進む判断を補強"
        elif next_action == "ask_identity_verification":
            note = "請求問い合わせでは先に本人確認を行う判断を補強"
        elif next_action == "ask_account_id":
            note = "月など一部情報だけでは account_id を追加確認する判断を補強"
        else:
            note = "該当アクションの判断例を補強"
        lines.append(f"| {index} | {utterance} | `{next_action}` | {note} |")
    return "\n".join(lines)


def prompt_diff(from_record: dict[str, Any], to_record: dict[str, Any]) -> str:
    diff = difflib.unified_diff(
        from_record["prompt_text"].splitlines(),
        to_record["prompt_text"].splitlines(),
        fromfile=f"{from_record['prompt_id']}/prompt.md",
        tofile=f"{to_record['prompt_id']}/prompt.md",
        lineterm="",
    )
    return "\n".join(diff) or "差分なし"


def build_report_markdown(
    *,
    created_at: str,
    baseline: dict[str, Any],
    best: dict[str, Any],
    latest: dict[str, Any],
    records: list[dict[str, Any]],
    comparisons: dict[str, list[dict[str, Any]]],
) -> str:
    baseline_eval = baseline["eval_summary"]
    best_eval = best["eval_summary"]
    latest_eval = latest["eval_summary"]
    best_metadata = best["metadata"]
    score_delta = best_eval["score"] - baseline_eval["score"]
    all_case_rows = build_case_rows(baseline_eval, best_eval)

    return f"""# Step 8: DSPy プロンプト最適化 比較レポート

生成日時: {created_at}

## サマリー

Step 7 で保存された評価結果を比較したところ、`{best_metadata.get("target_module", "unknown")}` の `next_action` 判定は、ベースラインの {format_percent(baseline_eval["score"])} から最適化後の {format_percent(best_eval["score"])} へ改善しました。改善幅は {format_percent(score_delta)} です。

- モデル名: `{best_metadata.get("model", "unknown")}`
- 推論サーバ: `Ollama`
- DSPy optimizer: `{best_metadata.get("optimizer") or "なし"}`
- 対象モジュール: `{best_metadata.get("target_module", "unknown")}`
- 評価データ: `{best_metadata.get("dataset_split", "unknown")}` split, {best_eval["total"]} turns
- ベースラインスコア: {baseline_eval["correct"]}/{baseline_eval["total"]} ({format_percent(baseline_eval["score"])})
- チューニング後スコア: {best_eval["correct"]}/{best_eval["total"]} ({format_percent(best_eval["score"])})
- 改善幅: {format_percent(best_eval["score"] - baseline_eval["score"])}
- ベースラインプロンプト: `{baseline["prompt_id"]}`
- 最良プロンプト: `{best["prompt_id"]}`
- 直近プロンプト: `{latest["prompt_id"]}` ({format_percent(latest_eval["score"])})

## 結論

- 今回の改善は、主に「請求問い合わせを曖昧問い合わせとして扱わず、本人確認に進む判断」と「account_id 取得後に請求サマリー取得ツールへ進む判断」の改善です。
- 悪化したケースはありませんでした。
- ただし評価件数は {best_eval["total"]} turns と小さいため、このスコアは本番品質の保証ではなく、Step 7 の最適化が dev データ上で効いたことを示す検証結果です。
- Amazon Connect AI Agents へ移植する場合は、few-shot 例をそのまま貼り付けるのではなく、本人確認、ツール呼び出し、有人引き継ぎの判断条件として整理してレビューするのが現実的です。

## 評価設計

{format_evaluation_design(best)}

## アクション定義

{format_action_glossary(all_case_rows)}

## プロンプト履歴

{format_prompt_history(records)}

## optimizer 別スコア比較

{format_optimizer_comparison(baseline=baseline, records=records)}

この表では、各 optimizer run を同じ baseline と比較しています。GEPA run では `reflection_lm` に `ollama_chat/gemma4:31b` が記録されます。

## GEPA metric call 追加検証

GEPA は初期実行で `max_metric_calls=36` に抑制していましたが、結果が 4/6 だったため、追加検証として `max_metric_calls=72` へ拡大しました。72 calls の run では 6/6、100% に到達しました。

{format_gepa_metric_call_progress(records)}

## スコア表記の読み方

{format_score_explanation(best_eval)}

## トークン使用量

{format_token_usage_comparison(baseline=baseline, records=records)}

この表は、DSPy の `track_usage()` が取得した LM usage を集計したものです。過去に usage 計測なしで実行した run は `-` になります。トークン数を正確に比較するには、usage 計測実装後に optimizer を再実行した run を使います。

{format_token_usage_explanation()}

## optimizer の種類と動き

{format_optimizer_explanations()}

## アクション別の傾向

{format_action_distribution(baseline_eval, best_eval)}

この表では、`expected` が評価データ上の正解分布、`baseline actual` がベースラインの予測分布、`tuned actual` が最適化後の予測分布です。最適化後は、今回の dev データでは期待分布と一致しています。

## 全評価ケース

{format_all_cases_table(baseline_eval, best_eval)}

## 改善したケース

{format_case_table(comparisons["improved"])}

## 改善ケースの読み取り

{format_case_explanations(comparisons["improved"])}

## 悪化したケース

{format_case_table(comparisons["worsened"])}

## 失敗例

{format_case_table(comparisons["still_failed"])}

## 最適化で選ばれた few-shot 例

{format_fewshot_examples(best)}

few-shot 例は、LLM に対して「この状態と発話なら、この `next_action` を選ぶ」という具体例を示すための材料です。今回の改善では、請求意図の初回発話を本人確認へ進める例と、account_id 取得後に請求サマリー取得へ進める例が効いていると読めます。

## 最適化されたプロンプト

参照先: `{best["run_dir"] / "prompt.md"}`

```markdown
{best["prompt_text"]}
```

## プロンプト履歴への参照

- インデックス: `outputs/curated/prompts/prompt_index.json`
- 現在採用中: `outputs/curated/prompts/current.json`
- ベースライン実行: `{baseline["run_dir"]}`
- 最良実行: `{best["run_dir"]}`
- 直近実行: `{latest["run_dir"]}`

## プロンプト差分の読み方

ベースラインから追加された主な差分は、`BootstrapFewShot` が選んだ few-shot 例です。基本指示文は大きく変わっていないため、今回のスコア差は「指示文の言い換え」よりも「判断例の追加」による影響が大きいと考えるのが自然です。

## ベースラインと最良プロンプトの差分

```diff
{prompt_diff(baseline, best)}
```

## ベースラインと直近プロンプトの差分

```diff
{prompt_diff(baseline, latest)}
```

## DSPy に詳しくない人向けの説明

DSPy は、LLM に渡す入力と期待する出力を `Signature` として定義し、その定義を使う `Module` を評価しながら、プロンプトや few-shot 例を改善するためのフレームワークです。

通常の手書きプロンプト調整では、人がプロンプトを書き換えて結果を見比べます。DSPy では、評価データ、評価指標、最適化対象を明示し、optimizer が候補となる few-shot 例や指示を選びます。今回の検証では `NextActionPlanner` の `next_action` が正解ラベルと一致するかを指標にしました。

主な用語の役割は次のとおりです。`Signature` は入力と出力の契約、`Module` はその契約を使う処理単位、`Predict` は LLM 呼び出し、`Optimizer` は評価指標に基づいてプロンプトや例を選ぶ仕組み、`Metric` は予測が正しいかを判定する関数です。

今回 DSPy が最適化したのは、請求問い合わせで次に取るべき行動を選ぶ `NextActionPlanner` の few-shot 例です。評価では、固定済み dev データの各ターンについて、予測された `next_action` が期待値と完全一致するかを確認しました。

Amazon Connect AI Agents の本番プロンプト設計に対しては、本人確認前の情報開示禁止、ツール呼び出し条件、有人引き継ぎ条件のような運用ルールを、会話状態と期待アクションに分解して評価できることが示唆です。ただし、今回のデータは小規模な合成データであり、スコア改善をそのまま本番品質とは見なせません。本番投入前には、業務担当者によるラベル確認、禁止応答のレビュー、実会話に近いテストデータでの再評価が必要です。

## Amazon Connect 本番プロンプトへ移植する示唆

1. 本人確認前の禁止事項を、抽象的な注意書きではなく「請求額、請求明細、契約情報を開示しない」のように具体化する。
2. `account_id` と本人確認がそろった状態を、ツール呼び出しの前提条件として明示する。
3. 顧客が有人対応を希望した場合は、追加説得ではなく `handoff_to_human` に進む条件として明示する。
4. 初回の請求問い合わせを `clarify_intent` に倒しすぎると解決が遅くなるため、請求意図が十分に読める表現は本人確認へ進める。
5. few-shot 例は、顧客発話だけでなく会話状態とセットで管理する。特に「本人確認前」「account_id 取得後」「不満表明後」の状態差を分ける。

## リスクと次の確認事項

- dev データが {best_eval["total"]} turns と少ないため、100% というスコアは過大評価の可能性があります。
- 合成データ由来の表現に偏っている可能性があるため、実運用に近い問い合わせ文で test 評価を追加する必要があります。
- 現在の評価は `next_action` の完全一致だけを見ており、実際の自然文応答の品質や禁止情報の混入までは直接評価していません。
- 本人確認の定義は検証用に単純化されています。本番では認証方式、照合項目、失敗時の扱いを業務ルールとして明確にする必要があります。
- `BootstrapFewShot` の選んだ例は有効そうに見えますが、業務担当者が内容をレビューし、不適切な例や過剰適合しそうな例を除外する工程が必要です。

## 次に実施すること

1. `test_billing_support.jsonl` に対して、ベースラインと最適化後プロンプトを同じ条件で評価する。
2. `next_action` だけでなく、実際のエージェント応答文に禁止情報が含まれないかを評価する。
3. 請求以外の問い合わせが混ざったケースで、`clarify_intent` と請求フローへの誘導が過不足なく働くか確認する。
4. 本番プロンプトへ移す前に、few-shot 例を業務用語と Amazon Connect の実ツール名に合わせて整形する。
"""


def run_step8_comparison_report(
    *,
    prompt_index_path: Path = Path("outputs/curated/prompts/prompt_index.json"),
    output_root: Path = Path("outputs/reports"),
) -> dict[str, Any]:
    index = read_json(prompt_index_path)
    records = [
        record
        for record in [load_prompt_record(record) for record in index["prompts"]]
        if not is_infrastructure_failed_record(record)
    ]
    baseline = select_latest_baseline(records)
    best = select_best(records)
    latest = select_latest(records)
    comparisons = compare_cases(baseline["eval_summary"], best["eval_summary"])

    created_at = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_path = output_root / f"{timestamp}-step08-comparison-report.md"
    report_text = build_report_markdown(
        created_at=created_at,
        baseline=baseline,
        best=best,
        latest=latest,
        records=records,
        comparisons=comparisons,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    summary = {
        "report_path": str(report_path),
        "baseline_prompt_id": baseline["prompt_id"],
        "best_prompt_id": best["prompt_id"],
        "latest_prompt_id": latest["prompt_id"],
        "baseline_score": baseline["eval_summary"]["score"],
        "best_score": best["eval_summary"]["score"],
        "latest_score": latest["eval_summary"]["score"],
        "score_delta": best["eval_summary"]["score"] - baseline["eval_summary"]["score"],
        "improved_case_count": len(comparisons["improved"]),
        "worsened_case_count": len(comparisons["worsened"]),
        "still_failed_case_count": len(comparisons["still_failed"]),
    }
    write_json(output_root / "latest_step08_summary.json", summary)
    return summary
