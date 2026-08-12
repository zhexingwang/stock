from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_agent.data import fetch_batch, load_universe
from stock_agent.scoring import score_recovery


@dataclass(frozen=True)
class ThemeSpec:
    key: str
    title_ja: str
    thesis: str
    sectors: tuple[str, ...]
    industries_contains: tuple[str, ...]
    macro_signals: tuple[str, ...]


THEMES: dict[str, ThemeSpec] = {
    "semiconductors": ThemeSpec(
        key="semiconductors",
        title_ja="半導体サイクル",
        thesis="在庫調整後の需要戻り・AI/先端投資が装置・素材の稼働を押し上げる局面を狙う。",
        sectors=("Technology",),
        industries_contains=("Semiconductor", "Chip", "Electronics"),
        macro_signals=("設備投資計画", "在庫月数", "先端ノード需要", "輸出規制"),
    ),
    "rates_sensitive_growth": ThemeSpec(
        key="rates_sensitive_growth",
        title_ja="金利感応グロース",
        thesis="金利低下で割引率改善が期待される一方、業績が壊れすぎていない銘柄を選別する。",
        sectors=("Technology", "Communication Services", "Real Estate"),
        industries_contains=("Software", "Internet", "REIT", "Semiconductor"),
        macro_signals=("政策金利見通し", "実質金利", "信用スプレッド"),
    ),
    "energy_transition": ThemeSpec(
        key="energy_transition",
        title_ja="エネルギー・移行関連",
        thesis="化石と移行技術の双方で、マージンとキャッシュが底打ちした企業を探す。",
        sectors=("Energy", "Utilities", "Industrials"),
        industries_contains=("Oil", "Gas", "Solar", "Renewable", "Utilities"),
        macro_signals=("原油・ガス価格", "発電マージン", "補助金/規制"),
    ),
    "healthcare_demand": ThemeSpec(
        key="healthcare_demand",
        title_ja="ヘルスケア需要",
        thesis="人口動態と診療需要は安定しやすい。パイプラインや償還リスクを織り込み過ぎた銘柄を検討。",
        sectors=("Healthcare",),
        industries_contains=("Drug", "Medical", "Biotech", "Health"),
        macro_signals=("薬価・償還", "治験イベント", "病院稼働"),
    ),
    "japan_domestic": ThemeSpec(
        key="japan_domestic",
        title_ja="日本内需・インバウンド",
        thesis="賃金・観光・サービス消費の回復で、国内需要感応度の高い業種のマージン改善を狙う。",
        sectors=("Consumer Cyclical", "Consumer Defensive", "Industrials"),
        industries_contains=("Travel", "Restaurant", "Retail", "Railroads", "Lodging"),
        macro_signals=("訪日客数", "実質賃金", "円安/円高", "個人消費"),
    ),
}


def list_themes() -> list[ThemeSpec]:
    return list(THEMES.values())


def match_theme(fund_sector: str | None, fund_industry: str | None, theme: ThemeSpec) -> bool:
    sector = (fund_sector or "").lower()
    industry = (fund_industry or "").lower()
    if theme.sectors and sector and sector not in {s.lower() for s in theme.sectors}:
        # industry keyword can still match across adjacent sectors
        if not any(k.lower() in industry for k in theme.industries_contains):
            return False
    if theme.industries_contains:
        return any(k.lower() in industry for k in theme.industries_contains)
    return True


def screen_theme(
    theme_key: str,
    universe_path: str,
    min_drawdown: float = 0.30,
    min_score: float = 40.0,
) -> tuple[ThemeSpec, pd.DataFrame]:
    if theme_key not in THEMES:
        known = ", ".join(sorted(THEMES))
        raise ValueError(f"未知のテーマ: {theme_key}. 利用可能: {known}")
    theme = THEMES[theme_key]
    tickers = load_universe(universe_path)
    rows = []
    for price, fund in fetch_batch(tickers):
        if not match_theme(fund.sector, fund.industry, theme):
            continue
        dd = price.drawdown_52w
        if dd is None or dd > -abs(min_drawdown):
            continue
        score = score_recovery(price, fund)
        if score.total < min_score:
            continue
        rows.append(
            {
                "ticker": price.ticker,
                "short_name": fund.short_name,
                "sector": fund.sector,
                "industry": fund.industry,
                "drawdown_52w": price.drawdown_52w,
                "recovery_score": score.total,
                "verdict": score.verdict,
                "ev_to_sales": fund.ev_to_sales,
                "operating_margin": fund.operating_margin,
                "current_ratio": fund.current_ratio,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("recovery_score", ascending=False).reset_index(drop=True)
    return theme, df
