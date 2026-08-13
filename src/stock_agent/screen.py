from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_agent.data import fetch_batch, load_universe
from stock_agent.models import ScreenRow
from stock_agent.scoring import score_recovery


def screen_universe(
    universe_path: str,
    min_drawdown: float = 0.35,
    min_score: float = 45.0,
    sector: str | None = None,
) -> pd.DataFrame:
    tickers = load_universe(universe_path)
    rows: list[ScreenRow] = []

    for price, fund in fetch_batch(tickers):
        dd = price.drawdown_52w
        if dd is None or dd > -abs(min_drawdown):
            continue
        if sector and (fund.sector or "").lower() != sector.lower():
            continue

        score = score_recovery(price, fund)
        if score.total < min_score:
            continue

        rows.append(
            ScreenRow(
                ticker=price.ticker,
                short_name=fund.short_name,
                sector=fund.sector,
                last_price=price.last_price,
                drawdown_52w=price.drawdown_52w,
                return_6m=price.return_6m,
                market_cap=fund.market_cap,
                current_ratio=fund.current_ratio,
                debt_to_equity=fund.debt_to_equity,
                free_cash_flow=fund.free_cash_flow,
                operating_margin=fund.operating_margin,
                recovery_score=score.total,
                verdict=score.verdict,
            )
        )

    df = pd.DataFrame([r.__dict__ for r in rows])
    if df.empty:
        return df
    return df.sort_values(["recovery_score", "drawdown_52w"], ascending=[False, True]).reset_index(drop=True)


def profile_universe(universe_path: str) -> pd.DataFrame:
    """フィルタなしでユニバース全銘柄の定量と回復スコアを返す。"""
    from stock_agent.scoring import classify_recovery_stage

    tickers = load_universe(universe_path)
    rows: list[dict] = []
    for price, fund in fetch_batch(tickers):
        score = score_recovery(price, fund)
        rows.append(
            {
                "ticker": price.ticker,
                "short_name": fund.short_name,
                "sector": fund.sector,
                "industry": fund.industry,
                "last_price": price.last_price,
                "currency": price.currency,
                "drawdown_52w": price.drawdown_52w,
                "drawdown_2y": price.drawdown_2y,
                "return_6m": price.return_6m,
                "return_1y": price.return_1y,
                "high_52w": price.high_52w,
                "low_52w": price.low_52w,
                "market_cap": fund.market_cap,
                "current_ratio": fund.current_ratio,
                "debt_to_equity": fund.debt_to_equity,
                "free_cash_flow": fund.free_cash_flow,
                "operating_margin": fund.operating_margin,
                "gross_margin": fund.gross_margin,
                "profit_margin": fund.profit_margin,
                "ev_to_sales": fund.ev_to_sales,
                "ev_to_ebitda": fund.ev_to_ebitda,
                "pe_trailing": fund.pe_trailing,
                "pe_forward": fund.pe_forward,
                "pb": fund.pb,
                "revenue_growth": fund.revenue_growth,
                "earnings_growth": fund.earnings_growth,
                "total_cash": fund.total_cash,
                "total_debt": fund.total_debt,
                "recovery_score": score.total,
                "verdict": score.verdict,
                "flags": "|".join(score.flags),
                "stage": classify_recovery_stage(price.drawdown_52w, price.return_6m),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["recovery_score", "drawdown_52w"], ascending=[False, True]).reset_index(drop=True)


def save_screen(df: pd.DataFrame, out_path: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
