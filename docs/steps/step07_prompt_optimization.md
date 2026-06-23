# Step 7: DSPy によるプロンプト最適化

## 目的

Step 6 で固定した `train` / `dev` データを使い、DSPy optimizer で `NextActionPlanner` を最適化する。

最初の最適化対象は `NextActionPlanner` に限定する。これは、Amazon Connect AI Agents 風の検証では「次に何をするか」の判断が、本人確認、ツール呼び出し、有人引き継ぎの安全性に直結するため。

利用できる optimizer は以下。

- `BootstrapFewShot`: few-shot 例の選択
- `MIPROv2`: instruction 候補と few-shot 候補の探索
- `GEPA`: feedback metric と reflection LM による instruction 改善

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
        optimizer_artifacts.json
      <timestamp>-mipro-v2/
        prompt.md
        metadata.json
        eval_summary.json
        fewshot_examples.jsonl
        optimizer_artifacts.json
      <timestamp>-gepa/
        prompt.md
        metadata.json
        eval_summary.json
        optimizer_artifacts.json
    optimizer_logs/
      <timestamp>-mipro-v2/
      <timestamp>-gepa/
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

引数なしの場合は既存互換の `BootstrapFewShot` を実行する。optimizer を明示する場合は以下。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer bootstrap
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer mipro
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer all
```

GEPA の metric call 上限を変えて検証する場合は、`--gepa-max-metric-calls` を指定する。

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step07_prompt_optimization.py --optimizer gepa --gepa-max-metric-calls 72
```

Step 7 は Ollama 経由で DSPy の推論を実行するため、事前に Ollama サーバと対象モデルが利用可能である必要がある。

MIPROv2 を実行する場合は、DSPy の任意依存である `optuna` が必要。

```bash
.venv/bin/pip install optuna
```

このステップでは OpenAI 互換 API ではなく、LiteLLM の `ollama_chat/gemma4:12b` provider を使う。理由は、Ollama の `think: false` が native chat API では有効だが、OpenAI 互換 API 経由では reasoning が `content` ではなく `reasoning` 側に出続け、DSPy の構造化出力パースに失敗するため。

`NextActionPlanner` は `next_action` の短いラベルだけを出すタスクなので、Step 7 の `max_tokens` は `64` にしている。入力コンテキスト長を制限する目的ではなく、モデルの出力を短く止めるための設定。

GEPA を実行する場合、通常推論の task model は `ollama_chat/gemma4:12b`、reflection LM は `ollama_chat/gemma4:31b` を使う。事前に以下を確認する。

```bash
ollama pull gemma4:31b
ollama list
```

GEPA は `gemma4:31b` で失敗例を分析するため、`BootstrapFewShot` や `MIPROv2` より実行時間が長くなる。初期実行確認では `auto="light"` ではなく `max_metric_calls=36` に制限している。`auto="light"` はこの小規模データでも数百回の metric call になるため、ローカル検証では重すぎる。

追加検証では、`max_metric_calls=36` の GEPA が 4/6 だったため、`max_metric_calls=72` に拡大した。結果は `20260620-215349-gepa` で 6/6、100% に到達した。実測では 845.9 秒、102,942 tokens、83 LM calls を使用した。内訳は task model `ollama_chat/gemma4:12b` が 90,703 tokens / 78 calls、reflection LM `ollama_chat/gemma4:31b` が 12,239 tokens / 5 calls。
