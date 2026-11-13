from __future__ import annotations

import argparse
import json
from pathlib import Path

from stock_agent.data import fetch_fundamentals, fetch_price_metrics, utc_today
from stock_agent.filings import extract_quantitative_facts, list_recent_filings
from stock_agent.japan import write_japan_report
from stock_agent.models import to_dict
from stock_agent.report import write_report
from stock_agent.scoring import score_recovery
from stock_agent.screen import save_screen, screen_universe
from stock_agent.segments import list_themes, screen_theme


def _print_df(df) -> None:
    if df.empty:
        print("該当なし")
        return
    try:
        print(df.to_markdown(index=False))
    except Exception:
        print(df.to_string(index=False))


def cmd_screen(args: argparse.Namespace) -> int:
    df = screen_universe(
        universe_path=args.universe,
        min_drawdown=args.min_drawdown,
        min_score=args.min_score,
        sector=args.sector,
    )
    _print_df(df)
    if args.out:
        path = save_screen(df, args.out)
        print(f"saved: {path}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    price = fetch_price_metrics(args.ticker)
    fund = fetch_fundamentals(args.ticker)
    score = score_recovery(price, fund)
    payload = {
        "price": to_dict(price),
        "fundamentals": to_dict(fund),
        "recovery_score": to_dict(score),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_filings(args: argparse.Namespace) -> int:
    if args.list_only:
        items = list_recent_filings(args.ticker, limit=args.limit)
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    snippets = extract_quantitative_facts(args.ticker)
    print(json.dumps([to_dict(s) for s in snippets], ensure_ascii=False, indent=2))
    return 0


def cmd_segment(args: argparse.Namespace) -> int:
    if args.list_themes:
        for theme in list_themes():
            print(f"{theme.key}: {theme.title_ja}")
            print(f"  thesis: {theme.thesis}")
            print(f"  signals: {', '.join(theme.macro_signals)}")
        return 0

    theme, df = screen_theme(
        theme_key=args.theme,
        universe_path=args.universe,
        min_drawdown=args.min_drawdown,
        min_score=args.min_score,
    )
    print(f"# {theme.title_ja} ({theme.key})")
    print(theme.thesis)
    print("マクロ信号:", ", ".join(theme.macro_signals))
    print()
    _print_df(df)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        print(f"saved: {path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    path = write_report(args.ticker, args.out)
    print(f"wrote: {path}")
    return 0


def cmd_japan_report(args: argparse.Namespace) -> int:
    paths = write_japan_report(
        universe_path=args.universe,
        out_dir=args.out,
        screen_dir=args.screen_dir,
    )
    print(f"wrote: {paths['report']}")
    print(f"profile: {paths['profile']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-agent",
        description="底値回復投資の調査ツールキット",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_screen = sub.add_parser("screen", help="ユニバースから底値候補を抽出")
    p_screen.add_argument("--universe", required=True, help="ticker列を持つCSV")
    p_screen.add_argument("--min-drawdown", type=float, default=0.35)
    p_screen.add_argument("--min-score", type=float, default=45.0)
    p_screen.add_argument("--sector", default=None)
    p_screen.add_argument("--out", default=f"data/screens/screen-{utc_today()}.csv")
    p_screen.set_defaults(func=cmd_screen)

    p_analyze = sub.add_parser("analyze", help="個別銘柄の定量プロファイル")
    p_analyze.add_argument("--ticker", required=True)
    p_analyze.set_defaults(func=cmd_analyze)

    p_filings = sub.add_parser("filings", help="決算・開示から定量抽出")
    p_filings.add_argument("--ticker", required=True)
    p_filings.add_argument("--list-only", action="store_true")
    p_filings.add_argument("--limit", type=int, default=5)
    p_filings.set_defaults(func=cmd_filings)

    p_segment = sub.add_parser("segment", help="世の中の動向テーマから候補抽出")
    p_segment.add_argument("--theme", default=None)
    p_segment.add_argument("--list-themes", action="store_true")
    p_segment.add_argument("--universe", default="examples/universe_us.csv")
    p_segment.add_argument("--min-drawdown", type=float, default=0.30)
    p_segment.add_argument("--min-score", type=float, default=40.0)
    p_segment.add_argument("--out", default=None)
    p_segment.set_defaults(func=cmd_segment)

    p_report = sub.add_parser("report", help="調査レポート下書きを生成")
    p_report.add_argument("--ticker", required=True)
    p_report.add_argument("--out", default="reports")
    p_report.set_defaults(func=cmd_report)

    p_jp = sub.add_parser("japan-report", help="日本国内の底値回復専用レポート")
    p_jp.add_argument("--universe", default="examples/universe_jp.csv")
    p_jp.add_argument("--out", default="reports")
    p_jp.add_argument("--screen-dir", default="data/screens")
    p_jp.set_defaults(func=cmd_japan_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "segment" and not args.list_themes and not args.theme:
        parser.error("segment には --theme か --list-themes が必要です")
    return args.func(args)
