# DSPy Sample

DSPy と Ollama を使い、Amazon Connect AI Agents 風の請求問い合わせワークフローをローカルで検証するサンプルプロジェクトです。

目的は、手作業のプロンプト調整ではなく、固定した評価データと metric に基づいて `next_action` 判定を改善し、改善前後をレポートとして確認できる状態を作ることです。

## 検証対象

このプロジェクトでは、請求問い合わせ対応における `NextActionPlanner` を中心に検証します。

`NextActionPlanner` は、会話状態、業務ルール、顧客の最新発話を受け取り、次に取るべき action を1つ選びます。

主な action は以下です。

| action | 意味 |
|---|---|
| `ask_identity_verification` | 本人確認に必要な情報を依頼する |
| `ask_account_id` | 請求確認に必要な account_id を依頼する |
| `call_get_billing_summary` | 本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ |
| `clarify_intent` | 問い合わせ意図が曖昧なため確認する |
| `handoff_to_human` | 有人対応へ引き継ぐ |

## 現在の結果

Step 7/8 の検証では、GEPA による最適化で dev split の `next_action` 判定が以下のように改善しました。

| 項目 | 結果 |
|---|---:|
| baseline | 2/6 (33.3%) |
| optimized | 6/6 (100.0%) |
| 改善ケース | 4 |
| 悪化ケース | 0 |

最新の比較結果は [outputs/reports/step08-comparison-curated.md](outputs/reports/step08-comparison-curated.md) にあります。

## 前提

- Python 3.12 以上
- Ollama
- `gemma4:12b`
- GEPA を実行する場合は `gemma4:31b`

モデルを用意します。

```bash
ollama pull gemma4:12b
ollama pull gemma4:31b
ollama list
```

## セットアップ

```bash
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
```

`pyproject.toml` では `dspy` と `optuna` を依存関係に含めています。

## 実行方法

各ステップは `examples/steps/` から実行できます。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step01_connection_check.py
PYTHONPATH=src .venv/bin/python examples/steps/step02_single_turn_agent.py
PYTHONPATH=src .venv/bin/python examples/steps/step03_multi_turn_agent.py
PYTHONPATH=src .venv/bin/python examples/steps/step04_billing_scenario.py
PYTHONPATH=src .venv/bin/python examples/steps/step05_generate_synthetic_data.py
PYTHONPATH=src .venv/bin/python examples/steps/step06_review_and_freeze_dataset.py
```

プロンプト最適化を実行する場合は Step 7 を使います。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer bootstrap
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer mipro
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa --gepa-max-metric-calls 72
```

保存済みの Step 7 結果から比較レポートを作る場合は Step 8 を実行します。Step 8 は保存済み JSON を読むだけなので、Ollama サーバを起動していなくても実行できます。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step08_comparison_report.py
```

## DSPy / Ollama の注意点

Step 7 では OpenAI 互換 API ではなく、LiteLLM の `ollama_chat/gemma4:12b` provider を使います。

OpenAI 互換 API 経由では reasoning が `content` ではなく `reasoning` 側に出続け、DSPy の構造化出力パースに失敗するケースがありました。native chat provider を使うことで、`NextActionPlanner` の `next_action` 出力を安定して扱えるようにしています。

GEPA では通常推論の task model に `ollama_chat/gemma4:12b`、reflection LM に `ollama_chat/gemma4:31b` を使います。

## ディレクトリ構成

```text
data/
  prompts/       ベースラインプロンプトと候補プロンプト
  scenarios/     train/dev/test に固定した評価データ
  synthetic/     合成データ生成の出力
docs/
  plan/          検証計画
  steps/         ステップごとの説明
  learning/      DSPy と optimizer の学習ガイド
examples/steps/  ステップ別の実行スクリプト
src/             最新の実装
outputs/
  prompts/       current.json と prompt_index.json を Git 管理
  reports/       curated report と latest summary を Git 管理
```

## Git 管理方針

`outputs/` には実行するたびに増えるタイムスタンプ付き成果物が含まれるため、全量は Git 管理しません。

Git 管理するのは、再開やレビューに必要な選別済み成果物だけです。

- `outputs/prompts/current.json`
- `outputs/prompts/prompt_index.json`
- `outputs/reports/latest_step08_summary.json`
- `outputs/reports/*-curated.md`

`outputs/prompts/prompt_runs/` と通常のタイムスタンプ付き report は ignore します。

## 主要ドキュメント

- [検証計画](docs/plan/dspy_ollama_connect_agent_plan.md)
- [MIPROv2 / GEPA optimizer 計画](docs/plan/dspy_mipro_gepa_optimizer_plan.md)
- [Step 7: DSPy によるプロンプトチューニング](docs/steps/step07_prompt_optimization.md)
- [Step 8: 改善前後の比較レポート](docs/steps/step08_comparison_report.md)
- [DSPy プロンプト最適化 学習ガイド](docs/learning/dspy_prompt_optimization_guide.md)

## ライセンス

このリポジトリには現時点でライセンスファイルは含まれていません。
