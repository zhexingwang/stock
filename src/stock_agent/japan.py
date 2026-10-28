from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from stock_agent.data import load_universe_meta
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
        "賃金とインバウンドは下支え候補だが、原油高は小売マージンの逆風。"
        "株価が深いだけでは足りず、利益率とFCFが落ちていないかを先に見る。"
    ),
    "semicon": (
        "10月のAI関連調整でドローダウンが深まった銘柄が増えた。"
        "倍率（EV/EBITDA、P/B）がまだ高ければ、底値圏でも『安い』とは扱わない。"
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
    "6762.T": (
        "8月は調整後リバウンドで見送りだったが、今回は底値圏かつ監視リスト。"
        "EV/EBITDAとPERが、同じように売られた電子部品・装置より低い。"
        "TTMのFCFは赤字だが、年次FCFは2024年3月期から2026年3月期まで黒字。"
        "確認するのは直近四半期の運転資本であり、通期の構造赤字ではない。"
        "短信でその切り分けができるまでサイズは小さくする。"
    ),
    "4568.T": (
        "底値圏の監視は継続。売上成長は残る一方、FCF赤字は8月から解消していない。"
        "ヘルスケアのパイプライン調整であり、内需回復テーマとは別。"
        "流動性は厚く、即時の生存懸念は小さい。エントリーはFCF改善の確認後。"
    ),
    "8267.T": (
        "ユニバースで最も深いドローダウン。EV/EBITDAは高くない。"
        "ただし8月以降に株価がさらに落ち、営業利益率は薄く、TTMのFCFは赤字。"
        "2月期の年次FCFは直近まで黒字なので、通期のキャッシュ創出は残っている。障害は期中の悪化と高負債。"
        "定量スコアの上昇は事業改善ではなく下落が深まった結果。"
        "境界例: 監視は続けるが、新規の買い増しは見送り寄り。増資や利払い負担の悪化が出たら撤退。"
    ),
    "4519.T": (
        "利益率・キャッシュはユニバース屈指で、下落は続くが生存懸念は小さい。"
        "EV/Salesは高く、底値の割安ではない。サイズを上げる優先度はTDKと第一三共の次。"
    ),
    "5803.T": (
        "AI・配線テーマの往復で底値圏に入った。営業利益率は高い。"
        "P/BとEV/EBITDAはまだ高く、1年リターンもプラス圏。"
        "『売られた高値株』であり、割安な底値ではない。受注が崩れていなければ押し目候補、崩れていれば見送り。"
    ),
    "6146.T": (
        "半導体装置の調整で底値圏。マージンは極めて高いが、EV/SalesとP/Bも高い。"
        "質のある調整として様子見。安いという理由では買わない。"
    ),
    "7011.T": (
        "FCFは厚く、高値圏から底値圏まで戻した。防衛・インフラの需要仮説は残る。"
        "PERはまだ高く、売上成長の勢いは弱い。モメンタム剥落の様子見。"
    ),
    "6981.T": (
        "財務は厚いままだが、6ヶ月リターンが大きくリバウンド途中。"
        "ドローダウンは8月より深い。エントリーは6ヶ月リターンが一服してから。"
    ),
    "8035.T": (
        "2026-09-29に株式分割（Yahoo Finance上は5分割）。株価の絶対水準は8月と比較しない。"
        "分割調整後の位置はリバウンド途中。FCFはプラスでネットキャッシュだが、倍率は高い。"
    ),
    "7201.T": (
        "定量スコアは監視リストまで上がったが、これはドローダウンが深まったため。"
        "FCFの大幅赤字と高負債が続き、P/Bの低さはディストレスの表れ。"
        "底だがキャッチ・オブ・フォーリング・ナイフ。見送り。"
    ),
    "4755.T": (
        "底値圏に入ったが、レバレッジが高くFCFは赤字。"
        "底値回復ではなくバランスシート再建。見送り。"
    ),
    "9984.T": (
        "リバウンド途中から底値圏へ落ちた。流動性・営業赤字・負債が重く、スコアは低い。"
        "価格が底でも回復仮説を置かない。見送り。"
    ),
    "8801.T": (
        "8月の底値圏から株価は戻り、今回は調整扱いで優先度を下げる。"
        "負債は重く、金利が下がるパスが見えるまで様子見。"
    ),
}

# 結論で明示する優先順。定量スコア順ではなく、回復仮説が置けるかで並べる。
PRIORITY = [
    ("6762.T", "新規の監視筆頭", "底値圏。電子部品の調整銘柄のなかでは倍率が高すぎない。年次FCFは黒字で、TTM赤字の中身が条件。"),
    ("4568.T", "監視継続", "底値圏のまま。ヘルスケア枠。FCF改善前にサイズを上げない。"),
    ("8267.T", "監視継続・新規は見送り寄り", "最も深い下落。8月より利益の質が悪化し、スコア上昇をエントリー理由にしない。"),
    ("4519.T", "様子見", "事業の質は高いがEV/Salesは高い。"),
    ("5803.T", "様子見", "底値圏に入ったが高倍率のテーマ株。割安ではない。"),
    ("6146.T", "様子見", "高マージンの装置株。倍率は高く、様子見。"),
    ("7011.T", "様子見", "FCFは厚いがPERは高い。底値圏入りはモメンタム剥落。"),
    ("6981.T", "押し目待ち", "リバウンド途中。財務の厚さだけで今は買わない。"),
    ("7201.T", "見送り", "フォーリングナイフ。定量の監視リストは採用しない。"),
    ("4755.T", "見送り", "フォーリングナイフ。高負債とFCF赤字。"),
    ("9984.T", "見送り", "底値圏でも生存と利益の質が不足。"),
]


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


def jst_today() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")


def jst_now_label() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M JST")


def comparable_price_change(
    old: float | None,
    new: float | None,
    return_6m_new: float | None,
) -> tuple[float | None, bool]:
    """株価変化率と、分割などで絶対水準が比較できない疑い。"""
    if old is None or new is None or pd.isna(old) or pd.isna(new) or float(old) == 0:
        return None, False
    change = float(new) / float(old) - 1.0
    six_m = None if return_6m_new is None or pd.isna(return_6m_new) else float(return_6m_new)
    split_suspect = change < -0.45 and (six_m is None or six_m > -0.25)
    return change, split_suspect


def find_previous_profile(screen_dir: str, day: str) -> tuple[pd.DataFrame | None, str | None]:
    paths = sorted(Path(screen_dir).glob("jp-profile-*.csv"))
    older: list[Path] = []
    for path in paths:
        stamp = path.stem.replace("jp-profile-", "")
        if stamp < day:
            older.append(path)
    if not older:
        return None, None
    path = older[-1]
    return pd.read_csv(path), path.name


def build_update_section(current: pd.DataFrame, previous: pd.DataFrame, previous_name: str) -> str:
    prev = previous.copy()
    if "name_ja" not in prev.columns:
        prev["name_ja"] = prev.get("short_name", prev["ticker"])
    merged = current.merge(prev, on="ticker", suffixes=("_new", "_old"))
    lines = [
        f"比較元: `{previous_name}` と今回の全件プロファイル。",
        "株価が45%超下落しているのに6ヶ月リターンがそこまで崩れていない銘柄は、分割などで絶対価格を比較しない。",
        "",
        "| ticker | 銘柄 | 株価変化 | DD52w 前回→今回 | ステージ | スコア | 判定 |",
        "|--------|------|----------|-----------------|----------|--------|------|",
    ]
    rows = []
    for _, row in merged.iterrows():
        change, split_suspect = comparable_price_change(
            row.get("last_price_old"),
            row.get("last_price_new"),
            row.get("return_6m_new"),
        )
        stage_changed = row.get("stage_old") != row.get("stage_new")
        verdict_changed = row.get("verdict_old") != row.get("verdict_new")
        dd_old = row.get("drawdown_52w_old")
        dd_new = row.get("drawdown_52w_new")
        dd_jump = (
            dd_old is not None
            and dd_new is not None
            and not pd.isna(dd_old)
            and not pd.isna(dd_new)
            and abs(float(dd_new) - float(dd_old)) >= 0.05
        )
        if not (stage_changed or verdict_changed or dd_jump or split_suspect):
            continue
        if split_suspect:
            px = "比較不能（分割の可能性）"
        else:
            px = _pct(change)
        name = row.get("name_ja_new") or row.get("name_ja_old") or row["ticker"]
        score_old = row.get("recovery_score_old")
        score_new = row.get("recovery_score_new")
        rows.append(
            (
                float(dd_new) if dd_new is not None and not pd.isna(dd_new) else 0,
                f"| {row['ticker']} | {name} | {px} | {_pct(dd_old)} → {_pct(dd_new)} | "
                f"{row.get('stage_old')} → {row.get('stage_new')} | "
                f"{_num(score_old, 1)} → {_num(score_new, 1)} | "
                f"{row.get('verdict_old')} → {row.get('verdict_new')} |",
            )
        )
    if not rows:
        return "\n".join(lines + ["変化の大きい銘柄はなし"])
    rows.sort(key=lambda item: item[0])
    lines.extend(line for _, line in rows)
    return "\n".join(lines)


def _priority_table(profile: pd.DataFrame) -> str:
    by_ticker = {row["ticker"]: row for _, row in profile.iterrows()}
    lines = [
        "| 扱い | 銘柄 | ステージ | DD52w | スコア | 定量判定 | 理由 |",
        "|------|------|----------|-------|--------|----------|------|",
    ]
    for ticker, label, reason in PRIORITY:
        row = by_ticker.get(ticker)
        if row is None:
            continue
        name = row.get("name_ja") or ticker
        lines.append(
            f"| {label} | {name}（{ticker}） | {row.get('stage')} | {_pct(row.get('drawdown_52w'))} | "
            f"{_num(row.get('recovery_score'), 1)} | {row.get('verdict')} | {reason} |"
        )
    return "\n".join(lines)


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
            snap[key] = {"symbol": symbol, "last": None, "return_1y": None, "drawdown_52w": None, "as_of": None}
            continue
        close = hist["Close"].dropna()
        if close.empty:
            snap[key] = {"symbol": symbol, "last": None, "return_1y": None, "drawdown_52w": None, "as_of": None}
            continue
        last = float(close.iloc[-1])
        peak = float(close.tail(252).max())
        year_ago = float(close.iloc[0])
        as_of = str(close.index[-1])[:10]
        snap[key] = {
            "symbol": symbol,
            "last": last,
            "as_of": as_of,
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


def generate_japan_report(
    universe_path: str,
    profile: pd.DataFrame,
    previous: pd.DataFrame | None = None,
    previous_name: str | None = None,
) -> str:
    now = jst_now_label()
    day = jst_today()
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

    known = set(profile["ticker"])
    deep_tickers = [ticker for ticker, _, _ in PRIORITY if ticker in known]

    deep_sections = []
    for ticker in deep_tickers:
        row = profile.loc[profile["ticker"] == ticker].iloc[0]
        trend = extract_jp_financial_trend(ticker)
        deep_sections.append(build_name_section(row, trend))

    if previous is not None and previous_name:
        update_md = build_update_section(profile, previous, previous_name)
    else:
        update_md = "前回プロファイルがないため、差分表はなし。"

    n225_dd_val = n225.get("drawdown_52w")
    if n225_dd_val is None or pd.isna(n225_dd_val):
        market_state = "指数位置は未取得"
    elif n225_dd_val > -0.08:
        market_state = "高値圏"
    elif n225_dd_val > -0.20:
        market_state = "高値からの調整局面であり、指数自体は底値圏ではない"
    else:
        market_state = "指数の下落が深く、市場全体も底値の議論に入る"

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
    n225_asof = n225.get("as_of") or "n/a"
    fx_last = _num(fx.get("last"), 2)
    fx_asof = fx.get("as_of") or "n/a"
    topix_last = _num(topix.get("last"), 1)
    topix_dd = _pct(topix.get("drawdown_52w"))
    topix_asof = topix.get("as_of") or "n/a"
    priority_md = _priority_table(profile)

    report = f"""# 日本国内 底値回復レポート（{day}）

- 作成: {now}
- 前回: `reports/2026-08-13-japan-domestic.md`（価格は2026-08-13前後）
- 対象: 東証ユニバース {len(profile)} 銘柄（`examples/universe_jp.csv`）
- データ: Yahoo Finance（価格・財務）。指数 `^N225` / `1306.T` / `USDJPY=X`
- 開示: 日本株はSEC対象外のため、有報相当の年次PL/CFをYahoo経由で抽出。一次資料はEDINET・株探リンク
- 本資料は調査メモであり、売買推奨ではない

## 1. 結論サマリ

- 市場は**{market_state}**。
- 日経平均 {n225_last} 円（履歴最終日 {n225_asof}、52週DD {n225_dd}、1年 {n225_1y}）。8月13日調査時は約68,700円、52週DD約-5%。
- ドル円 {fx_last}（履歴最終日 {fx_asof}）。8月調査時は約159円。
- TOPIX連動ETF（1306） {topix_last} 円（履歴最終日 {topix_asof}、52週DD {topix_dd}）。日経平均より調整は浅く、下落は半導体比率の高い日経平均に寄っている。
- ユニバース内の底値圏: {len(bottom)} 銘柄（8月は4銘柄）。監視リスト以上: {len(watch)} 銘柄。高値圏: {len(skip_high)} 銘柄。
- スコアが上がった銘柄の多くは、事業が良くなったのではなく**下落が深まった**ため。定量の監視リストを、そのまま買い候補にしない。

優先順位は回復仮説が置けるかで並べる。スコア順ではない。

{priority_md}

**今回のスタンス**

1. 指数の調整は底値回復の本丸ではない。メガバンクと高値圏の商社は対象外のまま。
2. 新規の監視筆頭は **TDK**。底値圏で、同じ調整の電子部品・装置より倍率が高すぎない。年次FCFは黒字で、赤字なのはTTM。直近四半期の中身が確認できるまでサイズは小さくする。
3. **第一三共**は8月からの監視を継続。**イオン**は最も深いが、利益率とFCFが悪化しており、8月の「本命」からは一段下げる。
4. フジクラ、ディスコ、三菱重工、村田はドローダウンが深まった。事業の質は残るが倍率は高く、割安な底値とは扱わない。
5. 日産・楽天・ソフトバンクGは底値圏でもフォーリングナイフ。日産の定量判定が監視リストでも、定性では見送り。
6. 三井不動産は底値圏から外れ、優先度を下げる。

## 1b. 前回（2026-08-13）からの変化

{update_md}

確認できたコーポレートアクション: 東京エレクトロン（8035）は2026-09-29に5分割、三井住友FG（8316）は同日に2分割（Yahoo Financeの分割履歴）。これらの株価絶対値は8月と比較しない。

## 2. トップダウン（世の中の動向 → セグメント）

出典:

- 価格・財務: Yahoo Finance（取得 {now}）
- 東京市場 2026-10-28: [OANDA 東京マーケットダイジェスト](https://www.oanda.jp/lab-education/market_news/mn_1041019_202610281539/) — 日経平均終値 63,954円、ドル円 157.82円、TOPIX 3,991.71、新発10年国債利回り 2.825%。円安けん制の発言
- 2026-10-19〜23の週次: [chartmemo 週間マーケットまとめ 10月第4週](https://chartmemo.com/weekly-43.html) — 日経平均は10/22に約3か月ぶり63,000円割れ、10/23終値 62,693円。日本9月コアCPIは前年比+2.1%。WTIは100ドル超の局面。日銀は10/30会合で政策金利1.25%据え置きとの観測（報道ベースの仮説。結果は本レポート作成時点では未確定）
- 前回ベースライン: `reports/2026-08-13-japan-domestic.md`

| 動向 | 8月調査時 | 今回 | この戦略での扱い |
|------|-----------|------|------------------|
| 日経平均 | 約68,700円、52週DD約-5%の高値圏 | 履歴終値は62,000円台、52週高値からは約-13%。10/28終値は63,954円まで戻した | 指数買いは引き続き対象外。個別の調整だけを見る |
| AI・半導体 | 指数を牽引し、多くはリバウンド途中 | 10/22に調整が入り、フジクラ・ディスコなどが底値圏へ | 倍率が高いままなら様子見。TDKのように倍率が落ちたものだけ監視を上げる |
| 原油 | 8月上旬はWTI 80ドル台 | 10月下旬に100ドル超 | イオンなど薄利内需のマージン逆風が強い |
| ドル円 | 約159円 | 約158円。円安けん制あり | 輸出採算の大逆転ではなく、小幅な円高。輸入コストはまだ重い |
| 日銀 | 利上げ前倒し観測 | 10/30は1.25%据え置き観測が優勢。10年債利回りは2.8%台 | 不動産の即時ショックは8月より弱いが、高負債を買う理由にはならない |
| 銀行・資源 | 物色の主役で高値圏 | 銀行は高値圏のまま。郵船・ENEOSは高値圏側 | モメンタム追いはしない |

### セグメント仮説の優先順位

1. **半導体・電子のうち倍率が落ちた銘柄** — 今回の新規枠。代表はTDK。フジクラとディスコは質があってもまだ高い
2. **ヘルスケア** — 第一三共を監視継続。中外は質が高く、割安ではない
3. **内需** — イオンは深いが質が悪化。他の小売・交通の多くは高値圏のまま
4. **重工** — 三菱重工はFCFが厚く底値圏。倍率確認が先で、様子見
5. **自動車のディストレス、金融の高値** — 日産は見送り。銀行は対象外

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

全件CSV: `data/screens/jp-profile-{day}.csv`

## 4. セグメント別マップ

{chr(10).join(segment_blocks)}

## 5. 重点銘柄の開示・定量

{chr(10).join(deep_sections) if deep_sections else "重点抽出なし"}

## 6. シナリオとアクション

| シナリオ | 条件 | 日本ポートフォリオへの含意 |
|----------|------|----------------------------|
| ベース | 日銀は据え置き、原油高は残る。半導体は決算でもみ合う | TDKと第一三共を小さく監視。高倍率のフジクラ・ディスコは急がない。イオンは短信待ち |
| 強気 | 原油が落ち着き、AI投資の回収不安が後退。FCFが改善 | TDK・第一三共の下落幅の約30%戻しで部分利確を検討。高倍率株は倍率低下が続いてから |
| 弱気 | 日銀が据え置き予想に反して利上げ、原油高が続き、AI調整が再燃 | イオン・日産・楽天・ソフトバンクGは撤退。倍率の高い調整株も買わない |

### エントリー条件（日本専用）

- ステージが底値圏
- 定量スコアだけでなく、EV/EBITDAかPERが同業の高値株より低い
- 流動比率 ≥ 1.0。FCF赤字なら、赤字の理由が在庫・投資であると短信で読める
- 高レバレッジかつ営業利益率が低い銘柄は、スコアが監視リストでも見送り
- 一括買いせず、10/30の日銀結果と次回決算のあとで分割

### 売却条件

- 利確: 下落幅の約30%戻しで半分、約60%戻しで残りを再評価
- 撤退: 増資、格下げ、主力事業の減損、FCF赤字の拡大
- 時間: 2四半期連続で売上もマージンも改善しないなら仮説破棄

### やらないこと

- 日経平均・TOPIXそのものの調整を「底」とみなして指数を買うこと
- メガバンク、高値圏の商社・海運のモメンタム追随
- 日産・楽天・ソフトバンクGを、P/Bやドローダウンの深さだけで買うこと
- フジクラやディスコを、ドローダウンが大きいという理由だけで割安扱いすること

## 7. 未確認事項

- 10/29のFOMC結果と10/30の日銀決定（作成時点では未開催）
- TDKのFCF赤字が在庫・設備投資か、構造的な悪化か（短信・有報）
- フジクラとディスコの受注残。倍率が高止まりなら見送り継続
- イオンの直近四半期で営業利益率とFCFが落ちた要因（原油、値引き、投資）
- 第一三共のパイプラインとFCF赤字の持続期間
- EDINETの有報XBRL一次パース（APIキーなしでは一覧取得が不安定）
- 空売り残高、自社株買い枠の消化

---
*情報整理であり、特定銘柄の売買を推奨するものではない。円建て・日本居住者向けの調査メモ。2026-08-13レポートの更新版。*
"""
    return report


def write_japan_report(universe_path: str, out_dir: str, screen_dir: str) -> dict[str, Path]:
    day = jst_today()
    previous, previous_name = find_previous_profile(screen_dir, day)
    profile = profile_universe(universe_path)
    profile = attach_universe_meta(profile, universe_path)
    screen_path = Path(screen_dir) / f"jp-profile-{day}.csv"
    save_screen(profile, str(screen_path))
    md = generate_japan_report(
        universe_path,
        profile,
        previous=previous,
        previous_name=previous_name,
    )
    report_path = Path(out_dir) / f"{day}-japan-domestic.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    return {"report": report_path, "profile": screen_path}
