from stock_agent.data import load_universe_meta
from stock_agent.japan import (
    SEGMENT_LABELS,
    _jpy,
    attach_universe_meta,
    build_update_section,
    comparable_price_change,
    jp_source_links,
)
import pandas as pd


def test_jp_universe_has_segments(tmp_path):
    rows = load_universe_meta("examples/universe_jp.csv")
    assert len(rows) >= 40
    assert any(r["ticker"] == "8267.T" and r["segment"] == "domestic" for r in rows)
    assert any(r["name_ja"] == "イオン" for r in rows)


def test_jpy_format():
    assert "兆円" in _jpy(1.37e13)
    assert "億円" in _jpy(3.8e11)
    assert _jpy(None) == "n/a"


def test_source_links():
    links = jp_source_links("8267.T")
    assert "8267" in links["kabutan"]
    assert "8267.T" in links["yahoo_jp"]


def test_attach_meta():
    df = pd.DataFrame([{"ticker": "8267.T", "short_name": "AEON"}])
    out = attach_universe_meta(df, "examples/universe_jp.csv")
    assert out.loc[0, "name_ja"] == "イオン"
    assert out.loc[0, "segment_ja"] == SEGMENT_LABELS["domestic"]


def test_split_suspect_when_price_collapses_but_return_does_not():
    change, suspect = comparable_price_change(59620, 9805, 0.11)
    assert suspect
    assert change < -0.8
    _, not_split = comparable_price_change(1388.5, 1151, -0.31)
    assert not not_split


def test_update_section_flags_stage_change():
    current = pd.DataFrame(
        [
            {
                "ticker": "5803.T",
                "name_ja": "フジクラ",
                "last_price": 4111,
                "drawdown_52w": -0.47,
                "return_6m": -0.30,
                "stage": "底値圏",
                "recovery_score": 51.5,
                "verdict": "様子見",
            }
        ]
    )
    previous = pd.DataFrame(
        [
            {
                "ticker": "5803.T",
                "name_ja": "フジクラ",
                "last_price": 5896,
                "drawdown_52w": -0.25,
                "return_6m": 0.64,
                "stage": "調整後リバウンド",
                "recovery_score": 38.0,
                "verdict": "見送り",
            }
        ]
    )
    text = build_update_section(current, previous, "jp-profile-2026-08-13.csv")
    assert "フジクラ" in text
    assert "底値圏" in text
    assert "比較不能" not in text
