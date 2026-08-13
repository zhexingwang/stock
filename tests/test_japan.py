from stock_agent.data import load_universe_meta
from stock_agent.japan import SEGMENT_LABELS, _jpy, attach_universe_meta, jp_source_links
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
