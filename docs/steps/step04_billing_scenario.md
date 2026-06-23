# Step 4: 請求問い合わせシナリオ

## 目的

本人確認、請求明細確認、原因説明、必要時の有人引き継ぎを含む、Amazon Connect AI Agents 風の請求問い合わせフローを実行する。

このステップの主目的は、プロンプト最適化そのものではなく、後続ステップでチューニング対象にする業務シナリオ、状態遷移、ツール呼び出し境界を固定すること。

## 対象コード

- `examples/steps/step04_billing_scenario.py`
- `src/connect_agent_eval/tools.py`
- `src/connect_agent_eval/modules.py`
- `src/connect_agent_eval/state.py`
- `src/connect_agent_eval/simulator.py`

## 追加したモックツール

```text
lookup_customer(account_id)
get_billing_summary(account_id, month)
create_case(account_id, reason)
handoff_to_human(summary)
```

ツール結果は `ConversationState.tool_results` に保存する。これにより、各ターンの応答だけでなく、どの業務ツールを呼んだかも transcript で確認できる。

## 会話フロー

```text
請求が高いという問い合わせ
  ↓
本人確認と account_id を依頼
  ↓
account_id を受領して本人確認済みにする
  ↓
lookup_customer を呼ぶ
  ↓
請求月が分かっていれば get_billing_summary を呼ぶ
  ↓
請求増加理由を説明
  ↓
必要なら create_case と handoff_to_human を呼ぶ
```

## 安全制約

- 本人確認前に請求額、請求明細、契約情報を出さない。
- `account_id` が未確認の場合は請求明細確認ツールを呼ばない。
- 顧客が有人対応を希望した場合、または自動確認できない場合はケースを作成して引き継ぐ。
- 応答は顧客向けの簡潔な日本語にする。

## プロンプト最適化との関係

Step 4 のサンプル実行では、主要な請求問い合わせフローを確定的なコードで処理する。そのため、通常のサンプル実行では Ollama を呼ばず、DSPy optimizer によるプロンプト最適化もまだ行わない。

この分離にした理由は、本人確認前に請求詳細を出さない、未確認の `account_id` で請求明細ツールを呼ばない、といった安全上重要な制約をまずコード側で明確にするため。Step 4 では「どの状態で、どのツールを、どの条件で呼んでよいか」を検証可能にする。

後続ステップでプロンプト最適化対象にする候補は以下。

- 顧客発話から `billing_issue` を判定する意図分類
- 会話状態から `ask_identity_verification`、`confirm_issue_month`、`call_get_billing_summary`、`handoff_to_human` などの `next_action` を選ぶ判断
- ツール結果を顧客向けに簡潔に説明する応答生成
- 自動対応継続か有人引き継ぎかの判断

ただし、LLM がツール呼び出しを提案する構成にしても、最終的なツール実行可否はコード側で検証する。プロンプトで安全制約を指示するだけにせず、本人確認や必須スロットの充足は実行前ガードとして扱う。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step04_billing_scenario.py
```

Step 4 のサンプルは主要フローを確定的に処理するため、Ollama が起動していなくても実行できる。
