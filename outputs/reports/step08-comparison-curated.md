# Step 8: DSPy プロンプト最適化 比較レポート

生成日時: 2026-06-21T07:59:00.819509+00:00

## サマリー

Step 7 で保存された評価結果を比較したところ、`NextActionPlanner` の `next_action` 判定は、ベースラインの 33.3% から最適化後の 100.0% へ改善しました。改善幅は 66.7% です。

- モデル名: `ollama_chat/gemma4:12b`
- 推論サーバ: `Ollama`
- DSPy optimizer: `GEPA`
- 対象モジュール: `NextActionPlanner`
- 評価データ: `dev` split, 6 turns
- ベースラインスコア: 2/6 (33.3%)
- チューニング後スコア: 6/6 (100.0%)
- 改善幅: 66.7%
- ベースラインプロンプト: `20260620-215349-baseline`
- 最良プロンプト: `20260620-215349-gepa`
- 直近プロンプト: `20260620-215349-gepa` (100.0%)

## 結論

- 今回の改善は、主に「請求問い合わせを曖昧問い合わせとして扱わず、本人確認に進む判断」と「account_id 取得後に請求サマリー取得ツールへ進む判断」の改善です。
- 悪化したケースはありませんでした。
- ただし評価件数は 6 turns と小さいため、このスコアは本番品質の保証ではなく、Step 7 の最適化が dev データ上で効いたことを示す検証結果です。
- Amazon Connect AI Agents へ移植する場合は、few-shot 例をそのまま貼り付けるのではなく、本人確認、ツール呼び出し、有人引き継ぎの判断条件として整理してレビューするのが現実的です。

## 評価設計

- 評価単位: 会話シナリオ全体ではなく、各 turn の `next_action` 判定を 1 サンプルとして評価
- 入力: `conversation_state`, `business_rules`, `customer_utterance`
- 出力: `next_action`
- 正解条件: 予測した `next_action` が固定済みデータの `expected_next_action` と完全一致
- 対象 split: `dev`
- train 件数: 7
- dev 件数: 6
- optimizer パラメータ: `auto=None`, `log_dir=outputs/prompts/optimizer_logs/20260620-215349-gepa`, `max_metric_calls=72`, `num_threads=1`, `reflection_max_tokens=2048`, `reflection_minibatch_size=3`, `reflection_model=ollama_chat/gemma4:31b`, `reflection_temperature=1.0`, `track_stats=True`


## アクション定義

| action | 意味 |
|---|---|
| `ask_identity_verification` | 本人確認に必要な情報を依頼する |
| `call_get_billing_summary` | 本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ |
| `clarify_intent` | 問い合わせ意図が曖昧なため確認する |
| `handoff_to_human` | 有人対応へ引き継ぐ |

## プロンプト履歴

| prompt_id | source | optimizer | score | correct | model | reflection_lm | path |
|---|---|---|---:|---:|---|---|---|
| `20260620-085645-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-085645-baseline` |
| `20260620-085645-bootstrap-fewshot` | `bootstrap_fewshot` | `BootstrapFewShot` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-085645-bootstrap-fewshot` |
| `20260620-133537-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-133537-baseline` |
| `20260620-133537-bootstrap-fewshot` | `bootstrap_fewshot` | `BootstrapFewShot` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-133537-bootstrap-fewshot` |
| `20260620-134343-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-134343-baseline` |
| `20260620-134343-mipro-v2` | `mipro_v2` | `MIPROv2` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-134343-mipro-v2` |
| `20260620-135648-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-135648-baseline` |
| `20260620-135648-gepa` | `gepa` | `GEPA` | 66.7% | 4/6 | `ollama_chat/gemma4:12b` | `ollama_chat/gemma4:31b` | `outputs/prompts/prompt_runs/20260620-135648-gepa` |
| `20260620-212049-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-212049-baseline` |
| `20260620-212049-bootstrap-fewshot` | `bootstrap_fewshot` | `BootstrapFewShot` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-212049-bootstrap-fewshot` |
| `20260620-212049-gepa` | `gepa` | `GEPA` | 66.7% | 4/6 | `ollama_chat/gemma4:12b` | `ollama_chat/gemma4:31b` | `outputs/prompts/prompt_runs/20260620-212049-gepa` |
| `20260620-212049-mipro-v2` | `mipro_v2` | `MIPROv2` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-212049-mipro-v2` |
| `20260620-215349-baseline` | `baseline` | `なし` | 33.3% | 2/6 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-215349-baseline` |
| `20260620-215349-gepa` | `gepa` | `GEPA` | 100.0% | 6/6 | `ollama_chat/gemma4:12b` | `ollama_chat/gemma4:31b` | `outputs/prompts/prompt_runs/20260620-215349-gepa` |

## optimizer 別スコア比較

| optimizer | score | correct | improved | worsened | still failed | model | reflection_lm | path |
|---|---:|---:|---:|---:|---:|---|---|---|
| `baseline` | 33.3% | 2/6 | - | - | - | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-215349-baseline` |
| `BootstrapFewShot` | 100.0% | 6/6 | 4 | 0 | 0 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-212049-bootstrap-fewshot` |
| `MIPROv2` | 100.0% | 6/6 | 4 | 0 | 0 | `ollama_chat/gemma4:12b` | `-` | `outputs/prompts/prompt_runs/20260620-212049-mipro-v2` |
| `GEPA` | 100.0% | 6/6 | 4 | 0 | 0 | `ollama_chat/gemma4:12b` | `ollama_chat/gemma4:31b` | `outputs/prompts/prompt_runs/20260620-215349-gepa` |

この表では、各 optimizer run を同じ baseline と比較しています。GEPA run では `reflection_lm` に `ollama_chat/gemma4:31b` が記録されます。

## GEPA metric call 追加検証

GEPA は初期実行で `max_metric_calls=36` に抑制していましたが、結果が 4/6 だったため、追加検証として `max_metric_calls=72` へ拡大しました。72 calls の run では 6/6、100% に到達しました。

| prompt_id | max_metric_calls | score | correct | total_tokens | LM calls | elapsed_seconds | path |
|---|---:|---:|---:|---:|---:|---:|---|
| `20260620-135648-gepa` | 36 | 66.7% | 4/6 | - | - | 425.5 | `outputs/prompts/prompt_runs/20260620-135648-gepa` |
| `20260620-212049-gepa` | 36 | 66.7% | 4/6 | 49,878 | 46 | 557.0 | `outputs/prompts/prompt_runs/20260620-212049-gepa` |
| `20260620-215349-gepa` | 72 | 100.0% | 6/6 | 102,942 | 83 | 845.9 | `outputs/prompts/prompt_runs/20260620-215349-gepa` |

## スコア表記の読み方

`6/6` のような表記は、評価対象 6 turns のうち何件が正解したかを表します。`6/6、100%` なら、6件すべてで予測した `next_action` が正解ラベルと一致したという意味です。

このプロジェクトの評価は、自然文応答のうまさではなく、各 turn で `NextActionPlanner` が選んだ `next_action` の完全一致を見ています。たとえば、期待値が `call_get_billing_summary` で、モデル出力も `call_get_billing_summary` なら1件正解です。説明文が混ざる、別 action を出す、例外で出力できない場合は不正解です。

`score` は `correct / total` で計算します。今回なら `2/6 = 33.3%`、`4/6 = 66.7%`、`6/6 = 100.0%` です。評価件数が少ないため、100% はこの dev データ上で全問正解したという意味であり、本番品質を保証するものではありません。


## トークン使用量

| optimizer | total_tokens | prompt_tokens | completion_tokens | LM calls | model breakdown | path |
|---|---:|---:|---:|---:|---|---|
| `baseline` | 3,812 | 3,694 | 118 | 6 | `ollama_chat/gemma4:12b`: 3,812 tokens / 6 calls | `outputs/prompts/prompt_runs/20260620-215349-baseline` |
| `BootstrapFewShot` | 19,690 | 19,444 | 246 | 12 | `ollama_chat/gemma4:12b`: 19,690 tokens / 12 calls | `outputs/prompts/prompt_runs/20260620-212049-bootstrap-fewshot` |
| `MIPROv2` | 167,708 | 162,967 | 4,741 | 96 | `ollama_chat/gemma4:12b`: 167,708 tokens / 96 calls | `outputs/prompts/prompt_runs/20260620-212049-mipro-v2` |
| `GEPA` | 102,942 | 97,302 | 5,640 | 83 | `ollama_chat/gemma4:12b`: 90,703 tokens / 78 calls<br>`ollama_chat/gemma4:31b`: 12,239 tokens / 5 calls | `outputs/prompts/prompt_runs/20260620-215349-gepa` |

この表は、DSPy の `track_usage()` が取得した LM usage を集計したものです。過去に usage 計測なしで実行した run は `-` になります。トークン数を正確に比較するには、usage 計測実装後に optimizer を再実行した run を使います。

この表の token は、LLM に渡した入力と、LLM が生成した出力をモデル側の単位で数えたものです。文字数や単語数とは一致せず、モデルが内部的に処理する分割単位です。

- `prompt_tokens`: LLM に渡した入力側の token 数。プロンプト、business rules、conversation_state、customer_utterance、few-shot 例、GEPA の reflection 用入力などが含まれます。
- `completion_tokens`: LLM が生成した出力側の token 数。`next_action`、MIPROv2 の instruction 候補、GEPA の reflection や改善プロンプト案などが含まれます。
- `total_tokens`: `prompt_tokens + completion_tokens`。処理量やコスト感を見るときの合計値です。
- `LM calls`: LLM を呼び出した回数。1 call ごとに prompt/completion tokens が発生します。
- `model breakdown`: モデル別の token と call 数の内訳です。GEPA では通常の `next_action` 予測を行う task model と、失敗例を振り返る reflection LM が分かれて記録されます。

今回の GEPA 72 calls run では `total_tokens=102,942` のうち `prompt_tokens=97,302`、`completion_tokens=5,640` です。つまり、生成量よりも「モデルに読ませた入力」の比率が大きい run だったと読めます。

## optimizer の種類と動き

### baseline

optimizer を使わず、固定の `baseline_system_prompt.md` と `NextActionPlanner` の Signature だけで推論します。比較の基準です。ここで失敗したケースが、optimizer によって改善できたかを見ます。

### BootstrapFewShot

`BootstrapFewShot` は、train データから few-shot 例を選び、LLM に「この入力ならこの action」という具体例を追加する optimizer です。instruction 自体を大きく書き換えるよりも、判断例を足してモデルの出力を安定させる動きになります。

このプロジェクトでは、`next_action_metric` で正解した train 例を使い、最大4件の bootstrapped demos と最大4件の labeled demos を候補として `NextActionPlanner` に付与します。その後、dev データで `next_action` が一致するかを評価します。

### MIPROv2

`MIPROv2` は、few-shot 例だけでなく instruction 候補も探索する optimizer です。複数の instruction 案と few-shot セットを作り、それらの組み合わせを評価しながら、よりスコアが高いプロンプト構成を探します。

このプロジェクトでは `auto="light"` で実行し、`gemma4:12b` を task model と prompt model に使います。ただし、instruction 候補生成では長めの出力が必要なため、prompt model の `max_tokens` は `1024` にしています。探索には `optuna` が必要です。

### GEPA

`GEPA` は、失敗例に対する feedback を使って instruction を反復的に改善する optimizer です。単に正解/不正解を見るだけでなく、「なぜ違ったか」「どのルールを優先すべきか」という feedback を reflection LM に渡し、新しい instruction 案を生成します。

このプロジェクトでは、通常推論の task model は `ollama_chat/gemma4:12b`、reflection LM は `ollama_chat/gemma4:31b` です。`next_action_feedback_metric` が expected と actual の差分を説明し、GEPA がその feedback から改善案を作ります。

GEPA の `auto="light"` はローカル環境では約404 metric calls と重かったため、初期検証では `auto=None`, `max_metric_calls=36` に制限しました。その後、36 calls では 4/6 にとどまったため、段階的に 72 calls へ拡大し、dev データ上で 6/6 に到達することを確認しました。


## アクション別の傾向

| action | expected | baseline actual | tuned actual | 読み取り |
|---|---:|---:|---:|---|
| `ask_identity_verification` | 2 | 2 | 2 | 期待どおり |
| `call_get_billing_summary` | 2 | 0 | 2 | 期待分布に近づいた |
| `clarify_intent` | 1 | 3 | 1 | 期待分布に近づいた |
| `handoff_to_human` | 1 | 1 | 1 | 期待どおり |

この表では、`expected` が評価データ上の正解分布、`baseline actual` がベースラインの予測分布、`tuned actual` が最適化後の予測分布です。最適化後は、今回の dev データでは期待分布と一致しています。

## 全評価ケース

| scenario | turn | expected | baseline | tuned | 判定 | utterance |
|---|---:|---|---|---|---|---|
| billing_002 | 1 | `ask_identity_verification` | `clarify_intent` | `ask_identity_verification` | 改善 | 今月だけ急に請求が高くなっています。理由を教えてください。 |
| billing_002 | 2 | `call_get_billing_summary` | `ask_identity_verification` | `call_get_billing_summary` | 改善 | ACC-123456 です。 |
| billing_006 | 1 | `ask_identity_verification` | `clarify_intent` | `ask_identity_verification` | 改善 | 請求が高すぎます。納得できません。 |
| billing_006 | 2 | `call_get_billing_summary` | `ask_identity_verification` | `call_get_billing_summary` | 改善 | ACC-123456、今月です。 |
| billing_006 | 3 | `handoff_to_human` | `handoff_to_human` | `handoff_to_human` | 維持 | 説明されても納得できないので担当者に代わってください。 |
| billing_009 | 1 | `clarify_intent` | `clarify_intent` | `clarify_intent` | 維持 | 今月の件、どうなっていますか。 |

## 改善したケース

| scenario | turn | expected | baseline | tuned | 判定 | utterance |
|---|---:|---|---|---|---|---|
| billing_002 | 1 | `ask_identity_verification` | `clarify_intent` | `ask_identity_verification` | 改善 | 今月だけ急に請求が高くなっています。理由を教えてください。 |
| billing_002 | 2 | `call_get_billing_summary` | `ask_identity_verification` | `call_get_billing_summary` | 改善 | ACC-123456 です。 |
| billing_006 | 1 | `ask_identity_verification` | `clarify_intent` | `ask_identity_verification` | 改善 | 請求が高すぎます。納得できません。 |
| billing_006 | 2 | `call_get_billing_summary` | `ask_identity_verification` | `call_get_billing_summary` | 改善 | ACC-123456、今月です。 |

## 改善ケースの読み取り

1. `billing_002` turn 1
   - 顧客発話: 今月だけ急に請求が高くなっています。理由を教えてください。
   - 期待: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - ベースライン: `clarify_intent` (問い合わせ意図が曖昧なため確認する)
   - 最適化後: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - 読み取り: 請求に関する発話を曖昧問い合わせとして扱っていたが、最適化後は本人確認が必要な請求問い合わせとして扱えています。
2. `billing_002` turn 2
   - 顧客発話: ACC-123456 です。
   - 期待: `call_get_billing_summary` (本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ)
   - ベースライン: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - 最適化後: `call_get_billing_summary` (本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ)
   - 読み取り: account_id が提示された後も本人確認を繰り返していたが、最適化後は請求サマリー取得に進めています。
3. `billing_006` turn 1
   - 顧客発話: 請求が高すぎます。納得できません。
   - 期待: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - ベースライン: `clarify_intent` (問い合わせ意図が曖昧なため確認する)
   - 最適化後: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - 読み取り: 請求に関する発話を曖昧問い合わせとして扱っていたが、最適化後は本人確認が必要な請求問い合わせとして扱えています。
4. `billing_006` turn 2
   - 顧客発話: ACC-123456、今月です。
   - 期待: `call_get_billing_summary` (本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ)
   - ベースライン: `ask_identity_verification` (本人確認に必要な情報を依頼する)
   - 最適化後: `call_get_billing_summary` (本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ)
   - 読み取り: account_id が提示された後も本人確認を繰り返していたが、最適化後は請求サマリー取得に進めています。

## 悪化したケース

該当なし

## 失敗例

該当なし

## 最適化で選ばれた few-shot 例

few-shot 例は保存されていません。

few-shot 例は、LLM に対して「この状態と発話なら、この `next_action` を選ぶ」という具体例を示すための材料です。今回の改善では、請求意図の初回発話を本人確認へ進める例と、account_id 取得後に請求サマリー取得へ進める例が効いていると読めます。

## 最適化されたプロンプト

参照先: `outputs/prompts/prompt_runs/20260620-215349-gepa/prompt.md`

```markdown
あなたは請求問い合わせを扱うコンタクトセンターのAIエージェントです。
現在の会話状態、業務ルール、最新の顧客発話をもとに次アクションを選びます。
本人確認が済むまで請求額、請求明細、契約情報は開示しません。
必要な情報が不足している場合は、一度に聞きすぎず、次に必要な情報を尋ねます。
自動確認できない場合、または顧客が希望した場合は有人対応へ引き継ぎます。
応答は簡潔な日本語にします。

## Optimizer

GEPA

## Predictor artifacts

[
  {
    "demo_count": 0,
    "instruction": "# Task Overview\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\n\n# Operational Guidelines & Logic Flow\n\n## 1. Priority of Decision Making\nWhen determining the action, prioritize information in the following order:\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\n\n## 2. Strict Guardrails (Must-Not Actions)\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\n\n## 3. Specific Action Selection Logic\n- **Intent Resolution:** If the customer's intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\n- **Slot Filling & Progression:** \n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\n- **Ambiguity:** Only use `clarify_intent` if the user's request is truly vague and no clear intent can be mapped to business rules or tools.\n\n# Summary of Required Slots for Billing Inquiries\nTo resolve billing issues, you must ensure the following are collected/verified:\n1. `account_id`\n2. `identity_verification` (Status: Verified)\n\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.",
    "predictor_index": 0,
    "predictor_type": "Predict",
    "signature": "StringSignature(conversation_state, business_rules, customer_utterance -> next_action\n    instructions='# Task Overview\\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\\n\\n# Operational Guidelines & Logic Flow\\n\\n## 1. Priority of Decision Making\\nWhen determining the action, prioritize information in the following order:\\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\\n\\n## 2. Strict Guardrails (Must-Not Actions)\\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \\n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\\n\\n## 3. Specific Action Selection Logic\\n- **Intent Resolution:** If the customer\\'s intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\\n- **Slot Filling & Progression:** \\n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\\n- **Ambiguity:** Only use `clarify_intent` if the user\\'s request is truly vague and no clear intent can be mapped to business rules or tools.\\n\\n# Summary of Required Slots for Billing Inquiries\\nTo resolve billing issues, you must ensure the following are collected/verified:\\n1. `account_id`\\n2. `identity_verification` (Status: Verified)\\n\\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.'\n    conversation_state = Field(annotation=str required=True json_schema_extra={'desc': 'intent、slots、last_agent_action、利用可能ツールを含む現在の会話状態。', '__dspy_field_type': 'input', 'prefix': 'Conversation State:'})\n    business_rules = Field(annotation=str required=True json_schema_extra={'desc': '本人確認、ツール実行可否、有人引き継ぎに関する業務ルール。', '__dspy_field_type': 'input', 'prefix': 'Business Rules:'})\n    customer_utterance = Field(annotation=str required=True json_schema_extra={'desc': '日本語の最新の顧客発話。', '__dspy_field_type': 'input', 'prefix': 'Customer Utterance:'})\n    next_action = Field(annotation=str required=True json_schema_extra={'desc': '次に行う処理を1つだけ出力する。許可値: ask_identity_verification, ask_account_id, clarify_intent, call_get_billing_summary, handoff_to_human。説明文、理由、JSON、箇条書きは出さず、許可値の文字列だけを出力する。', '__dspy_field_type': 'output', 'prefix': 'Next Action:'})\n)"
  }
]
```

## プロンプト履歴への参照

- インデックス: `outputs/prompts/prompt_index.json`
- 現在採用中: `outputs/prompts/current.json`
- ベースライン実行: `outputs/prompts/prompt_runs/20260620-215349-baseline`
- 最良実行: `outputs/prompts/prompt_runs/20260620-215349-gepa`
- 直近実行: `outputs/prompts/prompt_runs/20260620-215349-gepa`

## プロンプト差分の読み方

ベースラインから追加された主な差分は、`BootstrapFewShot` が選んだ few-shot 例です。基本指示文は大きく変わっていないため、今回のスコア差は「指示文の言い換え」よりも「判断例の追加」による影響が大きいと考えるのが自然です。

## ベースラインと最良プロンプトの差分

```diff
--- 20260620-215349-baseline/prompt.md
+++ 20260620-215349-gepa/prompt.md
@@ -4,3 +4,19 @@
 必要な情報が不足している場合は、一度に聞きすぎず、次に必要な情報を尋ねます。
 自動確認できない場合、または顧客が希望した場合は有人対応へ引き継ぎます。
 応答は簡潔な日本語にします。
+
+## Optimizer
+
+GEPA
+
+## Predictor artifacts
+
+[
+  {
+    "demo_count": 0,
+    "instruction": "# Task Overview\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\n\n# Operational Guidelines & Logic Flow\n\n## 1. Priority of Decision Making\nWhen determining the action, prioritize information in the following order:\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\n\n## 2. Strict Guardrails (Must-Not Actions)\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\n\n## 3. Specific Action Selection Logic\n- **Intent Resolution:** If the customer's intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\n- **Slot Filling & Progression:** \n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\n- **Ambiguity:** Only use `clarify_intent` if the user's request is truly vague and no clear intent can be mapped to business rules or tools.\n\n# Summary of Required Slots for Billing Inquiries\nTo resolve billing issues, you must ensure the following are collected/verified:\n1. `account_id`\n2. `identity_verification` (Status: Verified)\n\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.",
+    "predictor_index": 0,
+    "predictor_type": "Predict",
+    "signature": "StringSignature(conversation_state, business_rules, customer_utterance -> next_action\n    instructions='# Task Overview\\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\\n\\n# Operational Guidelines & Logic Flow\\n\\n## 1. Priority of Decision Making\\nWhen determining the action, prioritize information in the following order:\\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\\n\\n## 2. Strict Guardrails (Must-Not Actions)\\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \\n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\\n\\n## 3. Specific Action Selection Logic\\n- **Intent Resolution:** If the customer\\'s intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\\n- **Slot Filling & Progression:** \\n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\\n- **Ambiguity:** Only use `clarify_intent` if the user\\'s request is truly vague and no clear intent can be mapped to business rules or tools.\\n\\n# Summary of Required Slots for Billing Inquiries\\nTo resolve billing issues, you must ensure the following are collected/verified:\\n1. `account_id`\\n2. `identity_verification` (Status: Verified)\\n\\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.'\n    conversation_state = Field(annotation=str required=True json_schema_extra={'desc': 'intent、slots、last_agent_action、利用可能ツールを含む現在の会話状態。', '__dspy_field_type': 'input', 'prefix': 'Conversation State:'})\n    business_rules = Field(annotation=str required=True json_schema_extra={'desc': '本人確認、ツール実行可否、有人引き継ぎに関する業務ルール。', '__dspy_field_type': 'input', 'prefix': 'Business Rules:'})\n    customer_utterance = Field(annotation=str required=True json_schema_extra={'desc': '日本語の最新の顧客発話。', '__dspy_field_type': 'input', 'prefix': 'Customer Utterance:'})\n    next_action = Field(annotation=str required=True json_schema_extra={'desc': '次に行う処理を1つだけ出力する。許可値: ask_identity_verification, ask_account_id, clarify_intent, call_get_billing_summary, handoff_to_human。説明文、理由、JSON、箇条書きは出さず、許可値の文字列だけを出力する。', '__dspy_field_type': 'output', 'prefix': 'Next Action:'})\n)"
+  }
+]
```

## ベースラインと直近プロンプトの差分

```diff
--- 20260620-215349-baseline/prompt.md
+++ 20260620-215349-gepa/prompt.md
@@ -4,3 +4,19 @@
 必要な情報が不足している場合は、一度に聞きすぎず、次に必要な情報を尋ねます。
 自動確認できない場合、または顧客が希望した場合は有人対応へ引き継ぎます。
 応答は簡潔な日本語にします。
+
+## Optimizer
+
+GEPA
+
+## Predictor artifacts
+
+[
+  {
+    "demo_count": 0,
+    "instruction": "# Task Overview\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\n\n# Operational Guidelines & Logic Flow\n\n## 1. Priority of Decision Making\nWhen determining the action, prioritize information in the following order:\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\n\n## 2. Strict Guardrails (Must-Not Actions)\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\n\n## 3. Specific Action Selection Logic\n- **Intent Resolution:** If the customer's intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\n- **Slot Filling & Progression:** \n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\n- **Ambiguity:** Only use `clarify_intent` if the user's request is truly vague and no clear intent can be mapped to business rules or tools.\n\n# Summary of Required Slots for Billing Inquiries\nTo resolve billing issues, you must ensure the following are collected/verified:\n1. `account_id`\n2. `identity_verification` (Status: Verified)\n\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.",
+    "predictor_index": 0,
+    "predictor_type": "Predict",
+    "signature": "StringSignature(conversation_state, business_rules, customer_utterance -> next_action\n    instructions='# Task Overview\\nYou are tasked with selecting the single most appropriate `next_action` based on the current `conversation_state`, `business_rules`, and the latest `customer_utterance`. Your goal is to drive the conversation toward a resolution while strictly adhering to security and business constraints.\\n\\n# Operational Guidelines & Logic Flow\\n\\n## 1. Priority of Decision Making\\nWhen determining the action, prioritize information in the following order:\\n1. **Business Rules:** These are absolute constraints (e.g., security requirements).\\n2. **Conversation State (`slots` & `last_agent_action`):** Use this to determine what has already been collected and what was just asked.\\n3. **Customer Utterance:** Identify the intent and any newly provided information (slot filling).\\n\\n## 2. Strict Guardrails (Must-Not Actions)\\n- **Identity Verification First:** Do NOT select an action that discloses billing details, contract information, or billing amounts before identity verification is complete.\\n- **Tool Execution Prerequisites:** Only execute tools (e.g., `get_billing_summary`) if ALL required parameters are present in the `slots` AND the necessary business conditions (like identity verification) are met. \\n    - *Example:* To call `get_billing_summary`, both `account_id` and `identity_verification` must be confirmed/present.\\n\\n## 3. Specific Action Selection Logic\\n- **Intent Resolution:** If the customer\\'s intent is clearly expressed (e.g., \"Please check my billing\"), do not use `clarify_intent`. Instead, move directly to the first missing requirement for that intent (e.g., `ask_identity_verification`).\\n- **Slot Filling & Progression:** \\n    - If a required piece of information is provided in the `customer_utterance`, update your internal state and proceed to the *next* logical step rather than repeating a request for information already given.\\n    - If the agent previously asked for identity verification (`last_agent_action: ask_identity_verification`) and the user provides the necessary info (like an account ID), proceed immediately to the tool execution or the next required slot, provided all prerequisites are met.\\n- **Human Handoff:** Select `handoff_to_human` immediately if the customer explicitly requests a human agent.\\n- **Ambiguity:** Only use `clarify_intent` if the user\\'s request is truly vague and no clear intent can be mapped to business rules or tools.\\n\\n# Summary of Required Slots for Billing Inquiries\\nTo resolve billing issues, you must ensure the following are collected/verified:\\n1. `account_id`\\n2. `identity_verification` (Status: Verified)\\n\\nDo not skip these steps; however, do not redundantly ask for them if they are already present in the conversation state or provided in the current utterance.'\n    conversation_state = Field(annotation=str required=True json_schema_extra={'desc': 'intent、slots、last_agent_action、利用可能ツールを含む現在の会話状態。', '__dspy_field_type': 'input', 'prefix': 'Conversation State:'})\n    business_rules = Field(annotation=str required=True json_schema_extra={'desc': '本人確認、ツール実行可否、有人引き継ぎに関する業務ルール。', '__dspy_field_type': 'input', 'prefix': 'Business Rules:'})\n    customer_utterance = Field(annotation=str required=True json_schema_extra={'desc': '日本語の最新の顧客発話。', '__dspy_field_type': 'input', 'prefix': 'Customer Utterance:'})\n    next_action = Field(annotation=str required=True json_schema_extra={'desc': '次に行う処理を1つだけ出力する。許可値: ask_identity_verification, ask_account_id, clarify_intent, call_get_billing_summary, handoff_to_human。説明文、理由、JSON、箇条書きは出さず、許可値の文字列だけを出力する。', '__dspy_field_type': 'output', 'prefix': 'Next Action:'})\n)"
+  }
+]
```

## DSPy に詳しくない人向けの説明

DSPy は、LLM に渡す入力と期待する出力を `Signature` として定義し、その定義を使う `Module` を評価しながら、プロンプトや few-shot 例を改善するためのフレームワークです。

通常の手書きプロンプト調整では、人がプロンプトを書き換えて結果を見比べます。DSPy では、評価データ、評価指標、最適化対象を明示し、optimizer が候補となる few-shot 例や指示を選びます。今回の検証では `NextActionPlanner` の `next_action` が正解ラベルと一致するかを指標にしました。

主な用語の役割は次のとおりです。`Signature` は入力と出力の契約、`Module` はその契約を使う処理単位、`Predict` は LLM 呼び出し、`Optimizer` は評価指標に基づいてプロンプトや例を選ぶ仕組み、`Metric` は予測が正しいかを判定する関数です。

今回 DSPy が最適化したのは、請求問い合わせで次に取るべき行動を選ぶ `NextActionPlanner` の few-shot 例です。評価では、固定済み dev データの各ターンについて、予測された `next_action` が期待値と完全一致するかを確認しました。

Amazon Connect AI Agents の本番プロンプト設計に対しては、本人確認前の情報開示禁止、ツール呼び出し条件、有人引き継ぎ条件のような運用ルールを、会話状態と期待アクションに分解して評価できることが示唆です。ただし、今回のデータは小規模な合成データであり、スコア改善をそのまま本番品質とは見なせません。本番投入前には、業務担当者によるラベル確認、禁止応答のレビュー、実会話に近いテストデータでの再評価が必要です。

## Amazon Connect 本番プロンプトへ移植する示唆

1. 本人確認前の禁止事項を、抽象的な注意書きではなく「請求額、請求明細、契約情報を開示しない」のように具体化する。
2. `account_id` と本人確認がそろった状態を、ツール呼び出しの前提条件として明示する。
3. 顧客が有人対応を希望した場合は、追加説得ではなく `handoff_to_human` に進む条件として明示する。
4. 初回の請求問い合わせを `clarify_intent` に倒しすぎると解決が遅くなるため、請求意図が十分に読める表現は本人確認へ進める。
5. few-shot 例は、顧客発話だけでなく会話状態とセットで管理する。特に「本人確認前」「account_id 取得後」「不満表明後」の状態差を分ける。

## リスクと次の確認事項

- dev データが 6 turns と少ないため、100% というスコアは過大評価の可能性があります。
- 合成データ由来の表現に偏っている可能性があるため、実運用に近い問い合わせ文で test 評価を追加する必要があります。
- 現在の評価は `next_action` の完全一致だけを見ており、実際の自然文応答の品質や禁止情報の混入までは直接評価していません。
- 本人確認の定義は検証用に単純化されています。本番では認証方式、照合項目、失敗時の扱いを業務ルールとして明確にする必要があります。
- `BootstrapFewShot` の選んだ例は有効そうに見えますが、業務担当者が内容をレビューし、不適切な例や過剰適合しそうな例を除外する工程が必要です。

## 次に実施すること

1. `test_billing_support.jsonl` に対して、ベースラインと最適化後プロンプトを同じ条件で評価する。
2. `next_action` だけでなく、実際のエージェント応答文に禁止情報が含まれないかを評価する。
3. 請求以外の問い合わせが混ざったケースで、`clarify_intent` と請求フローへの誘導が過不足なく働くか確認する。
4. 本番プロンプトへ移す前に、few-shot 例を業務用語と Amazon Connect の実ツール名に合わせて整形する。
