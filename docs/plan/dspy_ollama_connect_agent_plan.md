# DSPy + Ollama gemma4:12b による Amazon Connect AI Agents 向け検証計画

作成日: 2026-06-20

## 目的

DSPy と Ollama の `gemma4:12b` を使い、Amazon Connect AI Agents のようなマルチターン会話エージェントを想定したプロンプト最適化の動作検証を行う。

この検証では、Amazon Connect へ直接接続する前段として、ローカル環境で以下を確認する。

- マルチターン会話における意図判定
- 必要情報の聞き返し
- 会話状態の保持
- 業務ルールに沿った応答
- ツール/API 呼び出し判断
- 有人エスカレーション判断
- DSPy optimizer によるプロンプト改善
- 改善前後の評価比較

## 前提

- 実行環境: Mac mini M4 Pro / 64GB メモリ
- 推論サーバ: Ollama
- モデル: `gemma4:12b`
- DSPy からは Ollama の OpenAI 互換 API を利用する
- 検証対象業務は、まず請求問い合わせに限定する

## 方針

最初から本番相当のエージェントを作らず、最小構成から段階的に拡張する。

1. Ollama + DSPy の疎通確認
2. 単発応答のプロンプト検証
3. マルチターン会話状態の導入
4. Amazon Connect AI Agents 風の業務シナリオ導入
5. 合成データによる評価データセットと候補プロンプトの生成
6. 評価データセットのレビューと固定化
7. DSPy optimizer によるプロンプト最適化
8. 改善前後の比較レポート作成

## ステップ 1: 環境確認

Ollama にモデルを用意し、ローカルで実行できることを確認する。

```bash
ollama pull gemma4:12b
ollama run gemma4:12b
ollama list
```

DSPy からは以下のように接続する想定。

```python
import dspy

lm = dspy.LM(
    "openai/gemma4:12b",
    api_base="http://localhost:11434/v1",
    api_key="ollama",
)

dspy.configure(lm=lm)
```

確認項目:

- Ollama サーバが起動している
- `gemma4:12b` が `ollama list` に表示される
- DSPy から単発プロンプトを実行できる
- JSON 形式の応答を安定して返せる

## ステップ 2: 最小 DSPy サンプル

最初の DSPy 実装では、顧客発話を単発入力として扱う。

入力:

- 顧客発話

出力:

- `intent`
- `required_slots`
- `response`
- `escalate`

想定 intent:

- `billing_issue`
- `delivery_status`
- `cancel_request`
- `technical_support`
- `human_handoff`
- `unknown`

確認項目:

- DSPy `Signature` で入出力を定義できる
- `dspy.Module` で基本的な推論を実行できる
- 構造化出力が破綻しにくい
- 不明な問い合わせを `unknown` または確認質問に倒せる

## ステップ 3: 会話状態の導入

次にマルチターン会話を扱うための状態を導入する。

状態の例:

```json
{
  "intent": "billing_issue",
  "slots": {
    "customer_name": null,
    "account_id": null,
    "issue_month": null
  },
  "history": [],
  "last_agent_action": "ask_account_id",
  "handoff_required": false
}
```

各ターンで LLM に渡す情報:

- 直近のユーザー発話
- 要約済み会話状態
- 必須スロット
- 業務ルール
- 利用可能ツール
- 前回のエージェント応答

設計上の注意:

- 会話履歴には最終応答のみを保存する
- 内部推論や分析文を履歴に混ぜない
- 全履歴を無制限に渡さず、必要に応じて状態要約を使う
- 本人確認前に機微情報を開示しない

## ステップ 4: 請求問い合わせシナリオ

最初の業務シナリオは請求問い合わせにする。

シナリオ概要:

顧客が「今月の請求が高い」と問い合わせる。エージェントは本人確認に必要な情報を集め、請求明細確認ツールを呼び、原因を説明し、必要なら有人対応へ渡す。

モックツール:

- `lookup_customer(account_id)`
- `get_billing_summary(account_id, month)`
- `create_case(account_id, reason)`
- `handoff_to_human(summary)`

確認項目:

- 本人確認前に請求詳細を出さない
- 不足スロットを適切に聞き返す
- 必要なタイミングでモックツール呼び出しを選択する
- ツール結果を会話状態に反映できる
- エスカレーション条件を守れる

## ステップ 5: 合成データ生成

評価データセットと候補プロンプトは、まず合成データとして生成する。

生成対象:

- 請求問い合わせの会話シナリオ
- 顧客ペルソナ
- 顧客発話のバリエーション
- 期待される next action
- 必須スロット
- 禁止事項
- エスカレーション条件
- ベースライン用システムプロンプト
- モジュール別候補プロンプト
- few-shot 候補例

合成データ生成の入力条件:

- 業務ルール
- 本人確認ポリシー
- 請求問い合わせの代表パターン
- 利用可能なモックツール
- エスカレーション条件
- 応答トーン
- 個人情報を含めない制約

生成するシナリオ分類:

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

合成データ生成時の制約:

- 実在する個人情報、電話番号、住所、アカウント ID を使わない
- 架空データであることが分かる ID 体系を使う
- 正解ラベルと評価基準を同時に生成する
- 生成データをそのまま採用せず、後続ステップでレビューする
- 評価用データと optimizer 用データを分ける

生成ファイル例:

```text
data/
  synthetic/
    generated_scenarios.jsonl
    generated_prompts.json
    generated_fewshot_examples.jsonl
    generation_manifest.json
```

`generation_manifest.json` には以下を記録する。

- 生成日時
- 生成に使ったモデル
- 生成プロンプト
- 生成件数
- 採用件数
- 除外件数
- 除外理由
- データ分割方針

## ステップ 6: 評価データセットのレビューと固定化

最初は 20 から 50 件程度の評価データを作成する。

合成生成したデータを確認し、検証に使うデータセットとして固定化する。

データ例:

```json
{
  "scenario_id": "billing_001",
  "turns": [
    {
      "role": "user",
      "content": "今月の請求が高いんだけど"
    },
    {
      "role": "agent_expected",
      "content": "本人確認のため、登録電話番号またはアカウントIDを確認する"
    }
  ],
  "expected": {
    "intent": "billing_issue",
    "next_action": "ask_identity_verification",
    "must_not": [
      "請求情報を本人確認前に開示する"
    ]
  }
}
```

評価軸:

- 意図分類が正しい
- 必要情報を一度に聞きすぎない
- 本人確認前に機微情報を出さない
- 会話状態を失わない
- 不明点は確認する
- ツール呼び出し条件が正しい
- 有人エスカレーション判断が妥当
- 応答がコンタクトセンター向けに簡潔

レビュー観点:

- 正解ラベルが業務ルールと一致している
- 本人確認前に開示してはいけない情報が明示されている
- 評価観点が一問一答ではなくマルチターン会話を見ている
- optimizer 用データと最終評価用データが混在していない
- 同じ表現ばかりに偏っていない
- 不自然な合成データを除外している

固定化後のファイル例:

```text
data/
  scenarios/
    train_billing_support.jsonl
    dev_billing_support.jsonl
    test_billing_support.jsonl
  prompts/
    baseline_system_prompt.md
    candidate_prompts.json
```

データ分割:

- `train`: DSPy optimizer に使う
- `dev`: チューニング中の比較に使う
- `test`: 最終評価にだけ使う

## ステップ 7: DSPy によるプロンプト最適化

最初は以下の順に試す。

1. 合成生成したベースラインプロンプトを人手で確認する
2. ベースラインプロンプトで初回評価する
3. `BootstrapFewShot` による few-shot 例の最適化
4. 必要に応じて `MIPROv2` による instruction と examples の最適化
5. チューニングごとのプロンプトを履歴として保存する
6. 同じ評価セットで改善前後を比較

最適化対象候補:

- `IntentClassifier`
- `SlotTracker`
- `NextActionPlanner`
- `AgentResponseGenerator`
- `ConversationEvaluator`

最初の最適化対象は `NextActionPlanner` に限定する。Amazon Connect AI Agents のプロンプト最適化に近い価値が出やすく、他モジュールより評価しやすいため。

### プロンプト履歴管理

ステップ 7 で生成または採用したプロンプトは、毎回スナップショットとして保存する。過去のプロンプトを後から確認し、評価結果と紐付けて比較できるようにする。

保存対象:

- ベースラインプロンプト
- 合成生成した候補プロンプト
- DSPy optimizer が採用した instruction
- DSPy optimizer が採用した few-shot examples
- 手動修正したプロンプト
- 評価スコア
- 使用した train/dev/test データセット
- 使用した optimizer とパラメータ
- 使用したモデル、温度、max tokens などの推論設定

保存形式:

```text
outputs/
  prompts/
    prompt_index.json
    prompt_runs/
      20260620-153000-baseline/
        prompt.md
        metadata.json
        eval_summary.json
      20260620-160000-bootstrap-fewshot/
        prompt.md
        fewshot_examples.jsonl
        metadata.json
        eval_summary.json
      20260620-163000-mipro-v2/
        prompt.md
        fewshot_examples.jsonl
        metadata.json
        eval_summary.json
```

`prompt_index.json` には以下を記録する。

- `prompt_id`
- `created_at`
- `source`: `baseline` / `synthetic` / `bootstrap_fewshot` / `mipro_v2` / `manual`
- `target_module`
- `parent_prompt_id`
- `dataset_split`
- `score`
- `notes`
- `path`

履歴管理のルール:

- プロンプトは上書きしない
- 手動修正した場合も別の `prompt_id` として保存する
- optimizer の出力は、採用しなかった候補も必要に応じて `rejected` として残す
- 最終採用プロンプトは `outputs/curated/prompts/current.json` から参照できるようにする
- 比較レポートでは、最低でもベースライン、最良プロンプト、直近プロンプトを比較する

## ステップ 8: 比較レポート

検証結果として以下を出力する。

- モデル名
- 推論サーバ
- DSPy optimizer
- 評価件数
- ベースラインスコア
- チューニング後スコア
- 改善したケース
- 悪化したケース
- 失敗例
- 最適化されたプロンプト
- プロンプト履歴への参照
- ベースライン、最良、直近プロンプトの差分
- DSPy に詳しくない人向けの説明
- Amazon Connect 本番プロンプトへ移植できる示唆

DSPy に詳しくない人向けの説明には、以下を含める。

- DSPy は何をするためのフレームワークか
- 通常の手書きプロンプト調整と DSPy による最適化の違い
- `Signature`、`Module`、`Predict`、`Optimizer`、`Metric` の役割
- 今回の検証でどの部分を DSPy が最適化したのか
- optimizer が生成したプロンプトをどう評価したのか
- スコア改善が Amazon Connect AI Agents のプロンプト設計にどう関係するのか
- DSPy の結果をそのまま本番投入せず、人手レビューする必要がある理由

説明の粒度:

- DSPy の内部実装詳細には踏み込みすぎない
- Amazon Connect やコンタクトセンター運用の観点から意味が分かる説明にする
- 図なしでも理解できるように、入力、処理、出力の流れを文章で示す
- 用語は初出時に短く説明する

## 推奨ディレクトリ構成

```text
DSPy_sample/
  pyproject.toml
  README.md
  examples/
    steps/
      step01_connection_check.py
      step02_single_turn_agent.py
      step03_multi_turn_agent.py
  src/
    connect_agent_eval/
      __init__.py
      settings.py
      lm.py
      signatures.py
      modules.py
      tools.py
      synthesize.py
      simulator.py
      evaluators.py
      optimize.py
      run_demo.py
  data/
    synthetic/
      generated_scenarios.jsonl
      generated_prompts.json
      generated_fewshot_examples.jsonl
      generation_manifest.json
    scenarios/
      train_billing_support.jsonl
      dev_billing_support.jsonl
      test_billing_support.jsonl
    knowledge/
      billing_policy.md
    prompts/
      baseline_system_prompt.md
      candidate_prompts.json
  docs/
    plan/
      dspy_ollama_connect_agent_plan.md
    steps/
      step01_connection_check.md
      step02_single_turn_agent.md
      step03_multi_turn_agent.md
  outputs/
    runs/
    optimized/
    prompts/
      current.json
      prompt_index.json
      prompt_runs/
```

## 初回マイルストーン

まずは以下を完了条件にする。

- `gemma4:12b` への DSPy 疎通
- 請求問い合わせ 1 シナリオ
- 3 から 5 ターンの会話シミュレーション
- 意図、スロット、次アクションの JSON 出力
- 簡易評価スコア
- ベースライン結果の保存

## 完了条件

初期検証は以下を満たしたら完了とする。

- `python -m connect_agent_eval.run_demo` で会話シミュレーションを実行できる
- ベースラインと最適化後のスコアを比較できる
- 評価データ、実行結果、最適化結果がファイルとして残る
- Amazon Connect AI Agents の本番プロンプト設計に使える改善点を説明できる
