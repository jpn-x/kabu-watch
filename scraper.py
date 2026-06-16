#!/usr/bin/env python3
"""
東証 危険銘柄スクレイパー
整理ポスト・管理ポスト・上場廃止確定銘柄を取得してJSONに保存する
"""
import json
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.jpx.co.jp/",
}

BASE = "https://www.jpx.co.jp"
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url: str) -> BeautifulSoup | None:
    try:
        r = SESSION.get(url, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[WARN] fetch failed: {url} -> {e}")
        return None


def parse_seiriposts(soup: BeautifulSoup) -> list[dict]:
    """整理ポスト銘柄を取得"""
    stocks = []
    if soup is None:
        return stocks

    for row in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in row.select("td")]
        if len(cells) >= 4:
            stocks.append({
                "code": cells[0],
                "name": cells[1],
                "market": cells[2] if len(cells) > 2 else "",
                "designated_date": cells[3] if len(cells) > 3 else "",
                "delisting_date": cells[4] if len(cells) > 4 else "",
                "category": "整理ポスト",
                "risk_level": "極高",
            })

    # テーブルが見つからない場合はdlやliからも試みる
    if not stocks:
        for item in soup.select(".component-text-block li, .component-list li"):
            text = item.get_text(strip=True)
            m = re.search(r"(\d{4})[　\s]+(.+?)(?:　|\s|（)", text)
            if m:
                stocks.append({
                    "code": m.group(1),
                    "name": m.group(2).strip(),
                    "market": "",
                    "designated_date": "",
                    "delisting_date": "",
                    "category": "整理ポスト",
                    "risk_level": "極高",
                })
    return stocks


def parse_kanriposts(soup: BeautifulSoup) -> list[dict]:
    """管理ポスト銘柄を取得"""
    stocks = []
    if soup is None:
        return stocks

    for row in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in row.select("td")]
        if len(cells) >= 3:
            stocks.append({
                "code": cells[0],
                "name": cells[1],
                "market": cells[2] if len(cells) > 2 else "",
                "designated_date": cells[3] if len(cells) > 3 else "",
                "delisting_date": "",
                "category": "管理ポスト",
                "risk_level": "高",
            })
    return stocks


def parse_delisting_decided(soup: BeautifulSoup) -> list[dict]:
    """上場廃止決定銘柄を取得"""
    stocks = []
    if soup is None:
        return stocks

    for row in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in row.select("td")]
        if len(cells) >= 3:
            stocks.append({
                "code": cells[0],
                "name": cells[1],
                "market": cells[2] if len(cells) > 2 else "",
                "designated_date": "",
                "delisting_date": cells[3] if len(cells) > 3 else cells[-1],
                "category": "上場廃止決定",
                "risk_level": "廃止確定",
            })
    return stocks


def scrape_jpx() -> list[dict]:
    all_stocks: list[dict] = []

    urls = {
        "整理ポスト": f"{BASE}/listing/others/delisting/index.html",
        "管理ポスト": f"{BASE}/listing/maintenance/index.html",
        "上場廃止決定": f"{BASE}/listing/others/delisting/index.html",
    }

    print("[INFO] 整理ポスト取得中...")
    soup_seiri = fetch(urls["整理ポスト"])
    all_stocks.extend(parse_seiriposts(soup_seiri))
    time.sleep(2)

    print("[INFO] 管理ポスト取得中...")
    soup_kanri = fetch(urls["管理ポスト"])
    all_stocks.extend(parse_kanriposts(soup_kanri))
    time.sleep(2)

    # サブページやPDF一覧から廃止確定も試みる
    print("[INFO] 上場廃止決定銘柄取得中...")
    soup_del = fetch(f"{BASE}/listing/others/delisting/index.html")
    all_stocks.extend(parse_delisting_decided(soup_del))

    # 重複除去（codeベース）
    seen: set[str] = set()
    unique: list[dict] = []
    for s in all_stocks:
        key = f"{s['code']}_{s['category']}"
        if key not in seen and s["code"]:
            seen.add(key)
            unique.append(s)

    return unique


def build_fallback() -> list[dict]:
    """スクレイピング失敗時の手動入力データ（最終更新日を明示）"""
    # JPX公表データを手動でメンテする場合はここに記載
    return []


def main():
    now_jst = datetime.now(JST)
    print(f"[INFO] 実行時刻: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")

    stocks = scrape_jpx()
    print(f"[INFO] 取得件数: {len(stocks)}")

    if not stocks:
        print("[WARN] スクレイピング失敗。フォールバックデータを使用")
        stocks = build_fallback()

    output = {
        "updated_at": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_iso": now_jst.isoformat(),
        "count": len(stocks),
        "stocks": stocks,
        "source": "東京証券取引所 (JPX)",
        "source_urls": {
            "整理ポスト": "https://www.jpx.co.jp/listing/others/delisting/index.html",
            "管理ポスト": "https://www.jpx.co.jp/listing/maintenance/index.html",
        },
    }

    Path("data").mkdir(exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[INFO] data/stocks.json に保存完了 ({len(stocks)}件)")


if __name__ == "__main__":
    main()
