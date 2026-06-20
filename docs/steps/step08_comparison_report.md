# Step 8: 改善前後の比較レポート

## 目的

Step 7 で保存したベースライン評価と DSPy optimizer 後の評価結果を比較し、Amazon Connect AI Agents の本番プロンプト設計に使える示唆を Markdown レポートとして残す。

## 対象コード

- `examples/steps/step08_comparison_report.py`
- `src/connect_agent_eval/report.py`

## 入力

```text
outputs/
  prompts/
    prompt_index.json
    current.json
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
```

## 出力

```text
outputs/
  reports/
    <timestamp>-step08-comparison-report.md
    latest_step08_summary.json
```

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step08_comparison_report.py
```

Step 8 は Step 7 の保存済み結果を読み込むだけなので、Ollama サーバを起動していなくても実行できる。

## レポートに含める内容

- モデル名
- 推論サーバ
- DSPy optimizer
- 評価設計
- 評価件数
- ベースラインスコア
- チューニング後スコア
- プロンプト履歴
- アクション定義
- アクション別の予測分布
- 全評価ケース
- 改善したケース
- 改善ケースの読み取り
- 悪化したケース
- 失敗例
- optimizer が選んだ few-shot 例
- 最適化されたプロンプト
- プロンプト履歴への参照
- ベースライン、最良、直近プロンプトの差分
- プロンプト差分の読み方
- DSPy に詳しくない人向けの説明
- Amazon Connect 本番プロンプトへ移植できる示唆
- リスクと次の確認事項
