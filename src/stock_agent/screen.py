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


def save_screen(df: pd.DataFrame, out_path: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
