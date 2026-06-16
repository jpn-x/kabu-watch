#!/usr/bin/env python3
"""
東証 危険銘柄スクレイパー
Playwright（ヘッドレスChromium）でJPXを取得 → JSON保存
"""
import json
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

# ---- Playwright でフェッチ ----

def fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ja-JP",
                extra_http_headers={"Accept-Language": "ja,en-US;q=0.9"},
            )
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            # 動的コンテンツ読み込み待機
            time.sleep(2)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"[WARN] playwright failed for {url}: {e}")
        return None


def fetch_with_requests(url: str) -> str | None:
    """Playwrightが使えない場合のフォールバック"""
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.jpx.co.jp/",
        }
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return r.text
    except Exception as e:
        print(f"[WARN] requests failed for {url}: {e}")
        return None


def fetch(url: str) -> "BeautifulSoup | None":
    from bs4 import BeautifulSoup
    html = fetch_with_playwright(url)
    if html is None:
        print(f"[INFO] fallback to requests: {url}")
        html = fetch_with_requests(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    # デバッグ: ページタイトルと先頭500文字を出力
    title = soup.title.string if soup.title else "(no title)"
    print(f"[DEBUG] title: {title}")
    tables = soup.select("table")
    print(f"[DEBUG] table count: {len(tables)}")
    for i, t in enumerate(tables[:3]):
        rows = t.select("tr")
        print(f"[DEBUG] table[{i}] rows={len(rows)} first_text={t.get_text()[:120].strip()!r}")
    # HTMLスニペットをファイルに保存（構造確認用）
    slug = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1].replace(".html","")
    Path("data").mkdir(exist_ok=True)
    with open(f"data/debug_{slug}.html", "w", encoding="utf-8") as f:
        f.write(html[:50000])
    return soup


# ---- パース ----

def parse_table_rows(soup, category: str, risk_level: str) -> list[dict]:
    stocks = []
    if soup is None:
        return stocks

    for row in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in row.select("td")]
        # 空行スキップ
        if len(cells) < 2 or not cells[0]:
            continue
        # コードらしき4桁数字があるか確認
        code = re.sub(r"\D", "", cells[0])[:4]
        if not re.match(r"^\d{4}$", code):
            continue
        stocks.append({
            "code": code,
            "name": cells[1] if len(cells) > 1 else "",
            "market": cells[2] if len(cells) > 2 else "",
            "designated_date": cells[3] if len(cells) > 3 else "",
            "delisting_date": cells[4] if len(cells) > 4 else "",
            "category": category,
            "risk_level": risk_level,
        })
    return stocks


def parse_supervision(soup) -> list[dict]:
    """監理・整理銘柄一覧ページ — 監理ポストと整理ポストが混在"""
    if soup is None:
        return []
    stocks = []
    # 複数テーブルを走査し、ヘッダーを見てカテゴリを判定
    for table in soup.select("table"):
        header_text = table.get_text()
        if "整理" in header_text:
            cat, risk = "整理ポスト", "極高"
        else:
            cat, risk = "管理ポスト（監理）", "高"
        for row in table.select("tbody tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) < 2:
                continue
            code = re.sub(r"\D", "", cells[0])[:4]
            if not re.match(r"^\d{4}$", code):
                continue
            stocks.append({
                "code": code,
                "name": cells[1] if len(cells) > 1 else "",
                "market": cells[2] if len(cells) > 2 else "",
                "designated_date": cells[3] if len(cells) > 3 else "",
                "delisting_date": cells[4] if len(cells) > 4 else "",
                "category": cat,
                "risk_level": risk,
            })
    return stocks


def parse_improvement(soup) -> list[dict]:
    """改善期間該当銘柄"""
    return parse_table_rows(soup, "改善期間中", "中")


def parse_delisted(soup) -> list[dict]:
    """上場廃止銘柄一覧（直近のもの）"""
    if soup is None:
        return []
    stocks = []
    for row in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in row.select("td")]
        if len(cells) < 2:
            continue
        code = re.sub(r"\D", "", cells[0])[:4]
        if not re.match(r"^\d{4}$", code):
            continue
        stocks.append({
            "code": code,
            "name": cells[1] if len(cells) > 1 else "",
            "market": cells[2] if len(cells) > 2 else "",
            "designated_date": "",
            "delisting_date": cells[3] if len(cells) > 3 else "",
            "category": "上場廃止",
            "risk_level": "廃止確定",
        })
    return stocks


# ---- メイン ----

URLS = {
    "監理・整理銘柄": "https://www.jpx.co.jp/listing/market-alerts/supervision/index.html",
    "改善期間": "https://www.jpx.co.jp/listing/market-alerts/improvement-period/index.html",
    "上場廃止": "https://www.jpx.co.jp/listing/stocks/delisted/index.html",
}


def scrape_jpx() -> list[dict]:
    all_stocks: list[dict] = []

    print("[INFO] 監理・整理銘柄一覧取得中...")
    soup = fetch(URLS["監理・整理銘柄"])
    stocks = parse_supervision(soup)
    print(f"[INFO]   → {len(stocks)}件")
    all_stocks.extend(stocks)

    time.sleep(3)

    print("[INFO] 改善期間該当銘柄取得中...")
    soup = fetch(URLS["改善期間"])
    stocks = parse_improvement(soup)
    print(f"[INFO]   → {len(stocks)}件")
    all_stocks.extend(stocks)

    time.sleep(3)

    print("[INFO] 上場廃止銘柄一覧取得中...")
    soup = fetch(URLS["上場廃止"])
    stocks = parse_delisted(soup)
    print(f"[INFO]   → {len(stocks)}件")
    all_stocks.extend(stocks)

    # 重複除去（code+categoryキー）
    seen: set[str] = set()
    unique: list[dict] = []
    for s in all_stocks:
        key = f"{s['code']}_{s['category']}"
        if key not in seen and s["code"]:
            seen.add(key)
            unique.append(s)

    return unique


def main():
    now_jst = datetime.now(JST)
    print(f"[INFO] 実行時刻: {now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}")

    stocks = scrape_jpx()
    print(f"[INFO] 取得件数合計: {len(stocks)}")

    # 廃止確定フラグ（整理ポストで廃止日が入っているもの）
    for s in stocks:
        if s["category"] == "整理ポスト" and s.get("delisting_date"):
            s["category"] = "上場廃止決定"
            s["risk_level"] = "廃止確定"

    output = {
        "updated_at": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at_iso": now_jst.isoformat(),
        "count": len(stocks),
        "stocks": stocks,
        "source": "東京証券取引所 (JPX)",
        "source_urls": URLS,
    }

    Path("data").mkdir(exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[INFO] data/stocks.json 保存完了")

    # スクレイピング結果がゼロでも警告だけ出してexit 0にする（前回データを残す）
    if not stocks:
        print("[WARN] 取得件数0件。JPXページ構造変更の可能性あり。前回データを維持します。")


if __name__ == "__main__":
    main()
