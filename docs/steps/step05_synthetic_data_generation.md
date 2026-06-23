# Step 5: 合成データ生成

## 目的

請求問い合わせシナリオをもとに、評価データセットとプロンプト最適化の候補にするレビュー前データを生成する。

Step 5 では、まだ DSPy optimizer によるチューニングは行わない。生成したデータもそのまま評価用に固定せず、Step 6 で人手レビューして `train`、`dev`、`test` に分ける。

## 対象コード

- `examples/steps/step05_generate_synthetic_data.py`
- `src/connect_agent_eval/synthesize.py`

## 生成ファイル

```text
data/
  synthetic/
    generated_scenarios.jsonl
    generated_prompts.json
    generated_fewshot_examples.jsonl
    generation_manifest.json
```

## 生成方針

現時点では Ollama に自由生成させず、固定テンプレートで再現可能な合成データを生成する。

理由は以下。

- Step 6 のレビュー前に、データ構造と評価観点を安定させるため。
- 実在しそうな個人情報や不自然な ID が混入するリスクを避けるため。
- 後続の optimizer で使う `next_action`、必須スロット、禁止事項を明示するため。
- 生成結果を毎回変えず、差分レビューしやすくするため。

## 含めるシナリオ分類

- 通常の請求金額確認
- 請求が急に高くなった問い合わせ
- 割引やキャンペーン終了による増額
- 追加利用料による増額
- 本人確認情報が不足しているケース
- 顧客が不満を強く表明するケース
- ツール結果が見つからないケース
- 有人対応が必要なケース
- 意図が曖昧なケース
- 請求以外の問い合わせが混ざるケース

## レビュー前データの扱い

`generated_scenarios.jsonl` は候補データであり、固定済み評価データではない。

Step 6 では以下を確認する。

- 正解ラベルが業務ルールと一致しているか。
- 本人確認前に開示してはいけない情報が `must_not` に含まれているか。
- `tool_calls` と `next_action` が Step 4 の安全制約と一致しているか。
- optimizer 用データと最終評価用データが混在していないか。
- 表現やシナリオが偏っていないか。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step05_generate_synthetic_data.py
```

実行後、`generation_manifest.json` に生成日時、生成方式、生成件数、採用件数、除外件数、データ分割方針を記録する。
