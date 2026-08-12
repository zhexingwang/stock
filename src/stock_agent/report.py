from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stock_agent.data import fetch_fundamentals, fetch_price_metrics
from stock_agent.filings import extract_quantitative_facts
from stock_agent.scoring import score_recovery


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _num(value: float | None, prefix: str = "") -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1_000_000_000:
        return f"{prefix}{value/1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{prefix}{value/1_000_000:.2f}M"
    return f"{prefix}{value:,.2f}"


def build_advice(score_total: float, verdict: str, drawdown: float | None) -> list[str]:
    advice = [
        "最終売買判断は人間が行う。以下は調査仮説に基づくアクション案。",
    ]
    if verdict == "見送り":
        advice.append("現時点ではエントリー非推奨。ドローダウン要因が構造的でないか再確認。")
        advice.append("監視条件: 流動比率改善、FCF黒字化、またはガイダンス上方修正。")
    elif verdict == "様子見":
        advice.append("即時買いより、次回決算とキャッシュフローの確認を優先。")
        advice.append("仮エントリーするなら小さく、カタリスト日付を区切る。")
    else:
        advice.append("監視リスト〜候補。開示精読後に分割エントリーを検討。")
        if drawdown is not None:
            recovery_30 = abs(drawdown) * 0.30
            recovery_60 = abs(drawdown) * 0.60
            advice.append(
                f"利確目安案: 下落幅の約30%戻し（+{recovery_30:.0%}相当）で部分、"
                f"約60%戻し（+{recovery_60:.0%}相当）で再評価。"
            )
        advice.append("損切り/撤退: 追加希薄化、流動性危機、主力事業の構造的シェア喪失が確認された場合。")
    if score_total >= 70:
        advice.append("定量スコアは高め。競合比較とカタリストの確度確認が次のボトルネック。")
    return advice


def generate_report(ticker: str) -> str:
    price = fetch_price_metrics(ticker)
    fund = fetch_fundamentals(ticker)
    score = score_recovery(price, fund)
    filings = extract_quantitative_facts(ticker)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    advice = build_advice(score.total, score.verdict, price.drawdown_52w)
    rationale = "\n".join(f"- {r}" for r in score.rationale) or "- （なし）"
    flags = ", ".join(score.flags) if score.flags else "なし"
    components = "\n".join(f"- {k}: {v:.1f}" for k, v in score.components.items())

    filing_md = []
    for snip in filings:
        filing_md.append(
            f"### {snip.title}\n"
            f"- 出典: {snip.source}\n"
            f"- フォーム: {snip.form or 'n/a'} / 提出: {snip.filed_at or 'n/a'}\n"
            f"- URL: {snip.url or 'n/a'}\n\n"
            f"{snip.excerpt}\n"
        )

    name = fund.short_name or ticker.upper()
    report = f"""# {name}（{ticker.upper()}）底値回復調査メモ

- 作成: {now}
- データソース: Yahoo Finance / SEC EDGAR（取得可能な範囲）
- 判定: **{score.verdict}**（回復スコア {score.total}/100）

## 1. 結論サマリ

- セクター/業種: {fund.sector or 'n/a'} / {fund.industry or 'n/a'}
- 株価: {_num(price.last_price)} {price.currency or ''}
- 52週ドローダウン: {_pct(price.drawdown_52w)} / 2年: {_pct(price.drawdown_2y)}
- 定量フラグ: {flags}

{rationale}

## 2. 戦略仮説

- 仮説A（ボトムアップ）: 価格下落が一時的サイクルやコスト要因で、財務耐久力があればマージン/需要正常化で平均回帰し得る。
- 仮説B（否定）: シェア喪失・負債過大・現金燃焼が主因なら、安値は「安く見えるだけ」で回復しない。
- 次に検証すべきカタリスト: 四半期ガイダンス、FCF、在庫/稼働率、セグメント需要、希薄化有無。

## 3. 定量データ

| 指標 | 値 |
|------|----|
| 最終価格 | {_num(price.last_price)} |
| 52週高値/安値 | {_num(price.high_52w)} / {_num(price.low_52w)} |
| 6ヶ月リターン | {_pct(price.return_6m)} |
| 1年リターン | {_pct(price.return_1y)} |
| 時価総額 | {_num(fund.market_cap)} |
| EV/Sales | {_num(fund.ev_to_sales)} |
| EV/EBITDA | {_num(fund.ev_to_ebitda)} |
| Trailing P/E | {_num(fund.pe_trailing)} |
| P/B | {_num(fund.pb)} |
| 流動比率 | {_num(fund.current_ratio)} |
| D/E | {_num(fund.debt_to_equity)} |
| 営業利益率 | {_pct(fund.operating_margin)} |
| 粗利率 | {_pct(fund.gross_margin)} |
| FCF | {_num(fund.free_cash_flow)} |
| 現金 | {_num(fund.total_cash)} |
| 有利子負債 | {_num(fund.total_debt)} |
| 売上成長 | {_pct(fund.revenue_growth)} |
| 利益成長 | {_pct(fund.earnings_growth)} |

### スコア内訳

{components}

## 4. 開示資料からの抽出

{("".join(filing_md) if filing_md else "抽出結果なし。")}

## 5. シナリオ

| シナリオ | 条件イメージ | 含意 |
|----------|--------------|------|
| ベース | 需要またはマージンが緩やかに改善 | 部分的な価格正常化を期待し、分割利確 |
| 強気 | ガイダンス上方 + FCF拡大 | ドローダウンの過半戻しも視野 |
| 弱気 | 追加負債/希薄化、需要の構造悪化 | 撤退。底値買い仮説を破棄 |

## 6. アクション案

{chr(10).join(f"- {a}" for a in advice)}

## 7. 未確認事項

- 同業他社との相対バリュエーション比較
- セグメント別売上・利益の詳細
- 直近IR説明会のマネジメントコメント精読
- 株主構成・短期需給（空売り、転換社債など）

---
*本レポートは情報整理であり、特定銘柄の売買を推奨するものではない。*
"""
    return report


def write_report(ticker: str, out_dir: str) -> Path:
    md = generate_report(ticker)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(out_dir) / f"{day}-{ticker.upper().replace('.', '_')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    return path
