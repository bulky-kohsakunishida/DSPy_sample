# DSPy プロンプト最適化 学習ガイド

## この資料の目的

この資料は、DSPy や optimizer をまだ使ったことがない技術者が、このプロジェクトの目的、実装の流れ、評価方法、プロンプト最適化の考え方を理解するための学習教材です。

対象読者は、Python と LLM API の基本は知っているが、DSPy の `Signature`、`Module`、`Metric`、`Optimizer` にはまだ慣れていない技術者を想定します。

このプロジェクトでは、Amazon Connect AI Agents のような請求問い合わせ対応を題材に、ローカルの Ollama + Gemma モデルを使って「次に取るべき行動」を選ぶエージェント部品を検証します。最終的な目的は、感覚的なプロンプト修正ではなく、評価データと metric に基づいてプロンプトを改善できる状態を作ることです。

## このプロジェクトで作っているもの

検証対象は、請求問い合わせにおける `NextActionPlanner` です。これは、顧客の最新発話と会話状態を受け取り、次に取るべき action を1つ選ぶ部品です。

代表的な action は次のとおりです。

| action | 意味 |
|---|---|
| `ask_identity_verification` | 本人確認に必要な情報を依頼する |
| `ask_account_id` | 請求確認に必要な account_id を依頼する |
| `call_get_billing_summary` | 本人確認と account_id がそろった状態で請求サマリー取得ツールを呼ぶ |
| `clarify_intent` | 問い合わせ意図が曖昧なため確認する |
| `handoff_to_human` | 有人対応へ引き継ぐ |

この部品が重要なのは、請求額や契約情報のような機微情報を扱う前に、本人確認や必要情報の収集ができているかを判断するからです。自然文応答の流暢さよりも、業務ルールに沿った action 選択の正確さを重視しています。

## なぜ DSPy を使うのか

通常のプロンプト改善では、人がプロンプトを書き換え、実行結果を見て、また書き換えるという手作業になりがちです。この方法は始めやすい一方で、次の問題があります。

- どの変更が効いたのか分かりにくい
- 成功/失敗を人の印象で判断しやすい
- 評価データが固定されず、改善したように見えても再現しにくい
- few-shot 例を増やす基準が曖昧になりやすい

DSPy は、LLM アプリケーションを「入出力の契約」「処理モジュール」「評価指標」「optimizer」に分けて扱います。これにより、プロンプトを単なる文章ではなく、評価可能なプログラム部品として改善できます。

このプロジェクトでは、DSPy によって次の流れを作っています。

1. 入力と出力を `Signature` として定義する
2. `Module` が `Signature` を使って予測する
3. 固定した評価データで予測結果を採点する
4. optimizer が few-shot 例や instruction を探索する
5. 改善前後の結果を保存し、比較レポートで確認する

## 主要な DSPy 用語

| 用語 | このプロジェクトでの意味 |
|---|---|
| `Signature` | LLM に渡す入力と、期待する出力の定義 |
| `Module` | `Signature` を使って実際に推論する処理単位 |
| `Predict` | DSPy が LLM 呼び出しを行うための基本部品 |
| `Metric` | 予測が正しいかどうかを判定する関数 |
| `Optimizer` | metric を使って、プロンプトや few-shot 例を改善する仕組み |
| `trainset` | optimizer が改善に使うデータ |
| `devset` | optimizer 後の性能確認に使うデータ |

重要なのは、DSPy の optimizer は「よさそうなプロンプトを雰囲気で作る」ものではないという点です。評価データと metric を与え、その結果に基づいてプロンプト構成を探索します。

## Signature と Module をもう少し細かく見る

DSPy を初めて読むときに分かりにくいのは、「プロンプトのどこが `Signature` で、どこが optimizer によって変わる部分なのか」です。このプロジェクトでは、次のように分けて考えます。

| 要素 | 役割 | 変えたいか |
|---|---|---|
| `Signature` | 入力フィールド、出力フィールド、出力形式、許可値を定義する契約 | 基本的には固定する |
| `Module` | `Signature` を使って、どのように LLM 呼び出しを組み立てるかを定義する処理単位 | 処理構造を変えたいときだけ変更する |
| instruction | LLM にどう判断してほしいかを説明する自然言語の指示 | optimizer に改善させたい |
| few-shot examples | 入力と期待出力の具体例 | optimizer に選ばせたい |
| runtime input | 実行時に毎回変わる `conversation_state` や `customer_utterance` | optimizer の対象ではない |

### このプロジェクトの Signature

`NextActionPlanner` の `Signature` は [src/connect_agent_eval/signatures.py](../../src/connect_agent_eval/signatures.py) にあります。

```python
class NextActionPlanner(dspy.Signature):
    """会話状態と最新発話から、次に実行する action を1つ選ぶ。

    本人確認前に請求詳細を開示する action を選ばない。ツール実行が必要な場合も、
    account_id と本人確認済み状態がそろっていることを前提に判断する。
    """

    conversation_state: str = dspy.InputField(
        desc="intent、slots、last_agent_action、利用可能ツールを含む現在の会話状態。"
    )
    business_rules: str = dspy.InputField(
        desc="本人確認、ツール実行可否、有人引き継ぎに関する業務ルール。"
    )
    customer_utterance: str = dspy.InputField(
        desc="日本語の最新の顧客発話。"
    )
    next_action: str = dspy.OutputField(
        desc=(
            "次に行う処理を1つだけ出力する。許可値: "
            "ask_identity_verification, ask_account_id, clarify_intent, "
            "call_get_billing_summary, handoff_to_human。"
            "説明文、理由、JSON、箇条書きは出さず、許可値の文字列だけを出力する。"
        )
    )
```

この `Signature` が決めているのは、主に次の契約です。

- 入力は `conversation_state`、`business_rules`、`customer_utterance` の3つ
- 出力は `next_action` の1つ
- `next_action` は許可された action ラベルだけを返す
- 説明文、理由、JSON、箇条書きは出さない

ここはプロンプト最適化で頻繁に変える場所ではありません。たとえば optimizer が「もっと説明を出したほうがよい」と判断しても、このプロジェクトでは `next_action` だけが欲しいため、`Signature` 側で「説明文を出さない」と固定しています。

言い換えると、`Signature` は「LLM に自由に書かせないための枠」です。Amazon Connect のような業務フローに接続する場合、後段処理は `call_get_billing_summary` のような安定した内部ラベルを期待します。そのため、出力形式は optimizer に任せず固定します。

### このプロジェクトの Module

`NextActionPlannerModule` は [src/connect_agent_eval/optimize.py](../../src/connect_agent_eval/optimize.py) にあります。

```python
class NextActionPlannerModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.plan = dspy.Predict(NextActionPlanner)

    def forward(
        self,
        conversation_state: str,
        business_rules: str,
        customer_utterance: str,
    ) -> dspy.Prediction:
        return self.plan(
            conversation_state=conversation_state,
            business_rules=business_rules,
            customer_utterance=customer_utterance,
        )
```

この `Module` はかなり薄い作りです。やっていることは、`NextActionPlanner` という `Signature` を `dspy.Predict` に渡し、実行時入力をそのまま渡すだけです。

この設計にしている理由は、今回の最適化対象を `NextActionPlanner` の判断に限定したいからです。複雑な分岐や後処理を `Module` に入れすぎると、optimizer が改善しているのか、Python 側のロジックが効いているのか分かりにくくなります。

`Module` を変えたくなる例は、次のような場合です。

- まず intent を分類し、その後に action を選ぶ2段構成にしたい
- tool 呼び出しの前に追加の検証モジュールを入れたい
- `next_action` だけでなく、ユーザー向け応答文も同時に生成したい
- 複数候補を出して、別の module で選び直したい

今回の Step 7 では、こうした構造変更はしません。`Module` は固定し、optimizer には instruction や few-shot 例の改善に集中させています。

### プロンプト成果物のどこが何に対応するか

baseline のプロンプトは [data/prompts/baseline_system_prompt.md](../../data/prompts/baseline_system_prompt.md) にあります。

```text
あなたは請求問い合わせを扱うコンタクトセンターのAIエージェントです。
現在の会話状態、業務ルール、最新の顧客発話をもとに次アクションを選びます。
本人確認が済むまで請求額、請求明細、契約情報は開示しません。
必要な情報が不足している場合は、一度に聞きすぎず、次に必要な情報を尋ねます。
自動確認できない場合、または顧客が希望した場合は有人対応へ引き継ぎます。
応答は簡潔な日本語にします。
```

この文章は、人が最初に用意した基本 instruction です。ただし、DSPy の実行時にはこれだけがプロンプトになるわけではありません。DSPy は `Signature` の入力フィールド、出力フィールド、field の説明、optimizer が選んだ instruction や few-shot 例を組み合わせて、実際の LLM 入力を組み立てます。

GEPA 後の成果物 `outputs/prompts/prompt_runs/20260620-215349-gepa/prompt.md` には、次のような情報が保存されています。

```text
StringSignature(conversation_state, business_rules, customer_utterance -> next_action)
```

これは、この optimizer 後のプロンプトでも、入出力の形が次のまま維持されていることを示します。

```text
conversation_state
business_rules
customer_utterance
  -> next_action
```

一方で、GEPA が改善した instruction は、たとえば次のような内容です。

```text
If the customer's intent is clearly expressed, do not use clarify_intent.
Instead, move directly to the first missing requirement for that intent.
```

この改善は、baseline が「請求を確認したい」という明確な発話を `clarify_intent` に倒しすぎていた失敗に対応しています。つまり GEPA は、入出力契約を変えずに、「明確な請求意図なら intent 確認ではなく本人確認へ進む」という判断ルールを instruction 側に追加しました。

### 何を固定し、何を最適化するか

このプロジェクトでは、次の線引きをしています。

| 固定するもの | 理由 |
|---|---|
| 入力フィールド名 | 評価データと実行コードがこの名前で値を渡すため |
| 出力フィールド名 `next_action` | 後段の評価と業務フロー接続で参照するため |
| action の許可値 | 想定外ラベルが出ると評価やツール呼び出しが壊れるため |
| 評価 metric | optimizer ごとに採点基準が変わると比較できないため |
| train / dev split | optimizer が見たデータと評価データを分けるため |

| 最適化するもの | 理由 |
|---|---|
| few-shot examples | どの会話状態ならどの action か、具体例で判断を安定させるため |
| instruction | 曖昧な判断ルールや優先順位を明確化するため |
| GEPA の reflection 結果 | 失敗理由から「次にどう直すべきか」を自然言語で反映するため |

たとえば、次のような変更は `Signature` を変えるべき変更です。

```text
next_action だけでなく、ユーザーに返す response も評価対象にしたい
```

この場合は出力フィールドに `response` を追加する必要があります。これは optimizer の仕事ではなく、タスク定義そのものの変更です。

一方で、次のような変更は optimizer に任せたい変更です。

```text
請求意図が明確なときに clarify_intent を選びすぎるので、本人確認へ進む判断を強めたい
```

この場合、入出力の形は変えず、instruction や few-shot 例を改善すればよいです。今回 GEPA がやったのはこのタイプの改善です。

## 全体手順

このプロジェクトは、段階的に機能を増やす構成になっています。

| step | 内容 | 参照 |
|---|---|---|
| 1 | Ollama + DSPy の接続確認 | `docs/steps/step01_connection_check.md` |
| 2 | 単発応答の DSPy サンプル | `docs/steps/step02_single_turn_agent.md` |
| 3 | マルチターン会話状態の導入 | `docs/steps/step03_multi_turn_agent.md` |
| 4 | 請求問い合わせシナリオの導入 | `docs/steps/step04_billing_scenario.md` |
| 5 | 合成データ生成 | `docs/steps/step05_synthetic_data_generation.md` |
| 6 | データレビューと固定化 | `docs/steps/step06_review_and_freeze_dataset.md` |
| 7 | DSPy optimizer によるプロンプト最適化 | `docs/steps/step07_prompt_optimization.md` |
| 8 | 改善前後の比較レポート | `docs/steps/step08_comparison_report.md` |

学習目的で読む場合は、Step 1 から順番に実行するより、まず Step 6 から Step 8 を読むと、評価データ、最適化、比較の関係をつかみやすくなります。

## 評価データの考え方

プロンプト最適化では、評価データの設計が重要です。このプロジェクトでは、請求問い合わせの会話を turn 単位に分解し、それぞれに期待する `next_action` を付けています。

1件の評価サンプルは、おおむね次の情報を持ちます。

```text
conversation_state
business_rules
customer_utterance
expected_next_action
```

LLM は `conversation_state`、`business_rules`、`customer_utterance` を入力として受け取り、`next_action` を予測します。予測が `expected_next_action` と完全一致すれば正解です。

この評価方法では、自然文応答の丁寧さや言い回しは評価しません。目的は、本人確認、account_id 取得、ツール呼び出し、有人引き継ぎの判断が正しいかを測ることです。

## train / dev / test の分け方

optimizer を使う場合、データ分割を曖昧にすると評価が信用できなくなります。

このプロジェクトでは、次の役割で分けます。

| split | 役割 |
|---|---|
| `train` | optimizer が few-shot 例や instruction 改善に使う |
| `dev` | optimizer の結果を比較する |
| `test` | 今後、最終確認に使う想定 |

`train` と `dev` を分ける理由は、optimizer が見たデータだけで評価すると、過剰に適合した結果を「改善」と誤解しやすいためです。今回の dev データは小規模なので、6/6 は有用な動作確認ではありますが、本番品質の保証ではありません。

## このプロジェクトの optimizer

### baseline

baseline は optimizer を使わない初期状態です。固定の `baseline_system_prompt.md` と `NextActionPlanner` の `Signature` だけで推論します。

baseline は比較の基準です。ここで失敗したケースが、optimizer によって改善できたかを確認します。

### BootstrapFewShot

`BootstrapFewShot` は、train データから few-shot 例を選び、LLM に「この入力ならこの action」という具体例を追加する optimizer です。

この optimizer は、instruction を大きく書き換えるというより、判断例を追加して出力を安定させる動きになります。今回のように、action ラベルを正確に選ぶタスクでは効果が出やすいです。

### MIPROv2

`MIPROv2` は、few-shot 例だけでなく instruction 候補も探索する optimizer です。複数の instruction 案と few-shot セットを作り、それらの組み合わせを評価して、よりスコアが高い構成を探します。

このプロジェクトでは `auto="light"` で実行しています。探索量は BootstrapFewShot より多く、token 使用量や実行時間も大きくなります。

### GEPA

`GEPA` は、失敗例に対する feedback を使って instruction を改善する optimizer です。単に正解/不正解を見るだけでなく、「なぜ違ったか」「どのルールを優先すべきか」を reflection LM に渡し、新しい instruction 案を作ります。

このプロジェクトでは、通常の action 予測に `ollama_chat/gemma4:12b` を使い、reflection LM に `ollama_chat/gemma4:31b` を使っています。

初期検証では `max_metric_calls=36` に抑えたため 4/6 でした。その後、`max_metric_calls=72` に拡大し、6/6 に到達しました。GEPA は改善能力がある一方で、reflection LM を使うため実行時間と token 使用量が増えやすい optimizer です。

## Metric の考え方

Metric は、optimizer にとっての採点関数です。このプロジェクトでは、予測された `next_action` が正解ラベルと一致するかを見ています。

通常の metric は、次のような考え方です。

```text
expected_next_action == actual_next_action なら 1
それ以外なら 0
```

GEPA では、単なる 0/1 だけではなく、失敗理由を説明する feedback metric を使います。たとえば、期待値が `ask_identity_verification` なのに `clarify_intent` を出した場合、「請求意図は明確なので intent 確認ではなく本人確認へ進むべき」という feedback を返します。

この feedback があることで、GEPA は「どう直せばよいか」を reflection LM に考えさせられます。

## プロンプト最適化の基本的な考え方

このプロジェクトでのプロンプト最適化は、次の考え方に基づきます。

1. まず baseline を測る
2. 失敗ケースを明確にする
3. optimizer に改善候補を作らせる
4. 同じ dev データで比較する
5. score だけでなく、改善/悪化/未解決ケースを見る
6. token 使用量と実行時間も確認する
7. 最終的に人が本番移植可否を判断する

重要なのは、optimizer の結果をそのまま本番採用しないことです。optimizer は評価データ上でよい候補を探しますが、業務ルール、禁止事項、実会話のばらつき、本番ツール名との整合性は人がレビューする必要があります。

## 実行手順

### 1. baseline と optimizer を実行する

BootstrapFewShot を実行する場合:

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer bootstrap
```

MIPROv2 を実行する場合:

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer mipro
```

GEPA を実行する場合:

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa
```

GEPA の metric call 上限を増やす場合:

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa --gepa-max-metric-calls 72
```

全 optimizer をまとめて実行する場合:

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer all
```

### 2. 比較レポートを生成する

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step08_comparison_report.py
```

生成されたレポートは `outputs/reports/` に保存されます。Step 8 は保存済み JSON を読むだけなので、LLM を呼び出しません。

## 結果の読み方

比較レポートでは、次の観点を確認します。

| 観点 | 見る内容 |
|---|---|
| score | `correct / total` の比率 |
| improved | baseline では不正解、optimizer 後に正解になったケース |
| worsened | baseline では正解、optimizer 後に不正解になったケース |
| still failed | optimizer 後も不正解のケース |
| token usage | optimizer 実行にかかった入力/出力 token 数 |
| LM calls | LLM を呼び出した回数 |
| prompt diff | baseline から何が変わったか |

`6/6` は、評価対象6件すべてで `next_action` が正解したという意味です。ただし、評価件数が少ないため、本番品質を保証する数字ではありません。

## Token usage の読み方

トークン使用量は、optimizer のコスト感を理解するために重要です。

| 項目 | 意味 |
|---|---|
| `prompt_tokens` | LLM に渡した入力側の token 数 |
| `completion_tokens` | LLM が生成した出力側の token 数 |
| `total_tokens` | 入力と出力の合計 |
| `LM calls` | LLM 呼び出し回数 |
| `model breakdown` | モデル別の token / call 内訳 |

GEPA の場合、task model と reflection LM が分かれます。task model は通常の `next_action` 予測を行い、reflection LM は失敗例を分析して instruction 改善案を作ります。

## この検証から分かること

今回の検証では、baseline は請求意図が明確な発話を `clarify_intent` に倒しすぎる傾向がありました。optimizer 後は、請求問い合わせでは本人確認へ進む、account_id と本人確認がそろったら請求サマリー取得ツールを呼ぶ、という判断が改善しました。

一方で、今回の評価データは小規模です。そのため、次にやるべきことは、より実運用に近い test データで評価することです。また、`next_action` だけでなく、実際に生成する自然文応答に禁止情報が混入しないかも評価する必要があります。

## 本番移植時の注意

Amazon Connect AI Agents の本番プロンプトへ移す場合、optimizer が生成した文言をそのまま貼り付けるのではなく、次の観点で整理します。

- 本人確認前に開示してはいけない情報を明文化する
- ツール呼び出しに必要な slot を明文化する
- 有人引き継ぎ条件を明文化する
- few-shot 例を業務担当者がレビューする
- 本番の tool 名、slot 名、認証方式に合わせて書き換える
- test データで再評価する

## 学習時のおすすめの読み進め方

1. `docs/steps/step06_review_and_freeze_dataset.md` でデータ固定の意味を読む
2. `docs/steps/step07_prompt_optimization.md` で optimizer 実行の流れを読む
3. `docs/steps/step08_comparison_report.md` で比較レポートの出力内容を読む
4. `src/connect_agent_eval/optimize.py` で `Metric` と optimizer 呼び出しを見る
5. `src/connect_agent_eval/report.py` で評価結果の読み方を見る
6. `outputs/reports/` の最新レポートを読み、改善ケースと token 使用量を確認する

## まとめ

このプロジェクトの主題は、プロンプトを手作業でなんとなく調整することではありません。業務ルールを action 判断に落とし込み、評価データを固定し、metric で採点し、DSPy optimizer でプロンプトを改善し、その結果を比較レポートで検証することです。

この流れを作ることで、LLM エージェントの改善を「印象」ではなく「再現可能な評価」に近づけられます。

## 参考資料

調査日: 2026-06-21

この資料では、プロジェクト内の実装・レポートに加えて、以下の一次情報および研究資料を参考にしています。DSPy や Amazon Connect は更新が速いため、実装方針を見直す場合は最新の公式ドキュメントを再確認してください。

### DSPy

| 種別 | 資料 | 参照する理由 |
|---|---|---|
| 公式ドキュメント | [DSPy Overview](https://dspy.ai/) | DSPy の基本思想、`Signature`、`Module`、optimizer の全体像を確認する入口 |
| 公式ドキュメント | [Program, don't prompt](https://dspy.ai/getting-started/programming/) | DSPy が「プロンプト文字列」ではなく、構造化されたプログラムとして LLM 処理を扱う考え方を理解するため |
| 公式ドキュメント | [Metrics](https://dspy.ai/getting-started/metrics/) | optimizer に渡す metric の役割を理解するため |
| 公式ドキュメント | [Optimizers: choosing one](https://dspy.ai/diving-deeper/choosing-an-optimizer/) | optimizer が instruction、demo、weights のどれを調整するか、GEPA や MIPROv2 をどう選ぶかを確認するため |
| 公式ドキュメント | [BootstrapFewShot](https://dspy.ai/api/optimizers/BootstrapFewShot/) | few-shot 例を選ぶ optimizer の API とパラメータを確認するため |
| 公式ドキュメント | [MIPROv2](https://dspy.ai/api/optimizers/MIPROv2/) | instruction と few-shot の探索を行う optimizer の API とパラメータを確認するため |
| 公式ドキュメント | [GEPA](https://dspy.ai/api/optimizers/GEPA/) | reflection LM と feedback metric を使う GEPA の API とパラメータを確認するため |
| 公式チュートリアル | [GEPA optimization](https://dspy.ai/getting-started/gepa-optimization/) | GEPA の基本的な使い方と feedback を使う流れを確認するため |

### 研究資料

| 種別 | 資料 | 参照する理由 |
|---|---|---|
| 論文 | [Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs](https://arxiv.org/abs/2406.11695) | MIPRO の背景にある、instruction と demonstration を評価指標に基づいて最適化する考え方を理解するため |
| 論文 | [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457) | GEPA が自然言語 reflection を使って prompt update を提案し、少ない rollout で改善を狙う考え方を理解するため |

### Amazon Connect

| 種別 | 資料 | 参照する理由 |
|---|---|---|
| 公式ページ | [Amazon Connect Customer Features](https://aws.amazon.com/products/connect/customer/features/) | Agentic self-service、step-by-step guides、AI-powered agent assist など、Amazon Connect 側の概念と照らし合わせるため |
| 公式ドキュメント | [Amazon Connect 管理者ガイド](https://docs.aws.amazon.com/connect/latest/adminguide/) | 本番移植時に、Amazon Connect の flows、agent workspace、routing、security 設定を確認する入口 |

### このリポジトリ内の関連資料

| 資料 | 用途 |
|---|---|
| [Step 6: データレビューと固定化](../steps/step06_review_and_freeze_dataset.md) | optimizer 実行前に評価データを固定する理由を確認する |
| [Step 7: DSPy によるプロンプト最適化](../steps/step07_prompt_optimization.md) | optimizer の実行方法、MIPROv2 / GEPA の設定、実測結果を確認する |
| [Step 8: 改善前後の比較レポート](../steps/step08_comparison_report.md) | 改善結果、トークン使用量、GEPA metric call 追加検証の読み方を確認する |
| [MIPROv2 / GEPA optimizer 追加計画](../plan/dspy_mipro_gepa_optimizer_plan.md) | optimizer 追加時の設計判断と実装計画を確認する |
