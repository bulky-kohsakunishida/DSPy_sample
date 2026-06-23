# Step 9: 本番プロンプト適用フロー

## 目的

実運用に近い流れとして、次の3段階を再現する。

1. 本番環境で使う初期プロンプトを用意する
2. DSPy で評価データに基づいてプロンプトを最適化する
3. 最適化済み instruction を DSPy なしの本番ランタイム用プロンプトへ適用する

このステップでは、DSPy は最適化フェーズだけで使う。最終的な本番ランタイムは、保存済みの Markdown プロンプトを読み、Ollama の native chat API に直接リクエストする。

## 入力

```text
data/prompts/baseline_system_prompt.md
outputs/curated/prompts/current.json
outputs/prompts/prompt_runs/<current prompt id>/optimizer_artifacts.json
```

`current.json` は Step 7 の結果から現在採用候補の run を指す。現時点では `20260620-215349-gepa` を指している。

## 出力

```text
outputs/curated/production/
  next_action_planner_prompt.md
  next_action_planner_manifest.json
```

`next_action_planner_prompt.md` は、DSPy の `Signature` や `Predict` を使わずに LLM API へ渡せる本番用テンプレートである。

## 実行方法

最適化済みプロンプトを本番ランタイム用にエクスポートする。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step09_production_prompt_flow.py
```

Ollama へ直接投げるデモも同時に実行する場合は、`--run-demo` を付ける。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step09_production_prompt_flow.py --run-demo
```

このデモは DSPy を使わず、`http://localhost:11434/api/chat` を直接呼ぶ。

## このステップで確認できること

- 本番初期プロンプトは `data/prompts/baseline_system_prompt.md` として管理する
- DSPy は Step 7 で instruction を最適化し、`optimizer_artifacts.json` に保存する
- Step 9 は `current.json` が指す最良 run から instruction を抽出する
- 抽出した instruction を本番用テンプレートへ埋め込む
- 本番ランタイムは DSPy に依存せず、通常の LLM API 呼び出しで `next_action` を得る

## 注意点

この repo では `outputs/curated/` だけを Git 管理対象にし、`outputs/prompts/prompt_runs/` は Git 管理外にする。そのため、別環境で Step 9 を完全に再実行するには、同じ Step 7 run をローカルに持っているか、Step 7 を再実行して `current.json` が指す run を作る必要がある。

dev split で `6/6` になった結果は、本番品質を保証しない。本番適用前には、実会話に近いテストデータ、禁止事項レビュー、業務担当者レビューを追加する。
