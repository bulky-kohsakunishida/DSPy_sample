# Step 2: 単発問い合わせエージェント

## 目的

単発の顧客発話に対して、DSPy の `Signature` と `Module` を使って意図分類と次応答を生成する。

## 対象コード

- `examples/steps/step02_single_turn_agent.py`
- `src/connect_agent_eval/signatures.py`
- `src/connect_agent_eval/modules.py`
- `src/connect_agent_eval/labels.py`

## 構成

```text
step02_single_turn_agent.py
  ↓
configure_lm()
  ↓
SingleTurnSupportAgent
  ↓
dspy.Predict(SingleTurnTriage)
  ↓
Ollama gemma4:12b
```

## 入力

```text
customer_utterance
```

## 出力

```text
intent
intent_display_name
required_slots
response
escalate
```

## 設計ポイント

- `intent` は内部処理用の英語固定ラベルにする
- `intent_display_name` は人間向けの日本語表示名にする
- ラベルの正規化と表示名への変換はコード側で補正する
- 本人確認前に請求詳細を開示しない制約を `Signature` に含める

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step02_single_turn_agent.py
```
