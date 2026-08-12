# 調査ワークフロー

## クイックスタート

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 底値スクリーニング（例: 米国大型〜中型）
python -m stock_agent screen --universe examples/universe_us.csv --min-drawdown 0.35

# 個別銘柄の定量プロファイル
python -m stock_agent analyze --ticker AAPL

# セグメント仮説から候補抽出
python -m stock_agent segment --theme semiconductors --universe examples/universe_us.csv

# レポート下書き生成
python -m stock_agent report --ticker AAPL --out reports/
```

## 推奨フロー

```
世の中の動向 / ユニバース
        │
        ├─(トップダウン)─► セグメント選定 ─► その中でドローダウン大
        │
        └─(ボトムアップ)─► ドローダウン・スクリーナー
                            │
                            ▼
                     生存・財務フィルタ
                            │
                            ▼
                   開示資料・IR 抽出
                            │
                            ▼
              回復仮説 + シナリオ + アクション案
                            │
                            ▼
                    reports/ に保存
```

## データソース

| 用途 | ソース | 備考 |
|------|--------|------|
| 価格・簡易財務 | Yahoo Finance (`yfinance`) | 速報・スクリーニング向け |
| 米国開示 | SEC EDGAR | 10-K/10-Q の定量抽出 |
| 日本株 | ティッカー末尾 `.T` | 例: `7203.T` |

取得できない項目は「未取得」と書き、推測で埋めない。

## レポート保存規則

- パス: `reports/YYYY-MM-DD-<ticker-or-theme>.md`
- 生データ: `data/raw/`（gitignore 可）
- スクリーナー結果: `data/screens/`
