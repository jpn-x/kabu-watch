#!/usr/bin/env python3
"""JSONデータからindex.htmlを生成する"""
import json
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

CATEGORY_BADGE = {
    "整理銘柄":         '<span class="badge badge-seiri">🔴 整理銘柄</span>',
    "監理銘柄（確認中）": '<span class="badge badge-kakunin">🟠 監理（確認中）</span>',
    "監理銘柄（審査中）": '<span class="badge badge-shinsa">🟡 監理（審査中）</span>',
    "監理銘柄":         '<span class="badge badge-kanri">🟠 監理銘柄</span>',
    "上場廃止":         '<span class="badge badge-abolished">⛔ 上場廃止</span>',
    "改善期間中":        '<span class="badge badge-kaizen">🟡 改善期間中</span>',
}
CATEGORY_ICON = {
    "整理銘柄": "🔴", "監理銘柄（確認中）": "🟠", "監理銘柄（審査中）": "🟡",
    "監理銘柄": "🟠", "上場廃止": "⛔", "改善期間中": "🟡",
}
CATEGORY_KEY = {
    "整理銘柄": "seiri", "監理銘柄（確認中）": "kakunin", "監理銘柄（審査中）": "shinsa",
    "監理銘柄": "kanri", "上場廃止": "abolished", "改善期間中": "kaizen",
}

ADVICE_HTML = """
<section class="advice">
  <h2>⚠️ 危険銘柄を見分けるポイント</h2>
  <div class="advice-grid">
    <div class="advice-card card-seiri"><h3>🔴 整理銘柄</h3>
      <p>上場廃止が確定または高確率で見込まれる銘柄。<strong>即時損切り推奨</strong>。廃止日までに必ず処分。</p></div>
    <div class="advice-card card-kanri"><h3>🟠 監理銘柄（確認中）</h3>
      <p>上場廃止基準抵触の疑いがあり確認中。<strong>新規購入は厳禁</strong>。整理銘柄へ移行する可能性が高い。</p></div>
    <div class="advice-card card-shinsa"><h3>🟡 監理銘柄（審査中）</h3>
      <p>MBO・TOB等で上場廃止の審査中。<strong>高値掴みに注意</strong>。</p></div>
    <div class="advice-card card-abolished"><h3>⛔ 上場廃止</h3>
      <p>廃止日が確定。<strong>最終売買日までに必ず処分</strong>。過ぎると売れなくなります。</p></div>
    <div class="advice-card"><h3>👀 その他の危険サイン</h3>
      <ul>
        <li>監査法人から「意見不表明」「否定的意見」</li>
        <li>継続企業の疑義注記（GC注記）</li>
        <li>債務超過・純資産マイナス</li>
        <li>業績予想の大幅下方修正が連続</li>
        <li>主要取引先・代表者の突然の変更</li>
      </ul>
    </div>
  </div>
</section>
"""


def primary_month(s: dict) -> str:
    """月タブ用のYYYY/MM文字列（指定日優先、なければ廃止日）"""
    for key in ("designated_date", "delisting_date"):
        d = s.get(key, "")
        if d and re.match(r"\d{4}/\d{2}", d):
            return d[:7]
    return ""


def render_row(s: dict) -> str:
    icon  = CATEGORY_ICON.get(s["category"], "⚠️")
    badge = CATEGORY_BADGE.get(s["category"], f'<span class="badge badge-kanri">{s["category"]}</span>')
    delisting      = s.get("delisting_date") or "—"
    last_trading   = s.get("last_trading_date") or "—"
    designated     = s.get("designated_date") or "—"
    market = s.get("market") or "—"
    reason = s.get("reason") or ""
    name_html = f'{icon} {s["name"]}'
    if reason:
        name_html += f'<br><small class="reason-text">{reason}</small>'
    cat_key = CATEGORY_KEY.get(s["category"], "kanri")
    month   = primary_month(s)
    delisting_html = f'<span class="delisting-date">{delisting}</span>' if delisting != "—" else "—"
    # 最終売買日: 廃止日がある銘柄のみ強調表示
    if last_trading != "—":
        ltd_html = f'<span class="last-trading-date">{last_trading}<small class="ltd-label">最終売買</small></span>'
    else:
        ltd_html = '<span class="ltd-none">—</span>'
    return (
        f'<tr class="stock-row" data-cat="{cat_key}" data-month="{month}">'
        f'<td class="td-code-block"><span class="stock-code">{s["code"]}</span>{ltd_html}</td>'
        f'<td class="stock-name">{name_html}</td>'
        f'<td>{market}</td>'
        f'<td>{badge}</td>'
        f'<td>{designated}</td>'
        f'<td>{delisting_html}</td>'
        f'</tr>'
    )


def generate(data_path: str = "data/stocks.json", out_path: str = "index.html"):
    p = Path(data_path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        stocks = data["stocks"]
        updated_at = data["updated_at"]
    else:
        stocks = []
        updated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    seiri    = [s for s in stocks if s["category"] == "整理銘柄"]
    kakunin  = [s for s in stocks if s["category"] == "監理銘柄（確認中）"]
    shinsa   = [s for s in stocks if s["category"] == "監理銘柄（審査中）"]
    kanri    = [s for s in stocks if s["category"] == "監理銘柄"]
    abolished= [s for s in stocks if s["category"] == "上場廃止"]
    kaizen   = [s for s in stocks if s["category"] == "改善期間中"]
    sorted_stocks = seiri + kakunin + shinsa + kanri + abolished + kaizen

    rows_html = "\n".join(render_row(s) for s in sorted_stocks)
    if not rows_html:
        rows_html = '<tr><td colspan="6" class="no-data">⚠️ データなし — <a href="https://www.jpx.co.jp/listing/market-alerts/supervision/index.html" target="_blank">JPX公式サイト</a></td></tr>'

    # 月タブ生成（データに存在する月を降順で列挙）
    months_set: set[str] = set()
    for s in sorted_stocks:
        m = primary_month(s)
        if m:
            months_set.add(m)
    months_sorted = sorted(months_set, reverse=True)  # 新しい月が左

    month_tabs_html = '<button class="tab t-month active" data-month="all" onclick="setMonth(\'all\')">全期間</button>\n'
    for m in months_sorted:
        label = m  # "YYYY/MM"
        month_tabs_html += f'    <button class="tab t-month" data-month="{m}" onclick="setMonth(\'{m}\')">{label}</button>\n'

    n_seiri    = len(seiri)
    n_kakunin  = len(kakunin)
    n_shinsa   = len(shinsa)
    n_abolished= len(abolished)
    n_all      = len(sorted_stocks)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>東証 危険銘柄ウォッチ 🚨</title>
  <meta name="description" content="東京証券取引所の整理銘柄・監理銘柄・上場廃止確定銘柄を毎日自動更新">
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="192x192" href="icons/favicon-192.png">
  <link rel="icon" type="image/png" sizes="512x512" href="icons/favicon-512.png">
  <meta name="theme-color" content="#3d0808">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="危険銘柄ウォッチ">
  <style>
    :root {{
      --red:#e53e3e; --orange:#dd6b20; --dark-red:#9b2335;
      --bg:#0f0f1a; --card-bg:#1a1a2e; --border:#2d2d4e;
      --text:#e2e8f0; --muted:#a0aec0; --accent:#f6ad55;
    }}
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'Hiragino Kaku Gothic Pro','Meiryo',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}

    header{{background:linear-gradient(135deg,#1a0a0a,#2d1515,#1a0a0a);border-bottom:2px solid var(--red);padding:22px 20px;text-align:center;}}
    header h1{{font-size:clamp(1.4rem,4vw,2.2rem);color:#fff;text-shadow:0 0 20px rgba(229,62,62,.8);}}
    .subtitle{{color:var(--muted);margin-top:5px;font-size:.9rem;}}
    .updated{{margin-top:8px;font-size:.82rem;color:var(--accent);}}
    .container{{max-width:1100px;margin:0 auto;padding:20px;}}

    /* 統計カード */
    .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:18px 0;}}
    .stat-card{{background:var(--card-bg);border-radius:12px;padding:14px;text-align:center;border:1px solid var(--border);cursor:pointer;transition:border-color .2s,transform .1s;}}
    .stat-card:hover{{transform:translateY(-2px);}}
    .stat-card.s-seiri{{border-color:#e53e3e;}}
    .stat-card.s-kanri{{border-color:#dd6b20;}}
    .stat-card.s-abolished{{border-color:#742a2a;background:#1a0a0a;}}
    .stat-card.s-all{{border-color:#4a4a7a;}}
    .stat-number{{font-size:2rem;font-weight:bold;}}
    .s-seiri .stat-number{{color:#fc8181;}}
    .s-kanri .stat-number{{color:var(--accent);}}
    .s-abolished .stat-number{{color:#fc8181;}}
    .s-all .stat-number{{color:#fff;}}
    .stat-label{{font-size:.76rem;color:var(--muted);margin-top:3px;}}

    /* フィルターエリア共通 */
    .filter-section{{margin-top:18px;}}
    .filter-row{{
      display:flex; align-items:center; gap:6px;
      flex-wrap:wrap; padding:8px 0;
    }}
    .filter-row + .filter-row{{
      border-top:1px solid var(--border);
      padding-top:10px; margin-top:4px;
    }}
    .filter-label{{
      font-size:.72rem; color:var(--muted);
      white-space:nowrap; min-width:52px; letter-spacing:.03em;
    }}

    /* タブ共通 */
    .tab{{
      background:var(--card-bg); color:#cce0f8;
      border:1px solid var(--border); border-radius:8px;
      padding:6px 13px; font-size:.8rem; cursor:pointer;
      white-space:nowrap; transition:all .2s;
    }}
    .tab:hover{{color:#e8f4ff;border-color:#5a5a8a;}}
    .tab.active{{color:#fff;font-weight:bold;}}

    /* 月タブ */
    .t-month.active{{background:#1e2a3e;border-color:#5a7aaa;color:#a8d4ff;}}

    /* カテゴリタブ */
    .reload-btn{{
      background:#1e2a3a;color:var(--accent);
      border:1px solid #3a5a7a;border-radius:8px;
      padding:6px 13px;font-size:.8rem;cursor:pointer;
      white-space:nowrap;transition:background .2s;
    }}
    .reload-btn:hover{{background:#2a3a4a;}}
    .reload-btn:active{{transform:scale(.96);}}
    .tab-divider{{width:1px;height:26px;background:var(--border);margin:0 3px;}}
    .t-all.active      {{background:#2a2a4e;border-color:#7a7aaa;}}
    .t-seiri.active    {{background:#4a1010;border-color:var(--red);color:#fc8181;}}
    .t-kakunin.active  {{background:#4a2000;border-color:var(--orange);color:var(--accent);}}
    .t-shinsa.active   {{background:#3a2a00;border-color:#b7791f;color:#fbd38d;}}
    .t-abolished.active{{background:#2a0808;border-color:#742a2a;color:#fc8181;}}

    .result-count{{font-size:.8rem;color:var(--muted);margin-left:auto;white-space:nowrap;align-self:center;}}

    /* テーブル */
    .table-wrap{{overflow-x:auto;background:var(--card-bg);border-radius:12px;border:1px solid var(--border);margin:10px 0 20px;}}
    table{{width:100%;border-collapse:collapse;}}
    thead th{{background:#16213e;padding:11px 14px;text-align:left;font-size:.8rem;color:var(--muted);letter-spacing:.05em;border-bottom:1px solid var(--border);white-space:nowrap;}}
    tbody tr{{border-bottom:1px solid var(--border);transition:background .12s;}}
    tbody tr:hover{{background:rgba(255,255,255,.04);}}
    tbody tr:last-child{{border-bottom:none;}}
    td{{padding:10px 14px;font-size:.88rem;vertical-align:middle;}}
    tr[data-cat="seiri"]    {{background:rgba(229,62,62,.07);}}
    tr[data-cat="abolished"]{{background:rgba(116,42,42,.13);}}
    tr.hidden{{display:none;}}

    .stock-code{{font-family:monospace;font-weight:bold;font-size:.98rem;color:var(--accent);}}
    .stock-name{{font-weight:500;}}
    .reason-text{{color:var(--muted);font-size:.76rem;}}
    .delisting-date{{color:#fc8181;font-weight:bold;}}

    .badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.74rem;font-weight:bold;white-space:nowrap;}}
    .badge-seiri    {{background:var(--red);color:#fff;}}
    .badge-kakunin  {{background:#c05621;color:#fff;}}
    .badge-shinsa   {{background:#975a16;color:#fff;}}
    .badge-kanri    {{background:var(--orange);color:#fff;}}
    .badge-abolished{{background:var(--dark-red);color:#fff;border:1px solid #fc8181;}}
    .badge-kaizen   {{background:#744210;color:#fff;}}

    /* コード＋最終売買日セル */
    .td-code-block{{white-space:nowrap;vertical-align:middle;}}
    .last-trading-date{{
      display:block; margin-top:4px;
      background:linear-gradient(135deg,#7a1010,#b22222);
      color:#fff; font-weight:bold; font-size:.78rem;
      padding:3px 8px; border-radius:6px;
      letter-spacing:.04em; line-height:1.3;
      box-shadow:0 0 8px rgba(220,50,50,.5);
      white-space:nowrap;
    }}
    .ltd-label{{
      display:block; font-size:.62rem; font-weight:normal;
      color:rgba(255,255,255,.75); letter-spacing:.02em; margin-top:1px;
    }}
    .ltd-none{{color:var(--muted);font-size:.82rem;}}

    .no-data{{text-align:center;padding:40px;color:var(--muted);line-height:2;}}
    .no-data a{{color:var(--accent);}}

    .advice{{margin:30px 0;}}
    .advice h2{{font-size:1.1rem;margin-bottom:14px;color:var(--accent);}}
    .advice-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}}
    .advice-card{{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:14px;}}
    .advice-card h3{{font-size:.9rem;margin-bottom:7px;}}
    .advice-card p,.advice-card li{{font-size:.82rem;color:var(--muted);line-height:1.6;}}
    .advice-card ul{{padding-left:15px;}}
    .card-seiri{{border-color:var(--red);}}
    .card-kanri{{border-color:var(--orange);}}
    .card-shinsa{{border-color:#b7791f;}}
    .card-abolished{{border-color:var(--dark-red);}}

    footer{{text-align:center;padding:28px 20px;font-size:.76rem;color:var(--muted);border-top:1px solid var(--border);margin-top:20px;}}
    footer a{{color:var(--accent);text-decoration:none;}}

    @media(max-width:600px){{
      td,th{{padding:8px 8px;font-size:.78rem;}}
      .tab{{padding:5px 9px;font-size:.74rem;}}
    }}
  </style>
</head>
<body>

<header>
  <h1>🚨 東証 危険銘柄ウォッチ</h1>
  <p class="subtitle">整理銘柄・監理銘柄・上場廃止確定銘柄を毎日自動更新</p>
  <p class="updated">🕐 最終更新: {updated_at} JST ／ データ出典: 東京証券取引所（JPX）</p>
</header>

<div class="container">

  <div class="stats">
    <div class="stat-card s-seiri"     onclick="setCat('seiri')">
      <div class="stat-number">{n_seiri}</div>
      <div class="stat-label">🔴 整理銘柄</div>
    </div>
    <div class="stat-card s-kanri"    onclick="setCat('kakunin')">
      <div class="stat-number">{n_kakunin}</div>
      <div class="stat-label">🟠 監理（確認中）</div>
    </div>
    <div class="stat-card s-kanri"    onclick="setCat('shinsa')">
      <div class="stat-number">{n_shinsa}</div>
      <div class="stat-label">🟡 監理（審査中）</div>
    </div>
    <div class="stat-card s-abolished" onclick="setCat('abolished')">
      <div class="stat-number">{n_abolished}</div>
      <div class="stat-label">⛔ 上場廃止</div>
    </div>
    <div class="stat-card s-all"      onclick="setCat('all');setMonth('all')">
      <div class="stat-number">{n_all}</div>
      <div class="stat-label">⚠️ 合計</div>
    </div>
  </div>

  <div class="filter-section">

    <!-- 月タブ（1段目） -->
    <div class="filter-row">
      <span class="filter-label">📅 月で絞る</span>
      {month_tabs_html}
    </div>

    <!-- カテゴリタブ（2段目） -->
    <div class="filter-row">
      <button class="reload-btn" onclick="hardReload()" title="Shift+Ctrl+R でも可">↺ 強制リロード</button>
      <div class="tab-divider"></div>
      <button class="tab t-all active"  onclick="setCat('all')">すべて</button>
      <button class="tab t-abolished"   onclick="setCat('abolished')">⛔ 上場廃止</button>
      <button class="tab t-seiri"       onclick="setCat('seiri')">🔴 整理銘柄</button>
      <button class="tab t-kakunin"     onclick="setCat('kakunin')">🟠 監理（確認中）</button>
      <button class="tab t-shinsa"      onclick="setCat('shinsa')">🟡 監理（審査中）</button>
      <span class="result-count" id="result-count">{n_all} 件</span>
    </div>

  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>コード<br><small style="font-weight:normal;color:#e07070">最終売買日</small></th>
          <th>銘柄名</th><th>市場</th>
          <th>ステータス</th><th>指定日</th><th>上場廃止日</th>
        </tr>
      </thead>
      <tbody id="stock-tbody">
{rows_html}
      </tbody>
    </table>
  </div>

{ADVICE_HTML}

</div>

<footer>
  <p>
    データ出典:
    <a href="https://www.jpx.co.jp/listing/market-alerts/supervision/index.html" target="_blank">JPX 監理・整理銘柄一覧</a> ／
    <a href="https://www.jpx.co.jp/listing/stocks/delisted/index.html" target="_blank">JPX 上場廃止銘柄一覧</a>
  </p>
  <p style="margin-top:8px">⚠️ 本サイトは情報提供のみを目的としています。投資判断は自己責任でお願いします。</p>
  <p style="margin-top:8px">毎日 20:00 JST 自動更新 ／ <a href="https://github.com/jpn-x/kabu-watch" target="_blank">GitHub</a></p>
</footer>

<script>
  var curMonth = 'all';
  var curCat   = 'all';

  function applyFilters() {{
    var rows = document.querySelectorAll('#stock-tbody .stock-row');
    var count = 0;
    rows.forEach(function(r) {{
      var monthOk = curMonth === 'all' || r.dataset.month === curMonth;
      var catOk   = curCat   === 'all' || r.dataset.cat   === curCat;
      if (monthOk && catOk) {{ r.classList.remove('hidden'); count++; }}
      else                  {{ r.classList.add('hidden'); }}
    }});
    document.getElementById('result-count').textContent = count + ' 件';
  }}

  function setMonth(m) {{
    curMonth = m;
    document.querySelectorAll('.t-month').forEach(function(t) {{
      t.classList.toggle('active', t.dataset.month === m);
    }});
    applyFilters();
  }}

  function setCat(cat) {{
    curCat = cat;
    document.querySelectorAll('.filter-row .tab:not(.t-month)').forEach(function(t) {{
      t.classList.remove('active');
    }});
    var sel = document.querySelector('.t-' + cat);
    if (sel) sel.classList.add('active');
    applyFilters();
  }}

  function hardReload() {{
    location.href = location.pathname + '?t=' + Date.now();
  }}

  document.addEventListener('keydown', function(e) {{
    if (e.shiftKey && (e.ctrlKey || e.metaKey) && e.key === 'R') {{
      e.preventDefault(); hardReload();
    }}
  }});
</script>

</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] {out_path} を生成しました ({len(sorted_stocks)}件)")


if __name__ == "__main__":
    generate()
