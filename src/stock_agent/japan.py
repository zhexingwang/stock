from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from stock_agent.data import load_universe_meta, utc_today
from stock_agent.screen import profile_universe, save_screen

SEGMENT_LABELS = {
    "domestic": "内需・インバウンド",
    "semicon": "半導体・電子・省力化",
    "autos": "自動車",
    "healthcare": "ヘルスケア",
    "finance": "金融・不動産",
    "trading": "商社",
    "materials": "素材・重工・資源",
    "telecom": "通信",
}

SEGMENT_THESIS = {
    "domestic": (
        "実質賃金のプラス定着とインバウンドが消費・交通・小売の稼働を支える。"
        "ただし指数が高値圏のため、内需でも『まだ底値圏』の銘柄に限定する。"
    ),
    "semicon": (
        "AI・先端投資はテーマとして強い。高値更新後の調整は買い場になり得るが、"
        "バリュエーションが高く『安い』とは限らない。"
    ),
    "autos": (
        "円安は輸出採算にプラスだが、関税・中国需要・EV競争が構造リスク。"
        "財務が厚い完成車と、落ち込みが深い日産のような個別を分けて見る。"
    ),
    "healthcare": (
        "国内薬価と海外パイプラインの二層。第一三共など成長株の調整は、"
        "FCFとパイプライン進捗が回復仮説の核になる。"
    ),
    "finance": (
        "金利上昇・TOPIX最高値局面では銀行が買われやすい。"
        "底値回復戦略としては高値追いより、不動産の調整銘柄を優先する。"
    ),
    "trading": (
        "資源価格と円安の感応度が高い。指数高値圏では割安放置より循環物色になりやすい。"
    ),
    "materials": (
        "原油高・防衛・インフラは追い風になり得るが、鉄鋼は需給とマージンのサイクル銘柄。"
    ),
    "telecom": (
        "キャッシュは厚いが成長は限定的。底値仮説より株主還元と金利感応で見る。"
    ),
}

NAME_NOTES = {
    "8267.T": (
        "本命の底値候補。売上・営業利益は増えているのに株価は半値近く。"
        "論点はレバレッジ（D/E約186、有利子負債4兆円超）と薄利（営業利益率2.6%）。"
        "賃上げ・インバウンドが続けば数量は支えられるが、原油高と金利は逆風。"
        "次の確認: 有報の負債明細、GMS再編、株主還元。分割なら小さく、増資観測が出たら撤退。"
    ),
    "4568.T": (
        "売上は2年で1.60→2.12兆円と伸びているが、営業利益は直近減、FCFは2期連続赤字。"
        "成長株の調整であり、内需回復とは別物。パイプラインと研究開発費の回収時期がカタリスト。"
        "財務は流動比率2.9で生存は問題になりにくい。PER約20は極端な割安ではない。"
        "エントリーは短信でFCF改善が見えてから。"
    ),
    "4519.T": (
        "利益率・ネットキャッシュはユニバース屈指。下落はバリュエーション圧縮寄り。"
        "EV/Sales約8倍は『底値の割安』ではない。回復しても上値が限定されやすい。"
        "監視は続けるが、サイズを大きくする優先度はイオンより低い。"
    ),
    "8801.T": (
        "不動産は金利前倒し観測の直撃ゾーン。営業利益は増えているがFCFは直近赤字、負債4.6兆円。"
        "P/B 1.22は極端な割安ではない。日銀パスが見えるまで様子見が妥当。"
    ),
    "6981.T": (
        "財務は極めて厚いが、6ヶ月で+148%戻しており『安い時期』は過ぎている。"
        "電子部品サイクルの押し目待ち。52週高値からまだ-34%あるので、再下落があれば再評価。"
    ),
    "7201.T": (
        "ディストレスト。FCF大幅赤字、D/E高、営業利益率2.6%。『安い』は構造問題の可能性が高い。"
        "再編・資本政策の一次資料なしに大型化しない。ウォッチのみ。"
    ),
    "4755.T": (
        "内需テックだが負債が大きくFCF赤字。底値回復というよりバランスシート再建。"
        "戦略の本命箱からは外す。"
    ),
}


def _code(ticker: str) -> str:
    return ticker.replace(".T", "").replace(".t", "")


def jp_source_links(ticker: str) -> dict[str, str]:
    code = _code(ticker)
    return {
        "yahoo_jp": f"https://finance.yahoo.co.jp/quote/{code}.T",
        "kabutan": f"https://kabutan.jp/stock/?code={code}",
        "edinet_search": (
            "https://disclosure2.edinet-fsa.go.jp/WAF0E0010.aspx"
        ),
        "tdnet": f"https://www.release.tdnet.info/inbs/I_search_eq_{code}.html",
    }


def _series_row(df: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    lower_index = {str(i).lower(): i for i in df.index}
    for name in candidates:
        key = name.lower()
        if key in lower_index:
            return df.loc[lower_index[key]]
        for idx_l, idx in lower_index.items():
            if key in idx_l:
                return df.loc[idx]
    return None


def extract_jp_financial_trend(ticker: str, years: int = 3) -> dict:
    """有報相当の年次PL/CFをYahoo経由で抽出（日本株の代替開示ソース）。"""
    t = yf.Ticker(ticker)
    try:
        fin = t.financials
    except Exception:
        fin = pd.DataFrame()
    try:
        cf = t.cashflow
    except Exception:
        cf = pd.DataFrame()
    try:
        bs = t.balance_sheet
    except Exception:
        bs = pd.DataFrame()

    revenue = _series_row(fin, ["Total Revenue", "Operating Revenue", "Revenue"])
    opinc = _series_row(fin, ["Operating Income", "Operating Income or Loss"])
    netinc = _series_row(fin, ["Net Income", "Net Income Common Stockholders"])
    fcf = _series_row(cf, ["Free Cash Flow"])
    cash = _series_row(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    debt = _series_row(bs, ["Total Debt", "Long Term Debt"])

    def _last_n(series: pd.Series | None) -> list[dict]:
        if series is None:
            return []
        items = []
        for col in list(series.index)[:years]:
            val = series[col]
            try:
                if pd.isna(val):
                    continue
                items.append({"period": str(col)[:10], "value": float(val)})
            except (TypeError, ValueError):
                continue
        return items

    return {
        "ticker": ticker.upper(),
        "revenue": _last_n(revenue),
        "operating_income": _last_n(opinc),
        "net_income": _last_n(netinc),
        "free_cash_flow": _last_n(fcf),
        "cash": _last_n(cash),
        "total_debt": _last_n(debt),
    }


def _jpy(value: float | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    v = float(value)
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1e12:
        return f"{sign}{av/1e12:.2f}兆円"
    if av >= 1e8:
        return f"{sign}{av/1e8:.0f}億円"
    if av >= 1e4:
        return f"{sign}{av/1e4:.0f}万円"
    return f"{sign}{av:,.0f}円"


def _pct(value: float | None) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    return f"{float(value):.1%}"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _trend_line(items: list[dict], label: str) -> str:
    if not items:
        return f"- {label}: 未取得"
    parts = [f"{x['period']} {_jpy(x['value'])}" for x in items]
    return f"- {label}: " + " / ".join(parts)


def attach_universe_meta(df: pd.DataFrame, universe_path: str) -> pd.DataFrame:
    meta = {row["ticker"]: row for row in load_universe_meta(universe_path)}
    out = df.copy()
    out["name_ja"] = out["ticker"].map(lambda t: meta.get(t, {}).get("name_ja") or "")
    out["segment"] = out["ticker"].map(lambda t: meta.get(t, {}).get("segment") or "")
    out["segment_ja"] = out["segment"].map(lambda s: SEGMENT_LABELS.get(s, s or "未分類"))
    return out


def fetch_index_snapshot() -> dict[str, dict]:
    symbols = {
        "n225": "^N225",
        "topix_etf": "1306.T",
        "usdjpy": "USDJPY=X",
    }
    snap: dict[str, dict] = {}
    for key, symbol in symbols.items():
        t = yf.Ticker(symbol)
        hist = t.history(period="1y", auto_adjust=True)
        if hist.empty:
            snap[key] = {"symbol": symbol, "last": None, "return_1y": None, "drawdown_52w": None}
            continue
        close = hist["Close"]
        last = float(close.iloc[-1])
        peak = float(close.tail(252).max())
        year_ago = float(close.iloc[0])
        snap[key] = {
            "symbol": symbol,
            "last": last,
            "return_1y": (last / year_ago - 1.0) if year_ago else None,
            "drawdown_52w": (last / peak - 1.0) if peak else None,
        }
    return snap


def _md_table(df: pd.DataFrame, columns: list[str], limit: int | None = None) -> str:
    view = df[columns].copy()
    if limit:
        view = view.head(limit)
    if view.empty:
        return "該当なし"
    try:
        return view.to_markdown(index=False)
    except Exception:
        return view.to_string(index=False)


def _format_screen_row(row: pd.Series) -> str:
    name = row.get("name_ja") or row.get("short_name") or row["ticker"]
    return (
        f"| {row['ticker']} | {name} | {row.get('segment_ja','')} | "
        f"{_num(row.get('last_price'), 1)} | {_pct(row.get('drawdown_52w'))} | "
        f"{_pct(row.get('return_6m'))} | {row.get('stage','')} | "
        f"{_num(row.get('recovery_score'), 1)} | {row.get('verdict','')} |"
    )


def build_name_section(row: pd.Series, trend: dict) -> str:
    ticker = row["ticker"]
    name = row.get("name_ja") or row.get("short_name") or ticker
    links = jp_source_links(ticker)
    flags = row.get("flags") or "なし"
    if isinstance(flags, float) and pd.isna(flags):
        flags = "なし"
    note = NAME_NOTES.get(ticker, "個別仮説は開示トレンドとマクロ箱から判断。一次資料の精読が次工程。")
    return f"""### {name}（{ticker}）

- 判定: **{row.get('verdict')}** / ステージ: **{row.get('stage')}** / スコア { _num(row.get('recovery_score'), 1) }
- セグメント: {row.get('segment_ja')}（{row.get('sector') or 'n/a'} / {row.get('industry') or 'n/a'}）
- 株価: {_num(row.get('last_price'), 1)} 円 / 52週高値 {_num(row.get('high_52w'), 1)} / 安値 {_num(row.get('low_52w'), 1)}
- ドローダウン: 52週 {_pct(row.get('drawdown_52w'))} / 2年 {_pct(row.get('drawdown_2y'))}
- リターン: 6ヶ月 {_pct(row.get('return_6m'))} / 1年 {_pct(row.get('return_1y'))}
- 時価総額: {_jpy(row.get('market_cap'))}
- バリュエーション: EV/Sales {_num(row.get('ev_to_sales'))} / EV/EBITDA {_num(row.get('ev_to_ebitda'))} / P/B {_num(row.get('pb'))} / PER {_num(row.get('pe_trailing'))}
- 財務: 流動比率 {_num(row.get('current_ratio'))} / D/E {_num(row.get('debt_to_equity'))} / 営業利益率 {_pct(row.get('operating_margin'))}
- キャッシュ: FCF {_jpy(row.get('free_cash_flow'))} / 現金 {_jpy(row.get('total_cash'))} / 有利子負債 {_jpy(row.get('total_debt'))}
- 成長: 売上 {_pct(row.get('revenue_growth'))} / 利益 {_pct(row.get('earnings_growth'))}
- フラグ: {flags}

**判断メモ:** {note}

年次開示トレンド（Yahoo Finance 財務、新しい期が左）:

{_trend_line(trend.get('revenue') or [], '売上高')}
{_trend_line(trend.get('operating_income') or [], '営業利益')}
{_trend_line(trend.get('net_income') or [], '純利益')}
{_trend_line(trend.get('free_cash_flow') or [], 'FCF')}
{_trend_line(trend.get('cash') or [], '現金同等物')}
{_trend_line(trend.get('total_debt') or [], '有利子負債')}

公開資料リンク:

- [Yahoo!ファイナンス]({links['yahoo_jp']})
- [株探]({links['kabutan']})
- [EDINET検索]({links['edinet_search']})（提出者名で有報・短信を検索）
"""


def generate_japan_report(universe_path: str, profile: pd.DataFrame) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    idx = fetch_index_snapshot()
    n225 = idx.get("n225", {})
    fx = idx.get("usdjpy", {})
    topix = idx.get("topix_etf", {})

    bottom = profile[profile["stage"] == "底値圏"].copy()
    rebound = profile[profile["stage"] == "リバウンド途中"].copy()
    watch = profile[profile["verdict"].isin(["監視リスト", "候補（要開示確認）"])].copy()
    skip_high = profile[profile["stage"] == "高値圏"].copy()
    near_bottom = profile[
        (profile["drawdown_52w"] <= -0.25) & (profile["stage"] != "底値圏")
    ].copy()

    # Deep-dive: 底値圏を優先、監視リスト、ディストレスト近傍
    deep_tickers = list(bottom["ticker"].head(5))
    for t in list(watch["ticker"]) + ["7201.T", "4755.T"]:
        if t not in deep_tickers and t in set(profile["ticker"]) and len(deep_tickers) < 8:
            deep_tickers.append(t)

    deep_sections = []
    for ticker in deep_tickers:
        row = profile.loc[profile["ticker"] == ticker].iloc[0]
        trend = extract_jp_financial_trend(ticker)
        deep_sections.append(build_name_section(row, trend))

    segment_blocks = []
    for key, label in SEGMENT_LABELS.items():
        sub = profile[profile["segment"] == key]
        if sub.empty:
            continue
        thesis = SEGMENT_THESIS.get(key, "")
        top3 = sub.sort_values(["drawdown_52w", "recovery_score"], ascending=[True, False]).head(3)
        lines = [
            f"### {label}",
            "",
            thesis,
            "",
            "| ticker | 銘柄 | 株価 | DD52w | 6m | ステージ | スコア | 判定 |",
            "|--------|------|------|-------|----|----------|--------|------|",
        ]
        for _, row in sub.sort_values("drawdown_52w").iterrows():
            name = row.get("name_ja") or row["ticker"]
            lines.append(
                f"| {row['ticker']} | {name} | {_num(row.get('last_price'), 1)} | "
                f"{_pct(row.get('drawdown_52w'))} | {_pct(row.get('return_6m'))} | "
                f"{row.get('stage')} | {_num(row.get('recovery_score'), 1)} | {row.get('verdict')} |"
            )
        if not top3.empty:
            names = "、".join(
                f"{r.get('name_ja') or r['ticker']}（{_pct(r.get('drawdown_52w'))}）"
                for _, r in top3.iterrows()
            )
            lines.extend(["", f"この箱で最も売られているのは {names}。"])
        segment_blocks.append("\n".join(lines))

    def _list_md(df: pd.DataFrame) -> str:
        if df.empty:
            return "該当なし"
        header = (
            "| ticker | 銘柄 | セグメント | 株価 | DD52w | 6m | ステージ | スコア | 判定 |\n"
            "|--------|------|------------|------|-------|----|----------|--------|------|"
        )
        body = "\n".join(_format_screen_row(r) for _, r in df.iterrows())
        return header + "\n" + body

    n225_last = _num(n225.get("last"), 0)
    n225_dd = _pct(n225.get("drawdown_52w"))
    n225_1y = _pct(n225.get("return_1y"))
    fx_last = _num(fx.get("last"), 2)
    topix_dd = _pct(topix.get("drawdown_52w"))

    bottom_names = "、".join(
        f"{r.get('name_ja') or r['ticker']}" for _, r in bottom.head(5).iterrows()
    ) or "なし"
    watch_names = "、".join(
        f"{r.get('name_ja') or r['ticker']}" for _, r in watch.head(5).iterrows()
    ) or "なし"

    report = f"""# 日本国内 底値回復レポート（{utc_today()}）

- 作成: {now}
- 対象: 東証ユニバース {len(profile)} 銘柄（`examples/universe_jp.csv`）
- データ: Yahoo Finance（価格・財務）、指数 `^N225` / `1306.T` / `USDJPY=X`
- 開示: 日本株はSEC対象外のため、有報相当の年次PL/CFをYahoo経由で抽出。一次資料はEDINET・株探リンクを併記
- 本資料は調査メモであり、売買推奨ではない

## 1. 結論サマリ

- 市場全体は**高値圏**。日経平均 {n225_last} 円（52週DD {n225_dd}、1年 {n225_1y}）、ドル円 {fx_last} 円、TOPIX連動ETFの52週DD {topix_dd}。
- 2026年8月時点のマクロは、実質賃金のプラス定着・企業最高益・AI/半導体物色・銀行買いが指数を支えている。底値回復戦略は「指数を買う」ではなく、**指数高の陰で置いていかれた内需・個別ショック銘柄**を探す局面。
- ユニバース内の底値圏: {len(bottom)} 銘柄。監視リスト以上: {len(watch)} 銘柄。高値圏: {len(skip_high)} 銘柄。
- 優先監視: {watch_names}
- 価格位置が『底値圏』: {bottom_names}

優先順位（調査時点）:

| 順位 | 銘柄 | 理由 |
|------|------|------|
| 1 | イオン | 唯一、深い底＋内需マクロ追い風が重なる。ただし負債は重い |
| 2 | 第一三共 | 底値圏で財務は厚い。FCF赤字が解消するまでサイズは小さく |
| 3 | 中外製薬 | 質は高いが割安ではない。押し目の監視 |
| 4 | 三井不動産 | 金利次第。今は様子見 |
| — | 村田 | 財務は良いがリバウンド済み。押し目待ち |
| — | 日産・楽天 | ディストレスト。底値戦略の本命にしない |

**本日のスタンス（日本専用）**

1. 指数・メガバンク・商社の高値追いは戦略対象外
2. 内需でまだ沈んでいる銘柄（小売・化粧品・一部交通）を本命の箱にする
3. 半導体はテーマは正しいが、リバウンド途中が多くエントリーは押し目待ち
4. 自動車は日産など個別破綻・再編リスクと、トヨタなど高値圏を明確に分離する

## 2. トップダウン（世の中の動向 → セグメント）

出典メモ: アセットマネジメントOne「マーケットインサイト8月」(2026-08)、野村AM Market Navi (2026-08-06)、株探市況 (2026-08-12)。

| 動向 | 含意 | この戦略での扱い |
|------|------|------------------|
| 実質賃金が複数月プラス、賃上げ定着 | 内需の数量・単価が戻りやすい | **本命箱**。ただし高値の内需（オリエンタルランド等）は除外 |
| インバウンド・サービス消費 | 交通・小売・レジャーの稼働 | JR・空運・小売の底値圏だけ拾う |
| AI/半導体が指数を牽引、TOPIX最高値 | 物色が偏り、非AI内需が置いていかれる | 半導体は調整待ち。内需の相対弱さを候補にする |
| 米金利・原油高で銀行・資源が買われる | 金融は高値、コスト高は内需の逆風 | 銀行は見送り。小売のマージン悪化は精査 |
| 円は介入警戒つきの円安圏 | 輸出採算は支え、輸入コストは小売・食品の負担 | 輸出株の高値と内需のコスト高を同時に見る |
| 日銀は利上げ前倒し観測 | 成長株の割引率、不動産・高負債に逆風 | 高レバレッジ内需は生存確認を厳しく |

### セグメント仮説の優先順位

1. **内需・インバウンド** — マクロは追い風なのに株価が弱い銘柄が、戦略の中心
2. **ヘルスケア** — パイプライン調整で売られた成長株。FCF次第
3. **半導体・電子** — テーマは強いが『底』ではない銘柄が多い。押し目リスト
4. **自動車** — 個別（日産）はディストレスト。完成車大手は高値圏
5. 金融・商社 — 今は循環物色の買い側。底値回復の主戦場ではない

## 3. 定量スクリーニング（日本ユニバース全件）

価格位置の定義:

- **底値圏**: 52週高値比 -30%以下、かつ直近6ヶ月が大幅プラスではない
- **リバウンド途中**: 大きく落ちたあと6ヶ月で10%超戻している
- **高値圏**: 52週高値比 -15%より浅い → この戦略では原則見送り

### 底値圏

{_list_md(bottom)}

### 監視リスト / 候補

{_list_md(watch)}

### 底値近傍（-25%以下だがステージは底値圏未満）

{_list_md(near_bottom)}

### リバウンド途中（遅れて入ると期待値が落ちる）

{_list_md(rebound)}

全件CSV: `data/screens/jp-profile-{utc_today()}.csv`

## 4. セグメント別マップ

{chr(10).join(segment_blocks)}

## 5. 重点銘柄の開示・定量

{chr(10).join(deep_sections) if deep_sections else "重点抽出なし"}

## 6. シナリオとアクション

| シナリオ | 条件 | 日本ポートフォリオへの含意 |
|----------|------|----------------------------|
| ベース | 賃上げとインバウンドが続き、指数は高値もみ合い | 内需の底値圏を分割で監視。半導体は押し目待ち |
| 強気 | 実質賃金加速、円が緩やかに円高、原油一服 | 小売・交通のマージン回復。底値圏の30-60%戻しで利確 |
| 弱気 | 日銀の利上げ加速、原油高定着、海外需要失速 | 高負債内需と日産型ディストレストは撤退。現金厚めの電子部品へ退避 |

### エントリー条件（日本専用）

- ステージが底値圏、または監視リスト以上
- 流動比率 ≥ 1.0、かつ高レバレッジならFCFまたはネットキャッシュを確認
- 直近短信で「構造的シェア喪失」ではなく、在庫・値引き・一時費用が主因と読める
- 一括買いせず、決算翌週の押し目を1/3ずつ

### 売却条件

- 利確: 下落幅の約30%戻しで半分、約60%戻しで残りを再評価
- 撤退: 増資・格下げ・主力事業の減損が続いた場合
- 時間: 2四半期連続で売上もマージンも改善しないなら仮説破棄

### やらないこと

- 日経平均・TOPIXそのものの高値追い
- メガバンク・総合商社のモメンタム追随（今の物色の主役であり、底値戦略ではない）
- 日産のようなディストレストを「安い」だけで大型化すること

## 7. 未確認事項

- EDINETの有報XBRL一次パース（APIキーなしでは一覧取得が不安定）
- 空売り残高、自社株買い枠の消化
- イオン・セブンの再編・株主提案の一次資料精読
- 資生堂・化粧品の中国需要とインバウンドの分解
- 第一三共のパイプラインイベント・FCF赤字の持続期間

---
*情報整理であり、特定銘柄の売買を推奨するものではない。円建て・日本居住者向けの調査メモ。*
"""
    return report


def write_japan_report(universe_path: str, out_dir: str, screen_dir: str) -> dict[str, Path]:
    profile = profile_universe(universe_path)
    profile = attach_universe_meta(profile, universe_path)
    day = utc_today()
    screen_path = Path(screen_dir) / f"jp-profile-{day}.csv"
    save_screen(profile, str(screen_path))
    md = generate_japan_report(universe_path, profile)
    report_path = Path(out_dir) / f"{day}-japan-domestic.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    return {"report": report_path, "profile": screen_path}
