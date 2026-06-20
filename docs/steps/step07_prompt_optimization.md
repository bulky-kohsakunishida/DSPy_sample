# Step 7: DSPy によるプロンプトチューニング

## 目的

Step 6 で固定した `train` / `dev` データを使い、DSPy optimizer で `NextActionPlanner` の few-shot 例を最適化する。

最初の最適化対象は `NextActionPlanner` に限定する。これは、Amazon Connect AI Agents 風の検証では「次に何をするか」の判断が、本人確認、ツール呼び出し、有人引き継ぎの安全性に直結するため。

## 対象コード

- `examples/steps/step07_prompt_optimization.py`
- `src/connect_agent_eval/optimize.py`
- `src/connect_agent_eval/signatures.py`

## 入力

```text
data/
  scenarios/
    train_billing_support.jsonl
    dev_billing_support.jsonl
  prompts/
    baseline_system_prompt.md
```

## 出力

```text
outputs/
  prompts/
    current.json
    prompt_index.json
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

## 評価方法

各 turn を `NextActionPlanner` の1サンプルとして扱う。

入力:

- `conversation_state`
- `business_rules`
- `customer_utterance`

出力:

- `next_action`

評価では、予測した `next_action` が固定データの `expected_next_action` と一致した場合に正解とする。

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py
```

Step 7 は Ollama 経由で DSPy の推論を実行するため、事前に Ollama サーバと対象モデルが利用可能である必要がある。

このステップでは OpenAI 互換 API ではなく、LiteLLM の `ollama_chat/gemma4:12b` provider を使う。理由は、Ollama の `think: false` が native chat API では有効だが、OpenAI 互換 API 経由では reasoning が `content` ではなく `reasoning` 側に出続け、DSPy の構造化出力パースに失敗するため。

`NextActionPlanner` は `next_action` の短いラベルだけを出すタスクなので、Step 7 の `max_tokens` は `64` にしている。入力コンテキスト長を制限する目的ではなく、モデルの出力を短く止めるための設定。
