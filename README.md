# stock — 底値回復企業調査エージェント

底に落ちた企業を探し、**回復能力があるか**を定量・開示資料で見極め、安い局面の購入と回復後の売却を検討するための調査リポジトリです。

> 本リポジトリの出力は投資判断の材料であり、売買推奨や利益保証ではありません。

## このエージェントに期待すること

1. 株投資の調査
2. 底値企業の発掘 → 回復力評価 → 安値購入・回復売却の戦略整理
3. 判断の戦略案とアドバイス
4. 決算・公開資料からのデータ抽出と定量判断
5. 世の中の動向から大きなセグメントを選ぶトップダウン調査

詳細な運用指針: [`AGENTS.md`](AGENTS.md) / 戦略: [`docs/strategy.md`](docs/strategy.md)

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 使い方

```bash
# テーマ一覧（トップダウン）
python -m stock_agent segment --list-themes

# ユニバースから底値候補スクリーニング
python -m stock_agent screen \
  --universe examples/universe_us.csv \
  --min-drawdown 0.35 \
  --out data/screens/us-screen.csv

# 個別銘柄の定量分析
python -m stock_agent analyze --ticker INTC

# 開示（SEC）定量抽出
python -m stock_agent filings --ticker INTC

# セグメント起点の候補抽出
python -m stock_agent segment \
  --theme semiconductors \
  --universe examples/universe_us.csv \
  --out data/screens/semi.csv

# 調査レポート下書き
python -m stock_agent report --ticker INTC --out reports/
```

日本株はティッカー末尾に `.T`（例: `8035.T`）。

## リポジトリ構成

```
AGENTS.md                 # エージェント運用ルール
docs/strategy.md          # 底値回復戦略
docs/workflow.md          # 調査手順
src/stock_agent/          # スクリーナー・スコア・開示抽出・レポート
examples/                 # サンプルユニバース
reports/                  # 調査メモ出力先
tests/                    # 単体テスト
```

## 判断の要約

| 判定 | 意味 |
|------|------|
| 候補（要開示確認） | 定量は通過。開示精読後にエントリー検討 |
| 監視リスト | 条件付きで追う。決算/キャッシュ確認が先 |
| 様子見 | 材料不足 or リスク残。急がない |
| 見送り | 底でも回復仮説が弱い、または生存リスク |
