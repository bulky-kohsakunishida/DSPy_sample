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

## Step 3 時点のチューニング対象プロンプト

Step 3 時点でチューニング対象になるのは、主に `MultiTurnTriage` が DSPy 経由で組み立てる「次アクション判断プロンプト」。

完成後の Amazon Connect 用の巨大なシステムプロンプト全体ではなく、現時点では以下の判断をする部分を対象にする。

```text
現在の会話状態を見て、
最新の顧客発話に対して、
次に何をすべきかを決める
```

### 入力イメージ

`MultiTurnTriage` には、次の3つを渡す。

```text
conversation_state
business_rules
customer_utterance
```

プロンプトとしては、概念的に以下のような内容になる。

```text
あなたはコンタクトセンターのAIエージェントです。
現在の会話状態、業務ルール、最新の顧客発話をもとに、
次のアクションと応答を決めてください。

現在の会話状態:
{
  "intent": "billing_issue",
  "intent_display_name": "請求問い合わせ",
  "slots": {
    "customer_name": null,
    "account_id": null,
    "issue_month": "今月",
    "identity_verification": null
  },
  "last_agent_action": "ask_identity_verification"
}

業務ルール:
- 本人確認が済むまで、請求額、明細、契約情報などの機微情報を開示しない
- 請求問い合わせでは、本人確認と account_id が必要
- 顧客が強い不満を示しても、まず謝意を示し、確認に必要な情報を一つずつ集める
- 自動対応で判断できない場合のみ有人対応へエスカレーションする
- 応答は簡潔な日本語にする

最新の顧客発話:
今月の請求が急に高くなっています。理由を確認してもらえますか？
```

### 出力イメージ

DSPy には、以下のような構造化出力を期待する。

```json
{
  "intent": "billing_issue",
  "intent_display_name": "請求問い合わせ",
  "required_slots": "identity_verification, account_id",
  "next_action": "ask_identity_verification",
  "response": "お困りの状況を承知いたしました。詳細を確認するため、まずはご本人様確認のお手続きをお願いいたします。",
  "escalate": "false"
}
```

### チューニングで改善したい点

- 正しい `intent` を選ぶ
- 不足しているスロットを正しく出す
- `next_action` を安定して選ぶ
- 本人確認前に請求詳細を出さない
- 必要以上に有人対応へ逃げない
- 顧客向け応答を簡潔にする
- 出力形式を崩さない

特に重要なのは `next_action`。初回発話では `ask_identity_verification` を選び、アカウントIDが取れた後は `explain_next_step` や、Step 4 以降で追加する `call_get_billing_summary` のようなツール呼び出しアクションを選べるようにする。

### Step 3 時点ではまだ本格的に扱わないこと

- 請求明細の説明文
- ツール呼び出し結果の要約
- 本番 Amazon Connect 用の最終システムプロンプト
- 大規模な few-shot セット
- エスカレーション詳細ルール

これらは Step 4 以降で、モックツールや業務シナリオが入ってから対象にする。

### コード上の対応箇所

- `src/connect_agent_eval/signatures.py` の `MultiTurnTriage`
- `src/connect_agent_eval/simulator.py` の `DEFAULT_BUSINESS_RULES`
- `src/connect_agent_eval/modules.py` の `MultiTurnSupportAgent`

特に `MultiTurnTriage` の `Signature` が、DSPy がプロンプトを組み立てる元になる。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step03_multi_turn_agent.py
```
