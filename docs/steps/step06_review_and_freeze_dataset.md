# Step 6: 評価データセットのレビューと固定化

## 目的

Step 5 で生成したレビュー前の合成データを確認し、プロンプト最適化と評価に使う初期データセットとして固定する。

このステップでは DSPy optimizer はまだ実行しない。Step 7 で optimizer を回す前に、入力データ、正解ラベル、禁止事項、分割方針を固定する。

## 対象コード

- `examples/steps/step06_review_and_freeze_dataset.py`
- `src/connect_agent_eval/curate.py`

## 入力

```text
data/
  synthetic/
    generated_scenarios.jsonl
    generated_prompts.json
    generated_fewshot_examples.jsonl
    generation_manifest.json
```

## 出力

```text
data/
  scenarios/
    train_billing_support.jsonl
    dev_billing_support.jsonl
    test_billing_support.jsonl
    review_report.json
  prompts/
    baseline_system_prompt.md
    candidate_prompts.json
```

## レビュー観点

- `intent` が許可ラベルに含まれるか。
- 各 turn に `role`、`content`、`expected_next_action` があるか。
- `expected_next_action` が許可アクションに含まれるか。
- 請求問い合わせには本人確認前の禁止事項が明示されているか。
- `tool_calls` が本人確認と `account_id` の制約に反していないか。
- 実在しそうな電話番号や住所を含まないか。

## 固定化方針

Step 5 の `review_split_hint` に従って、候補データを以下に分ける。

- `train`: DSPy optimizer 用
- `dev`: チューニング中の比較用
- `test`: 最終評価専用

固定後の `scenario_id` は `billing_syn_001` のような生成 ID から `billing_001` のような評価用 ID に変換し、元 ID は `source_scenario_id` に残す。

## 注意

このステップのレビューは機械的な初期チェックであり、最終的な業務レビューの代替ではない。Step 7 で optimizer を実行する前に、必要に応じて `review_report.json` と固定済み JSONL を人手で確認する。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step06_review_and_freeze_dataset.py
```
