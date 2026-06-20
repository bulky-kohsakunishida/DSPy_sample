# Step 1: Ollama / DSPy 接続確認

## 目的

DSPy から Ollama の OpenAI 互換 API 経由で `gemma4:12b` を呼び出せることを確認する。

## 対象コード

- `examples/steps/step01_connection_check.py`
- 互換用: `scripts/check_step1.py`

## 実行方法

```bash
PYTHONPATH=src .venv/bin/python examples/steps/step01_connection_check.py
```

## 確認すること

- Ollama が起動している
- `gemma4:12b` が利用可能
- DSPy からモデルを呼び出せる
- `intent`、`required_slots`、`response`、`escalate` の形式で出力できる

## このステップでまだ扱わないこと

- 業務シナリオ
- 会話状態
- 評価データセット
- DSPy optimizer
