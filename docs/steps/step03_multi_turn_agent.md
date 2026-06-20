# Step 3: マルチターン会話状態

## 目的

複数ターンの会話で、意図、スロット、履歴、最後のアクション、有人対応要否を状態として保持する。

## 対象コード

- `examples/steps/step03_multi_turn_agent.py`
- `src/connect_agent_eval/state.py`
- `src/connect_agent_eval/signatures.py`
- `src/connect_agent_eval/modules.py`
- `src/connect_agent_eval/simulator.py`

## 全体構成

```text
step03_multi_turn_agent.py
  ↓
run_conversation()
  ↓
MultiTurnSupportAgent
  ↓
ConversationState
  ↓
deterministic transition または DSPy / Ollama
```

## 1ターンの処理

```text
顧客発話を受け取る
  ↓
history に user 発話を保存
  ↓
発話から account_id や issue_month を簡易抽出
  ↓
明確な状態遷移か判定
  ↓
明確ならコードで応答を決定
  ↓
曖昧なら DSPy / Ollama に判断させる
  ↓
intent / slots / next_action / response を state に反映
  ↓
history に agent 応答を保存
```

## ConversationState

```text
intent
intent_display_name
slots
history
last_agent_action
handoff_required
```

## 役割分担

DSPy / Ollama に任せること:

- 初回発話の意図分類
- 曖昧な発話に対する次アクション判断
- 自然な応答文生成

コード側で処理すること:

- `account_id` の抽出
- `issue_month` の抽出
- 本人確認済みフラグの更新
- 明確な状態遷移
- 会話履歴とスロットの保持

## この分離にした理由

2ターン目以降もすべて LLM に渡すと、`gemma4:12b` が内部推論を長く生成し、DSPy の出力パースに失敗した。本人確認やスロット充足のような明確な処理はコード側で扱い、LLM は曖昧な判断に集中させる。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step03_multi_turn_agent.py
```
