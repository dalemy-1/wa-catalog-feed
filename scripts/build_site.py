import csv
import io
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

import requests

# ======================
# Config
# ======================
EXPORT_URL = os.getenv(
    "EXPORT_URL",
    "http://154.48.226.95:5001/admin/Product/export_csv",
)

PRICE_COL = os.getenv("PRICE_COL", "Discount Price")

# 你要展示哪些国家（顺序=页面顺序）
MARKETS = os.getenv("MARKETS", "US,UK,DE,FR,IT,ES,CA,JP").split(",")

MARKET_NAMES = {
    "US": "美国",
    "UK": "英国",
    "DE": "德国",
    "FR": "法国",
    "IT": "意大利",
    "ES": "西班牙",
    "CA": "加拿大",
    "JP": "日本",
}

FLAGS = {
    "US": "🇺🇸",
    "UK": "🇬🇧",
    "DE": "🇩🇪",
    "FR": "🇫🇷",
    "IT": "🇮🇹",
    "ES": "🇪🇸",
    "CA": "🇨🇦",
    "JP": "🇯🇵",
}

CURRENCY_BY_MARKET = {
    "US": "USD",
    "UK": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "CA": "CAD",
    "JP": "JPY",
}

# 你的联系方式（图标按钮链接）
WA_LINK = "https://wa.me/message/DFLXQVO45JMMB1"
TG_LINK = "https://t.me/dalemyrong"

# 输出目录（GitHub Pages 常用 docs/）
OUT_DIR = "docs"

# ======================
# Helpers
# ======================
def norm(s: str) -> str:
    return (s or "").strip()

def normalize_market(m: str) -> str:
    return norm(m).upper()

def normalize_asin(a: str) -> str:
    return norm(a).upper()

def parse_price(v) -> Decimal:
    # 允许 0，无法解析则默认 0
    if v is None:
        return Decimal("0")
    s = str(v).strip()
    if not s:
        return Decimal("0")
    s = s.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return Decimal("0")
    try:
        return Decimal(m.group(1))
    except (InvalidOperation, ValueError):
        return Decimal("0")

def safe_html(s: str) -> str:
    # 最小转义，避免破坏页面
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def build_desc(keyword: str, store: str, remark: str) -> str:
    # 按你现在 WhatsApp 目录里想要的格式：
    # Keyword: xxx
    # Store: yyy
    # remark: Need Text Review
    lines = []
    if keyword:
        lines.append(f"Keyword: {keyword}")
    if store:
        lines.append(f"Store: {store}")
    if remark:
        lines.append(f"remark: {remark}")
    return "\n".join(lines).strip()

def read_source_rows() -> list[dict]:
    r = requests.get(EXPORT_URL, timeout=60)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise RuntimeError("源 CSV 没有表头")
    if PRICE_COL not in reader.fieldnames:
        raise RuntimeError(f"找不到价格列 '{PRICE_COL}'，当前表头: {reader.fieldnames}")
    return list(reader)

def map_row(src: dict) -> dict | None:
    """
    期望你的源 CSV 至少包含：
    market, asin, title, link, image_url, keyword, store, remark, Discount Price
    """
    market = normalize_market(src.get("market"))
    asin = normalize_asin(src.get("asin"))
    title = norm(src.get("title"))
    link = norm(src.get("link"))
    image_url = norm(src.get("image_url"))
    keyword = norm(src.get("keyword"))
    store = norm(src.get("store"))
    remark = norm(src.get("remark"))

    if not market or not asin or not title or not link or not image_url:
        return None

    price = parse_price(src.get(PRICE_COL))
    currency = CURRENCY_BY_MARKET.get(market, "USD")

    # 标题格式： (CA)🇨🇦加拿大蓝色拉力带
    flag = FLAGS.get(market, "")
    title_show = f"({market}){flag}{title}"

    return {
        "market": market,
        "asin": asin,
        "title": title_show,
        "title_raw": title,
        "keyword": keyword,
        "store": store,
        "remark": remark,
        "desc": build_desc(keyword, store, remark),
        "price": f"{price:.2f} {currency}",
        "link": link,
        "image": image_url,
    }

def group_by_market(rows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for r in rows:
        m = r["market"]
        by.setdefault(m, []).append(r)

    # 排序：保留重复项，仅排序（你要求不要去重）
    for m, items in by.items():
        items.sort(key=lambda x: (x["asin"], x["title"], x["link"], x["image"]))
    return by

def svg_whatsapp() -> str:
    # 简洁 WhatsApp 图标（SVG）
    return """<svg viewBox="0 0 32 32" aria-hidden="true">
<path d="M19.11 17.41c-.2-.1-1.2-.59-1.38-.66-.18-.07-.31-.1-.44.1-.13.2-.5.66-.62.79-.11.13-.22.15-.42.05-.2-.1-.85-.31-1.62-.99-.6-.54-1-1.2-1.11-1.4-.11-.2-.01-.31.09-.41.09-.09.2-.22.31-.33.1-.11.13-.2.2-.33.07-.13.03-.25-.02-.35-.05-.1-.44-1.06-.6-1.45-.16-.38-.32-.33-.44-.33h-.38c-.13 0-.35.05-.53.25-.18.2-.7.68-.7 1.67s.72 1.95.82 2.09c.1.13 1.41 2.15 3.41 3.01.48.21.86.33 1.15.42.48.15.92.13 1.27.08.39-.06 1.2-.49 1.37-.97.17-.48.17-.89.12-.97-.05-.08-.18-.13-.38-.23z"/>
<path d="M16 3C8.83 3 3 8.83 3 16c0 2.53.72 4.89 1.97 6.89L3 29l6.28-1.9A12.94 12.94 0 0 0 16 29c7.17 0 13-5.83 13-13S23.17 3 16 3zm0 23.5c-2.1 0-4.04-.62-5.67-1.68l-.4-.25-3.73 1.13 1.2-3.63-.26-.42A10.44 10.44 0 0 1 5.5 16C5.5 10.21 10.21 5.5 16 5.5S26.5 10.21 26.5 16 21.79 26.5 16 26.5z"/>
</svg>"""

def svg_telegram() -> str:
    return """<svg viewBox="0 0 32 32" aria-hidden="true">
<path d="M28.5 6.1 24.6 26c-.3 1.4-1.1 1.7-2.2 1.1l-6.1-4.5-3 2.9c-.3.3-.6.6-1.2.6l.4-6.4 11.7-10.6c.5-.4-.1-.7-.8-.3L8.9 18.1l-6.2-1.9c-1.3-.4-1.4-1.3.3-1.9L26.9 5c1.1-.4 2 .3 1.6 1.1z"/>
</svg>"""

def page_shell(title: str, nav_html: str, body_html: str, updated_at: str) -> str:
    css = """
:root{--bg:#0b0f17;--card:#111827;--muted:#9ca3af;--text:#e5e7eb;--line:#1f2937;--accent:#22c55e}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,"PingFang SC","Microsoft Yahei",sans-serif;background:linear-gradient(180deg,#0b0f17,#070a10);color:var(--text)}
a{color:inherit;text-decoration:none}
.container{max-width:1120px;margin:0 auto;padding:18px}
.header{position:sticky;top:0;z-index:20;background:rgba(11,15,23,.78);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hrow{display:flex;align-items:center;justify-content:space-between;gap:12px}
.brand{font-weight:700;letter-spacing:.2px}
.sub{color:var(--muted);font-size:12px;margin-top:2px}
.actions{display:flex;align-items:center;gap:10px}
.iconbtn{display:inline-flex;align-items:center;gap:8px;padding:10px 12px;border:1px solid var(--line);background:rgba(17,24,39,.65);border-radius:999px}
.icon{width:18px;height:18px;display:inline-block}
.icon svg{width:18px;height:18px;fill:currentColor}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.pill{padding:8px 10px;border:1px solid var(--line);border-radius:999px;color:var(--muted);background:rgba(17,24,39,.35)}
.pill.active{color:var(--text);border-color:rgba(34,197,94,.5);box-shadow:0 0 0 2px rgba(34,197,94,.12) inset}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}
@media (max-width: 980px){.grid{grid-template-columns:repeat(3,1fr)}}
@media (max-width: 720px){.grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width: 420px){.grid{grid-template-columns:1fr}}
.card{border:1px solid var(--line);background:rgba(17,24,39,.55);border-radius:16px;overflow:hidden}
.thumb{aspect-ratio:1/1;background:#0b0f17}
.thumb img{width:100%;height:100%;object-fit:cover;display:block}
.cbody{padding:10px}
.ctitle{font-size:14px;font-weight:650;line-height:1.35;min-height:38px}
.cmeta{margin-top:6px;color:var(--muted);font-size:12px;white-space:pre-line}
.cfoot{display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:8px}
.price{font-weight:700}
.btn{padding:8px 10px;border:1px solid var(--line);border-radius:10px;background:rgba(17,24,39,.35);color:var(--text);font-size:12px}
.footer{margin:18px 0 8px;color:var(--muted);font-size:12px;text-align:center}
"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{safe_html(title)}</title>
<style>{css}</style>
</head>
<body>
<div class="header">
  <div class="container">
    <div class="hrow">
      <div>
        <div class="brand">{safe_html(title)}</div>
        <div class="sub">Updated: {safe_html(updated_at)}</div>
      </div>
      <div class="actions">
        <a class="iconbtn" href="{WA_LINK}" target="_blank" rel="noopener">
          <span class="icon">{svg_whatsapp()}</span>
          <span>WhatsApp</span>
        </a>
        <a class="iconbtn" href="{TG_LINK}" target="_blank" rel="noopener">
          <span class="icon">{svg_telegram()}</span>
          <span>Telegram</span>
        </a>
      </div>
    </div>
    <div class="nav">{nav_html}</div>
  </div>
</div>

<div class="container">
{body_html}
<div class="footer">Contact: WhatsApp / Telegram · Data source: your CSV</div>
</div>
</body>
</html>"""

def build_nav(active_market: str | None) -> str:
    pills = []
    pills.append(f'<a class="pill {"active" if active_market is None else ""}" href="index.html">All</a>')
    for m in MARKETS:
        mm = m.strip().upper()
        name = MARKET_NAMES.get(mm, mm)
        flag = FLAGS.get(mm, "")
        href = f"{mm.lower()}.html"
        pills.append(
            f'<a class="pill {"active" if active_market==mm else ""}" href="{href}">{flag}{safe_html(name)} ({mm})</a>'
        )
    return "\n".join(pills)

def product_grid(items: list[dict]) -> str:
    cards = []
    for it in items:
        cards.append(f"""
<div class="card">
  <div class="thumb"><img src="{safe_html(it["image"])}" alt="{safe_html(it["title"])}" loading="lazy"/></div>
  <div class="cbody">
    <div class="ctitle">{safe_html(it["title"])}</div>
    <div class="cmeta">{safe_html(it["desc"])}</div>
    <div class="cfoot">
      <div class="price">{safe_html(it["price"])}</div>
      <a class="btn" href="{safe_html(it["link"])}" target="_blank" rel="noopener">Open</a>
    </div>
  </div>
</div>
""")
    return f'<div class="grid">\n' + "\n".join(cards) + "\n</div>"

def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    src_rows = read_source_rows()
    mapped = []
    for r in src_rows:
        x = map_row(r)
        if x:
            mapped.append(x)

    by_market = group_by_market(mapped)

    updated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    # 1) index: All Products（合并展示）
    all_items = []
    for m in MARKETS:
        mm = m.strip().upper()
        all_items.extend(by_market.get(mm, []))

    # 合并页排序：按 market 再按 asin
    all_items.sort(key=lambda x: (x["market"], x["asin"], x["title"], x["link"]))

    nav = build_nav(active_market=None)
    body = product_grid(all_items)
    write_file(
        os.path.join(OUT_DIR, "index.html"),
        page_shell("Dalemy · All Products", nav, body, updated_at),
    )

    # 2) 每个国家单独页面
    for m in MARKETS:
        mm = m.strip().upper()
        items = by_market.get(mm, [])
        navm = build_nav(active_market=mm)
        title = f"Dalemy · {FLAGS.get(mm,'')}{MARKET_NAMES.get(mm,mm)} ({mm})"
        bodym = product_grid(items)
        write_file(
            os.path.join(OUT_DIR, f"{mm.lower()}.html"),
            page_shell(title, navm, bodym, updated_at),
        )

    print(f"done: total={len(mapped)}; by_market={{" + ", ".join(f"{k}:{len(v)}" for k,v in by_market.items()) + "}}")

if __name__ == "__main__":
    main()
