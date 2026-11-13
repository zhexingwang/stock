from stock_agent.models import FundamentalMetrics, PriceMetrics
from stock_agent.scoring import classify_recovery_stage, score_recovery


def _price(**kwargs):
    base = dict(
        ticker="TEST",
        as_of="2026-08-12",
        last_price=10.0,
        currency="USD",
        drawdown_52w=-0.45,
        drawdown_2y=-0.50,
        return_1y=-0.40,
        return_6m=-0.20,
        avg_volume_20d=1_000_000,
        high_52w=20.0,
        low_52w=9.0,
    )
    base.update(kwargs)
    return PriceMetrics(**base)


def _fund(**kwargs):
    base = dict(
        ticker="TEST",
        as_of="2026-08-12",
        market_cap=1e9,
        enterprise_value=1.1e9,
        revenue_ttm=2e9,
        ebitda_ttm=3e8,
        free_cash_flow=1e8,
        total_cash=4e8,
        total_debt=2e8,
        current_ratio=1.8,
        debt_to_equity=40.0,
        operating_margin=0.12,
        profit_margin=0.08,
        gross_margin=0.40,
        pe_trailing=12.0,
        pe_forward=10.0,
        pb=1.1,
        ev_to_sales=0.9,
        ev_to_ebitda=7.0,
        revenue_growth=0.05,
        earnings_growth=0.10,
        sector="Technology",
        industry="Semiconductors",
        short_name="Test Co",
    )
    base.update(kwargs)
    return FundamentalMetrics(**base)


def test_strong_candidate_scores_high():
    score = score_recovery(_price(), _fund())
    assert score.total >= 70
    assert score.verdict in {"監視リスト", "候補（要開示確認）"}


def test_shallow_drawdown_is_rejected():
    score = score_recovery(_price(drawdown_52w=-0.10), _fund())
    assert score.verdict == "見送り"


def test_weak_balance_sheet_flags():
    score = score_recovery(
        _price(),
        _fund(current_ratio=0.6, debt_to_equity=250, free_cash_flow=-5e7, total_cash=1e7),
    )
    assert "weak_liquidity" in score.flags
    assert "high_leverage" in score.flags


def test_recovery_stage_bottom_vs_rebound():
    assert classify_recovery_stage(-0.45, -0.20) == "底値圏"
    assert classify_recovery_stage(-0.45, 0.50) == "リバウンド途中"
    assert classify_recovery_stage(-0.08, 0.10) == "高値圏"
    assert classify_recovery_stage(-0.22, -0.05) == "調整"
