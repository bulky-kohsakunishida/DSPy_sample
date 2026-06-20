# DSPy MIPROv2 / GEPA optimizer 追加計画

作成日: 2026-06-20

## 目的

現在の Step 7 は `BootstrapFewShot` による `NextActionPlanner` の few-shot 最適化に限定している。

この計画では、追加 optimizer として `MIPROv2` と `GEPA` を導入し、以下を比較できる状態にする。

- ベースライン
- `BootstrapFewShot`
- `MIPROv2`
- `GEPA`

比較対象は引き続き、Amazon Connect AI Agents 風の請求問い合わせで次に取るべき行動を選ぶ `NextActionPlanner` とする。

## 前提

- task model: `ollama_chat/gemma4:12b`
- GEPA reflection model: `ollama_chat/gemma4:31b`
- 推論サーバ: Ollama
- 最初の評価対象: `data/scenarios/dev_billing_support.jsonl`
- optimizer 用データ: `data/scenarios/train_billing_support.jsonl`
- 出力先: `outputs/prompts`

GEPA は reflection に強いモデルを使う前提で設計する。通常の推論は `gemma4:12b`、GEPA の失敗分析と instruction 改善提案は `gemma4:31b` に分ける。

## 現状

現在の実装では [src/connect_agent_eval/optimize.py](../../src/connect_agent_eval/optimize.py) に以下が実装されている。

- `NextActionPlannerModule`
- `next_action_metric`
- `evaluate_module`
- `BootstrapFewShot` 実行
- `outputs/prompts/prompt_runs/<timestamp>-baseline`
- `outputs/prompts/prompt_runs/<timestamp>-bootstrap-fewshot`
- `outputs/prompts/prompt_index.json`
- `outputs/prompts/current.json`

Step 8 の比較レポートは [src/connect_agent_eval/report.py](../../src/connect_agent_eval/report.py) が `prompt_index.json` と各 run の `eval_summary.json` を読み込む構成になっている。

## 方針

最初に optimizer 実行基盤を共通化し、その後に `MIPROv2`、最後に `GEPA` を追加する。

`MIPROv2` は既存の `next_action_metric` を使えるため、先に実装する。`GEPA` は feedback metric と reflection LM の追加が必要なので、MIPROv2 の保存・比較形式が安定してから追加する。

## 出力ディレクトリ構成

```text
outputs/
  prompts/
    current.json
    prompt_index.json
    prompt_runs/
      <timestamp>-baseline/
        prompt.md
        metadata.json
        eval_summary.json
      <timestamp>-bootstrap-fewshot/
        prompt.md
        metadata.json
        eval_summary.json
        fewshot_examples.jsonl
      <timestamp>-mipro-v2/
        prompt.md
        metadata.json
        eval_summary.json
        fewshot_examples.jsonl
        optimizer_artifacts.json
      <timestamp>-gepa/
        prompt.md
        metadata.json
        eval_summary.json
        optimizer_artifacts.json
    optimizer_logs/
      <timestamp>-gepa/
```

## prompt_index.json の拡張

各 optimizer run を同じ形式で記録する。

```json
{
  "prompt_id": "20260620-120000-mipro-v2",
  "created_at": "2026-06-20T12:00:00+00:00",
  "source": "mipro_v2",
  "target_module": "NextActionPlanner",
  "parent_prompt_id": "20260620-120000-baseline",
  "dataset_split": "dev",
  "score": 0.83,
  "optimizer": "MIPROv2",
  "notes": "MIPROv2 auto=light による instruction と few-shot の最適化。",
  "path": "outputs/prompts/prompt_runs/20260620-120000-mipro-v2"
}
```

`current.json` は最高スコアの run を参照する。ただし同点の場合は以下の優先順で選ぶ。

1. `GEPA`
2. `MIPROv2`
3. `BootstrapFewShot`
4. `baseline`

同点時に後続 optimizer を優先するのは、より多くの最適化能力を持つ optimizer の成果物を確認対象にしやすくするため。ただし Step 8 レポートでは全 run を表示し、採用判断を人が確認できるようにする。

## Phase 1: optimizer 実行基盤の共通化

### 変更対象

- `src/connect_agent_eval/optimize.py`
- `examples/steps/step07_prompt_optimization.py`
- `docs/steps/step07_prompt_optimization.md`

### 実装内容

- `OptimizerRunConfig` を追加する。
- baseline 評価処理を `run_baseline_evaluation()` に分離する。
- `BootstrapFewShot` 実行処理を `run_bootstrap_fewshot_optimization()` に分離する。
- optimizer run の保存処理を共通化する。
- `prompt_index.json` を既存 run に追記できる構造にする。
- CLI で optimizer を選べるようにする。

### CLI 案

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer bootstrap
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer mipro
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer all
```

既存互換のため、引数なしのデフォルトは `bootstrap` とする。

### 完了条件

- 既存の `BootstrapFewShot` 実行結果が従来と同等に保存される。
- `prompt_index.json` に複数 run が記録される。
- Step 8 が既存 run を読める。

## Phase 2: MIPROv2 の追加

### 目的

`MIPROv2` により、few-shot 例だけでなく instruction 候補も含めて最適化する。

### 初期設定

```python
optimizer = dspy.MIPROv2(
    metric=next_action_metric,
    auto="light",
    num_threads=1,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
)

optimized_module = optimizer.compile(
    NextActionPlannerModule(),
    trainset=trainset,
    valset=devset,
    max_bootstrapped_demos=4,
    max_labeled_demos=4,
)
```

### 設定理由

- `auto="light"`: Ollama ローカル実行で探索コストを抑える。
- `num_threads=1`: ローカル Ollama で同時実行負荷を避ける。
- `max_bootstrapped_demos=4`: 既存 `BootstrapFewShot` と条件を揃える。
- `max_labeled_demos=4`: 既存 `BootstrapFewShot` と条件を揃える。
- `valset=devset`: train と dev の役割を分ける。

### 保存内容

`<timestamp>-mipro-v2/metadata.json`

```json
{
  "optimizer": "MIPROv2",
  "optimizer_params": {
    "auto": "light",
    "num_threads": 1,
    "max_bootstrapped_demos": 4,
    "max_labeled_demos": 4
  },
  "model": "ollama_chat/gemma4:12b",
  "target_module": "NextActionPlanner"
}
```

`optimizer_artifacts.json` には、取得可能な範囲で以下を保存する。

- selected demos
- predictor instructions
- optimizer stats
- compile settings

### 注意点

- `auto` を指定する場合、`num_candidates` や `num_trials` を同時指定しない。
- `MIPROv2` は探索回数が増えるため、初期実装では `auto="light"` 以外を使わない。
- 小さい dev set ではスコアが過大評価されやすい。

### 完了条件

- `--optimizer mipro` で MIPROv2 run が生成される。
- `prompt_index.json` に `source=mipro_v2` の run が追加される。
- Step 8 レポートに MIPROv2 が表示される。

## Phase 3: GEPA feedback metric の追加

### 目的

GEPA が失敗例から instruction 改善を行えるように、単なる bool metric ではなく feedback 付き metric を追加する。

### metric 案

```python
def next_action_feedback_metric(example, prediction, trace=None, pred_name=None, pred_trace=None):
    expected = normalize_action(example.next_action)
    actual = normalize_action(getattr(prediction, "next_action", ""))

    if actual == expected:
        return dspy.Prediction(
            score=1.0,
            feedback="正解です。期待された next_action と一致しています。",
        )

    feedback = (
        f"期待アクションは `{expected}` ですが、予測は `{actual}` でした。"
        " `conversation_state` の slots、last_agent_action、must_not、"
        "および `business_rules` の本人確認条件とツール呼び出し条件を優先してください。"
    )
    return dspy.Prediction(score=0.0, feedback=feedback)
```

### feedback 設計

誤りの種類に応じて feedback を分岐する。

- `expected=ask_identity_verification`, `actual=clarify_intent`
  - 請求意図が十分に明確な場合は本人確認へ進むべき、と説明する。
- `expected=call_get_billing_summary`, `actual=ask_identity_verification`
  - `account_id` と本人確認済み状態を読み取り、ツール呼び出しへ進むべき、と説明する。
- `expected=handoff_to_human`
  - 顧客が有人対応を希望した場合は追加質問より引き継ぎを優先する、と説明する。
- その他
  - expected / actual / state / rule の差分を短く説明する。

### 完了条件

- bool metric と feedback metric を用途別に使い分けられる。
- feedback metric 単体の簡易テストができる。
- GEPA run の評価結果が既存 `eval_summary.json` と同じ形式で保存される。

## Phase 4: GEPA の追加

### 目的

GEPA により、失敗例への feedback を使って instruction を反復改善する。

### モデル構成

- task model: `ollama_chat/gemma4:12b`
- reflection_lm: `ollama_chat/gemma4:31b`

task model は実際の `NextActionPlanner` 推論に使う。reflection model は GEPA が失敗例を分析し、改善案を作る用途に使う。

### 初期設定

```python
reflection_lm = dspy.LM(
    "ollama_chat/gemma4:31b",
    api_base="http://localhost:11434",
    api_key="ollama",
    temperature=1.0,
    max_tokens=2048,
)

optimizer = dspy.GEPA(
    metric=next_action_feedback_metric,
    auto="light",
    num_threads=1,
    reflection_minibatch_size=3,
    reflection_lm=reflection_lm,
    track_stats=True,
    log_dir=str(output_root / "optimizer_logs" / f"{timestamp}-gepa"),
)

optimized_module = optimizer.compile(
    NextActionPlannerModule(),
    trainset=trainset,
    valset=devset,
)
```

### 設定理由

- `reflection_lm=gemma4:31b`: 失敗分析と改善案生成には、通常推論より大きいモデルを使う。
- `temperature=1.0`: reflection では改善案の探索幅を確保する。
- `max_tokens=2048`: ローカル実行の負荷を抑えつつ、短い `NextActionPlanner` 改善には十分な上限にする。
- `auto="light"`: 初期導入では呼び出し回数と実行時間を抑える。
- `reflection_minibatch_size=3`: 現在の dev set が小さいため、過度に大きくしない。
- `num_threads=1`: Ollama の同時実行負荷を避ける。
- `track_stats=True`: Step 8 の比較レポートで GEPA の挙動を説明できるようにする。

### 保存内容

`<timestamp>-gepa/metadata.json`

```json
{
  "optimizer": "GEPA",
  "optimizer_params": {
    "auto": "light",
    "num_threads": 1,
    "reflection_minibatch_size": 3,
    "reflection_model": "ollama_chat/gemma4:31b",
    "reflection_temperature": 1.0,
    "reflection_max_tokens": 2048,
    "track_stats": true
  },
  "model": "ollama_chat/gemma4:12b",
  "target_module": "NextActionPlanner"
}
```

`optimizer_artifacts.json` には、取得可能な範囲で以下を保存する。

- GEPA stats
- reflection log directory
- selected candidate information
- final predictor instructions
- feedback metric summary

### 事前確認

```bash
ollama pull gemma4:31b
ollama list
```

DSPy からの接続確認:

```python
import dspy

reflection_lm = dspy.LM(
    "ollama_chat/gemma4:31b",
    api_base="http://localhost:11434",
    api_key="ollama",
    temperature=1.0,
    max_tokens=2048,
)
```

### 注意点

- `gemma4:31b` はローカル実行負荷が高い。M4 Pro / 64GB でも実行時間が長くなる可能性がある。
- reflection の品質が低い場合、GEPA が不適切な instruction を提案する可能性がある。
- `auto="light"` でも、BootstrapFewShot より実行時間は長くなる。
- GEPA のスコアが高くても、feedback metric や dev set に過適合している可能性がある。

### 完了条件

- `--optimizer gepa` で GEPA run が生成される。
- `metadata.json` に task model と reflection model が分離して記録される。
- `optimizer_logs/<timestamp>-gepa` が生成される。
- Step 8 レポートに GEPA が表示される。

## Phase 5: Step 8 比較レポート拡張

### 目的

`baseline`、`BootstrapFewShot`、`MIPROv2`、`GEPA` を同じレポートで比較する。

### 追加する表

```text
| optimizer | score | correct/total | improved | worsened | model | reflection_lm | path |
|---|---:|---:|---:|---:|---|---|---|
| baseline | 33.3% | 2/6 | - | - | gemma4:12b | - | ... |
| BootstrapFewShot | 100.0% | 6/6 | 4 | 0 | gemma4:12b | - | ... |
| MIPROv2 | ... | ... | ... | ... | gemma4:12b | - | ... |
| GEPA | ... | ... | ... | ... | gemma4:12b | gemma4:31b | ... |
```

### 追加する章

- optimizer 別の特徴
- optimizer 別スコア比較
- optimizer 別の改善ケース
- MIPROv2 の instruction / few-shot の変化
- GEPA の feedback と reflection の要約
- 最良 run の選定理由
- 本番プロンプトへ採用する要素
- 過適合リスク

### 完了条件

- Step 8 レポートに全 optimizer run が表示される。
- 最高スコア run と直近 run が分かる。
- GEPA の `reflection_lm` が `gemma4:31b` と明記される。

## Phase 6: 検証手順

### 事前準備

```bash
ollama pull gemma4:12b
ollama pull gemma4:31b
ollama list
```

### 実行

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer bootstrap
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer mipro
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa
PYTHONPATH=src .venv/bin/python examples/steps/step08_comparison_report.py
```

### 構文確認

```bash
.venv/bin/python -m compileall src examples
```

### 確認項目

- `prompt_index.json` に baseline / bootstrap / mipro / gepa が記録されている。
- `current.json` が最高スコア run を参照している。
- 各 run の `metadata.json` に optimizer パラメータが保存されている。
- GEPA run の `metadata.json` に `reflection_model=ollama_chat/gemma4:31b` が保存されている。
- Step 8 レポートで全 optimizer の比較ができる。

## リスク

### 実行時間

`MIPROv2` と `GEPA` は `BootstrapFewShot` より実行時間が長くなる。特に GEPA は `gemma4:31b` を reflection に使うため、ローカル環境では数十分かかる可能性がある。

対策:

- 初期設定は `auto="light"` に固定する。
- `num_threads=1` にする。
- 実行ログに開始時刻、終了時刻、経過秒数を保存する。

### 過適合

現在の dev set は小さいため、100% スコアでも本番品質とは限らない。

対策:

- `test_billing_support.jsonl` で最終評価する Step 9 を追加する。
- 合成データ以外の表現を増やす。
- `next_action` だけでなく、自然文応答の禁止事項違反も評価する。

### GEPA feedback 品質

feedback metric の文章が曖昧だと、GEPA が不適切な改善を行う可能性がある。

対策:

- 誤り種別ごとの feedback を明示する。
- GEPA の出力 instruction を人手レビューする。
- feedback を `expected`、`actual`、`state`、`rule` の4要素で構成する。

### reflection_lm の負荷

`gemma4:31b` は `gemma4:12b` より負荷が高い。

対策:

- reflection の `max_tokens` は初期値 `2048` に抑える。
- GEPA は単独実行できる CLI にする。
- 必要に応じて `--optimizer gepa` 実行時だけ `gemma4:31b` を使う。

## 実装順序

1. `optimize.py` の optimizer 共通化
2. CLI 引数 `--optimizer` の追加
3. 既存 `BootstrapFewShot` の回帰確認
4. `MIPROv2` 実装
5. Step 8 の複数 optimizer 比較対応
6. GEPA feedback metric 実装
7. `reflection_lm=ollama_chat/gemma4:31b` の GEPA 実装
8. Step 7 / Step 8 ドキュメント更新
9. 全 optimizer の実行確認
10. 比較レポート確認

## 完了条件

- `BootstrapFewShot`、`MIPROv2`、`GEPA` を CLI から個別実行できる。
- `GEPA` は `reflection_lm=ollama_chat/gemma4:31b` を使う。
- 各 optimizer の結果が同一形式で `outputs/prompts/prompt_runs` に保存される。
- `prompt_index.json` と `current.json` が更新される。
- Step 8 レポートで全 optimizer のスコア、改善ケース、プロンプト差分、リスクを比較できる。
