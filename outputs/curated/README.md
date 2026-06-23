# Curated Outputs

このディレクトリには、Git 管理するレビュー済み成果物だけを置く。

## 対象

- `prompts/`: 現在採用中の prompt run を示すポインタと比較用インデックス
- `reports/`: 人が読むために整えた比較レポートと最新サマリー
- `production/`: DSPy 最適化結果を本番ランタイム用に適用したプロンプト

## 対象外

以下は `outputs/curated/` に置かず、Git 管理しない。

- optimizer の raw run
- optimizer logs
- タイムスタンプ付きの一時 report
- 実行ごとに値が変わる検証途中の成果物
