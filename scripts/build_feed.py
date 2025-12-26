import csv
import io
import os
import sys
import requests
from decimal import Decimal, InvalidOperation

EXPORT_URL = os.getenv("EXPORT_URL", "http://154.48.226.95:5001/admin/Product/export_csv")

# 你需要提供一个能公开访问的查价接口（示例：返回 {"price": 12.34}）
# 若你是数据库查询，把 query_price() 改成你自己的逻辑即可
PRICE_URL = os.getenv("PRICE_URL", "http://154.48.226.95:5001/api/price")

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

OUT_FIELDS = [
    "id", "title", "description", "availability", "condition",
    "price", "link", "image_link", "brand"
]

def query_price(market: str, asin: str) -> Decimal | None:
    """按 asin+market 查询价格；查不到返回 None"""
    try:
        r = requests.get(PRICE_URL, params={"market": market, "asin": asin}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        p = data.get("price", None)
        if p is None:
            return None
        return Decimal(str(p))
    except Exception:
        return None

def safe_decimal(s: str) -> Decimal | None:
    try:
        return Decimal(str(s))
    except (InvalidOperation, ValueError):
        return None

def build_rows(src_rows: list[dict]) -> list[dict]:
    out = []
    for src in src_rows:
        market = (src.get("market") or "").strip().upper()
        asin = (src.get("asin") or "").strip()
        title = (src.get("title") or "").strip()
        keyword = (src.get("keyword") or "").strip()
        store = (src.get("store") or "").strip()
        remark = (src.get("remark") or "").strip()
        link = (src.get("link") or "").strip()
        image_url = (src.get("image_url") or "").strip()

        if not market or not asin or not title or not link or not image_url:
            continue

        currency = CURRENCY_BY_MARKET.get(market, "USD")

        # 查价（B：查不到默认 0）
        price = query_price(market, asin)
        availability = "in stock"
        if price is None:
            price = Decimal("0")
            # 建议：查不到价格就 out of stock，减少 0 价带来的导入风险
            availability = "out of stock"

        # 标题加国家标识，便于你在 WhatsApp App 里搜索并创建 Collections
        title2 = f"{title} ({market})"

        desc = remark
        if keyword and keyword not in desc:
            desc = (keyword + " " + desc).strip()

        out.append({
            "id": f"{market}_{asin}",
            "title": title2,
            "description": desc,
            "availability": availability,
            "condition": "new",
            "price": f"{price:.2f} {currency}",
            "link": link,
            "image_link": image_url,
            "brand": store or "Generic",
        })
    return out

def write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main():
    r = requests.get(EXPORT_URL, timeout=30)
    r.raise_for_status()

    text = r.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    src_rows = list(reader)

    all_rows = build_rows(src_rows)
    write_csv("docs/meta_all.csv", all_rows)

    # 可选：按国家输出，便于你检查
    by_market = {}
    for row in all_rows:
        m = row["id"].split("_", 1)[0]
        by_market.setdefault(m, []).append(row)
    for m, rows in by_market.items():
        write_csv(f"docs/{m.lower()}.csv", rows)

    print(f"done: {len(all_rows)} rows, markets={sorted(by_market.keys())}")

if __name__ == "__main__":
    main()
