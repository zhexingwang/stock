from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

import requests

from stock_agent.models import FilingSnippet

SEC_HEADERS = {
    "User-Agent": "stock-agent research bot contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}


def _get_json(url: str) -> dict[str, Any]:
    resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def resolve_cik(ticker: str) -> str | None:
    mapping = _get_json("https://www.sec.gov/files/company_tickers.json")
    target = ticker.upper()
    for item in mapping.values():
        if str(item.get("ticker", "")).upper() == target:
            return str(item["cik_str"]).zfill(10)
    return None


def list_recent_filings(ticker: str, forms: list[str] | None = None, limit: int = 5) -> list[dict[str, Any]]:
    forms = forms or ["10-K", "10-Q", "8-K"]
    cik = resolve_cik(ticker)
    if not cik:
        return []
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    recent = data.get("filings", {}).get("recent", {})
    out: list[dict[str, Any]] = []
    for i, form in enumerate(recent.get("form", [])):
        if form not in forms:
            continue
        acc = recent["accessionNumber"][i].replace("-", "")
        primary = recent["primaryDocument"][i]
        out.append(
            {
                "ticker": ticker.upper(),
                "cik": cik,
                "form": form,
                "filed_at": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_document": primary,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{primary}",
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_company_facts(ticker: str) -> dict[str, Any] | None:
    cik = resolve_cik(ticker)
    if not cik:
        return None
    try:
        return _get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    except requests.HTTPError:
        return None


def _latest_fact(facts: dict[str, Any], concept: str, unit: str = "USD") -> dict[str, Any] | None:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    node = us_gaap.get(concept)
    if not node:
        return None
    series = node.get("units", {}).get(unit) or []
    if not series:
        return None
    # Prefer filed FY/Q recent values
    ordered = sorted(series, key=lambda x: x.get("end") or x.get("filed") or "", reverse=True)
    return ordered[0]


def extract_quantitative_facts(ticker: str) -> list[FilingSnippet]:
    facts = fetch_company_facts(ticker)
    if not facts:
        return [
            FilingSnippet(
                source="SEC EDGAR",
                filed_at=None,
                form=None,
                url=None,
                title="companyfacts 未取得",
                excerpt="CIK解決失敗、またはXBRL factsがありません（非米国銘柄の可能性）。",
            )
        ]

    concepts = {
        "Revenues": "売上高",
        "RevenueFromContractWithCustomerExcludingAssessedTax": "顧客契約売上",
        "NetIncomeLoss": "純利益",
        "OperatingIncomeLoss": "営業利益",
        "Assets": "総資産",
        "Liabilities": "総負債",
        "CashAndCashEquivalentsAtCarryingValue": "現金同等物",
        "LongTermDebt": "長期借入",
        "StockholdersEquity": "株主資本",
    }

    snippets: list[FilingSnippet] = []
    metrics: dict[str, Any] = {}
    for concept, label in concepts.items():
        latest = _latest_fact(facts, concept)
        if not latest:
            continue
        metrics[label] = {
            "value": latest.get("val"),
            "end": latest.get("end"),
            "filed": latest.get("filed"),
            "form": latest.get("form"),
            "concept": concept,
        }

    filings = list_recent_filings(ticker, forms=["10-K", "10-Q"], limit=3)
    latest_url = filings[0]["url"] if filings else None
    latest_filed = filings[0]["filed_at"] if filings else None
    latest_form = filings[0]["form"] if filings else None

    if metrics:
        lines = [
            f"- {k}: {v['value']:,.0f} (期末 {v['end']}, 提出 {v['filed']}, {v['form']})"
            for k, v in metrics.items()
            if isinstance(v.get("value"), (int, float))
        ]
        snippets.append(
            FilingSnippet(
                source="SEC companyfacts (XBRL)",
                filed_at=latest_filed,
                form=latest_form,
                url=latest_url,
                title=f"{ticker.upper()} 主要財務ファクト抽出",
                excerpt="\n".join(lines) if lines else "数値抽出なし",
                metrics=metrics,
            )
        )

    for item in filings:
        snippets.append(
            FilingSnippet(
                source="SEC EDGAR submissions",
                filed_at=item["filed_at"],
                form=item["form"],
                url=item["url"],
                title=f"{item['form']} ({item['filed_at']})",
                excerpt="開示書類リンク。本文の詳細精読は人手または追加パーサで実施。",
            )
        )
    return snippets


def extract_text_keywords(html_or_text: str, keywords: list[str] | None = None, window: int = 180) -> list[str]:
    keywords = keywords or [
        "liquidity",
        "going concern",
        "impairment",
        "restructuring",
        "outlook",
        "guidance",
        "demand",
        "margin",
    ]
    text = re.sub(r"<[^>]+>", " ", html_or_text)
    text = re.sub(r"\s+", " ", text)
    hits: list[str] = []
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw.lower())
        if idx < 0:
            continue
        start = max(0, idx - window // 2)
        end = min(len(text), idx + window // 2)
        hits.append(text[start:end].strip())
    return hits


def try_parse_xml_table(xml_text: str) -> list[dict[str, str]]:
    """軽量なXBRL/XML走査。失敗しても空リスト。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict[str, str]] = []
    for elem in list(root.iter())[:200]:
        if elem.text and elem.text.strip() and elem.tag:
            rows.append({"tag": elem.tag, "text": elem.text.strip()[:200]})
    return rows
