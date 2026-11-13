from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PriceMetrics:
    ticker: str
    as_of: str
    last_price: float | None
    currency: str | None
    drawdown_52w: float | None
    drawdown_2y: float | None
    return_1y: float | None
    return_6m: float | None
    avg_volume_20d: float | None
    high_52w: float | None
    low_52w: float | None


@dataclass
class FundamentalMetrics:
    ticker: str
    as_of: str
    market_cap: float | None
    enterprise_value: float | None
    revenue_ttm: float | None
    ebitda_ttm: float | None
    free_cash_flow: float | None
    total_cash: float | None
    total_debt: float | None
    current_ratio: float | None
    debt_to_equity: float | None
    operating_margin: float | None
    profit_margin: float | None
    gross_margin: float | None
    pe_trailing: float | None
    pe_forward: float | None
    pb: float | None
    ev_to_sales: float | None
    ev_to_ebitda: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    sector: str | None
    industry: str | None
    short_name: str | None


@dataclass
class RecoveryScore:
    ticker: str
    total: float
    components: dict[str, float]
    flags: list[str]
    verdict: str
    rationale: list[str]


@dataclass
class ScreenRow:
    ticker: str
    short_name: str | None
    sector: str | None
    last_price: float | None
    drawdown_52w: float | None
    return_6m: float | None
    market_cap: float | None
    current_ratio: float | None
    debt_to_equity: float | None
    free_cash_flow: float | None
    operating_margin: float | None
    recovery_score: float | None
    verdict: str | None


@dataclass
class FilingSnippet:
    source: str
    filed_at: str | None
    form: str | None
    url: str | None
    title: str
    excerpt: str
    metrics: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(f"Unsupported type: {type(obj)}")
