from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd
import yfinance as yf

from stock_agent.models import FundamentalMetrics, PriceMetrics


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_universe(path: str) -> list[str]:
    meta = load_universe_meta(path)
    return [row["ticker"] for row in meta]


def load_universe_meta(path: str) -> list[dict[str, str]]:
    df = pd.read_csv(path)
    col = "ticker" if "ticker" in df.columns else df.columns[0]
    rows: list[dict[str, str]] = []
    for _, rec in df.iterrows():
        ticker = str(rec[col]).strip().upper()
        if not ticker or ticker == "TICKER":
            continue
        rows.append(
            {
                "ticker": ticker,
                "name": str(rec["name"]).strip() if "name" in df.columns and pd.notna(rec.get("name")) else ticker,
                "name_ja": str(rec["name_ja"]).strip() if "name_ja" in df.columns and pd.notna(rec.get("name_ja")) else "",
                "segment": str(rec["segment"]).strip() if "segment" in df.columns and pd.notna(rec.get("segment")) else "",
            }
        )
    return rows


def _safe_float(value: object) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _drawdown_from_high(close: pd.Series, window: int) -> float | None:
    if close.empty:
        return None
    recent = close.tail(window)
    if recent.empty:
        return None
    peak = float(recent.max())
    last = float(recent.iloc[-1])
    if peak <= 0:
        return None
    return (last / peak) - 1.0


def _period_return(close: pd.Series, days: int) -> float | None:
    if len(close) < days + 1:
        return None
    past = float(close.iloc[-(days + 1)])
    last = float(close.iloc[-1])
    if past <= 0:
        return None
    return (last / past) - 1.0


def fetch_price_metrics(ticker: str) -> PriceMetrics:
    t = yf.Ticker(ticker)
    hist = t.history(period="2y", auto_adjust=True)
    info = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
    volume = hist["Volume"] if not hist.empty else pd.Series(dtype=float)

    high_52w = _safe_float(info.get("fiftyTwoWeekHigh"))
    low_52w = _safe_float(info.get("fiftyTwoWeekLow"))
    last = _safe_float(close.iloc[-1]) if not close.empty else _safe_float(info.get("currentPrice"))

    drawdown_52w = _drawdown_from_high(close, 252)
    if drawdown_52w is None and last is not None and high_52w:
        drawdown_52w = (last / high_52w) - 1.0

    return PriceMetrics(
        ticker=ticker.upper(),
        as_of=utc_today(),
        last_price=last,
        currency=info.get("currency"),
        drawdown_52w=drawdown_52w,
        drawdown_2y=_drawdown_from_high(close, 504),
        return_1y=_period_return(close, 252),
        return_6m=_period_return(close, 126),
        avg_volume_20d=_safe_float(volume.tail(20).mean()) if not volume.empty else None,
        high_52w=high_52w if high_52w is not None else (_safe_float(close.tail(252).max()) if not close.empty else None),
        low_52w=low_52w if low_52w is not None else (_safe_float(close.tail(252).min()) if not close.empty else None),
    )


def fetch_fundamentals(ticker: str) -> FundamentalMetrics:
    t = yf.Ticker(ticker)
    info: dict = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    return FundamentalMetrics(
        ticker=ticker.upper(),
        as_of=utc_today(),
        market_cap=_safe_float(info.get("marketCap")),
        enterprise_value=_safe_float(info.get("enterpriseValue")),
        revenue_ttm=_safe_float(info.get("totalRevenue")),
        ebitda_ttm=_safe_float(info.get("ebitda")),
        free_cash_flow=_safe_float(info.get("freeCashflow")),
        total_cash=_safe_float(info.get("totalCash")),
        total_debt=_safe_float(info.get("totalDebt")),
        current_ratio=_safe_float(info.get("currentRatio")),
        debt_to_equity=_safe_float(info.get("debtToEquity")),
        operating_margin=_safe_float(info.get("operatingMargins")),
        profit_margin=_safe_float(info.get("profitMargins")),
        gross_margin=_safe_float(info.get("grossMargins")),
        pe_trailing=_safe_float(info.get("trailingPE")),
        pe_forward=_safe_float(info.get("forwardPE")),
        pb=_safe_float(info.get("priceToBook")),
        ev_to_sales=_safe_float(info.get("enterpriseToRevenue")),
        ev_to_ebitda=_safe_float(info.get("enterpriseToEbitda")),
        revenue_growth=_safe_float(info.get("revenueGrowth")),
        earnings_growth=_safe_float(info.get("earningsGrowth")),
        sector=info.get("sector"),
        industry=info.get("industry"),
        short_name=info.get("shortName") or info.get("longName"),
    )


def fetch_batch(
    tickers: Iterable[str],
) -> list[tuple[PriceMetrics, FundamentalMetrics]]:
    rows: list[tuple[PriceMetrics, FundamentalMetrics]] = []
    for ticker in tickers:
        try:
            rows.append((fetch_price_metrics(ticker), fetch_fundamentals(ticker)))
        except Exception:
            continue
    return rows
