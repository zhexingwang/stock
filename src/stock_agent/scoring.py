from __future__ import annotations

from stock_agent.models import FundamentalMetrics, PriceMetrics, RecoveryScore


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_recovery(price: PriceMetrics, fund: FundamentalMetrics) -> RecoveryScore:
    """定量のみの回復スコア。0-100。高いほど『底＋回復余地』寄り。"""
    components: dict[str, float] = {}
    flags: list[str] = []
    rationale: list[str] = []

    # 1) 売られ過ぎ（最大30）
    dd = price.drawdown_52w
    if dd is None:
        components["drawdown"] = 0.0
        flags.append("drawdown_missing")
    else:
        # -30%で0.4, -50%で0.8, -70%で1.0
        severity = _clamp((-dd - 0.20) / 0.50)
        components["drawdown"] = 30.0 * severity
        rationale.append(f"52週高値比ドローダウン {dd:.1%}")

    # 2) 流動性・生存（最大25）
    survival = 0.0
    cr = fund.current_ratio
    if cr is None:
        flags.append("current_ratio_missing")
    elif cr >= 1.5:
        survival += 12.0
        rationale.append(f"流動比率 {cr:.2f} で短期支払い余力あり")
    elif cr >= 1.0:
        survival += 7.0
        rationale.append(f"流動比率 {cr:.2f} は最低ライン付近")
    else:
        survival += 0.0
        flags.append("weak_liquidity")
        rationale.append(f"流動比率 {cr:.2f} は弱い")

    dte = fund.debt_to_equity
    if dte is None:
        flags.append("debt_to_equity_missing")
    elif dte <= 50:
        survival += 8.0
    elif dte <= 100:
        survival += 5.0
    elif dte <= 200:
        survival += 2.0
        flags.append("elevated_leverage")
    else:
        flags.append("high_leverage")

    fcf = fund.free_cash_flow
    cash = fund.total_cash
    debt = fund.total_debt
    if fcf is not None and fcf > 0:
        survival += 5.0
        rationale.append("FCFがプラス")
    elif fcf is not None and fcf <= 0:
        flags.append("negative_fcf")
        if cash is not None and debt is not None and cash > debt:
            survival += 2.0
            rationale.append("FCFマイナスだがネットキャッシュ")
        else:
            rationale.append("FCFマイナスで耐久力要確認")
    components["survival"] = survival

    # 3) 収益の質・反転余地（最大25）
    quality = 0.0
    om = fund.operating_margin
    if om is not None:
        if om > 0.10:
            quality += 10.0
            rationale.append(f"営業利益率 {om:.1%} は黒字基盤あり")
        elif om > 0:
            quality += 6.0
        elif om > -0.05:
            quality += 3.0
            flags.append("thin_or_negative_margin")
        else:
            flags.append("deep_negative_margin")
    gm = fund.gross_margin
    if gm is not None and gm >= 0.30:
        quality += 5.0
    rg = fund.revenue_growth
    eg = fund.earnings_growth
    if rg is not None and rg > 0:
        quality += 5.0
        rationale.append(f"売上成長 {rg:.1%}")
    if eg is not None and eg > 0:
        quality += 5.0
        rationale.append(f"利益成長 {eg:.1%}")
    components["quality"] = quality

    # 4) バリュエーションの余裕（最大20）
    value = 0.0
    if fund.ev_to_sales is not None:
        if fund.ev_to_sales < 1.0:
            value += 10.0
        elif fund.ev_to_sales < 2.5:
            value += 6.0
        elif fund.ev_to_sales < 5.0:
            value += 3.0
    if fund.ev_to_ebitda is not None and fund.ev_to_ebitda > 0:
        if fund.ev_to_ebitda < 8:
            value += 6.0
        elif fund.ev_to_ebitda < 12:
            value += 4.0
        elif fund.ev_to_ebitda < 18:
            value += 2.0
    if fund.pb is not None and 0 < fund.pb < 1.2:
        value += 4.0
        rationale.append(f"P/B {fund.pb:.2f} は資産面で割安寄り")
    components["valuation"] = value

    total = round(sum(components.values()), 1)

    hard_reject = "weak_liquidity" in flags and "high_leverage" in flags
    if hard_reject or total < 35:
        verdict = "見送り"
    elif total < 55:
        verdict = "様子見"
    elif total < 70:
        verdict = "監視リスト"
    else:
        verdict = "候補（要開示確認）"

    if dd is not None and dd > -0.25:
        verdict = "見送り"
        rationale.append("ドローダウンが浅く『底値』仮説が弱い")

    return RecoveryScore(
        ticker=price.ticker,
        total=total,
        components=components,
        flags=flags,
        verdict=verdict,
        rationale=rationale,
    )


def classify_recovery_stage(drawdown_52w: float | None, return_6m: float | None) -> str:
    """価格位置。底値買い戦略では『底値圏』を優先し、リバウンド途中は遅れて入る。"""
    if drawdown_52w is None:
        return "不明"
    if drawdown_52w > -0.15:
        return "高値圏"
    bounced = return_6m is not None and return_6m > 0.10
    if drawdown_52w <= -0.30 and bounced:
        return "リバウンド途中"
    if drawdown_52w <= -0.30:
        return "底値圏"
    if bounced:
        return "調整後リバウンド"
    return "調整"
