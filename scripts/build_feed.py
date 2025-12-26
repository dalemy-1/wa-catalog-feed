import csv
import io
import os
import re
import requests
from decimal import Decimal, InvalidOperation

EXPORT_URL = os.getenv("EXPORT_URL", "http://154.48.226.95:5001/admin/Product/export_csv")

# 你说价格以“Discount Price”列为准
PRICE_COL_CANDIDATES = [
    "Discount Price",
    "discount_price",
    "DiscountPrice",
    "Discount",  # 如果你实际表头就是 Discount
]

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

def pick_price_col(fieldnames: list[str]) -> str | None:
    # 精确匹配优先，其次忽略大小写与空格差异
    sset = set(fieldnames)
    for c in PRICE_COL_CANDIDATES:
        if c in sset:
            return c

    norm_map = {re.sub(r"\s+", "", f).lower(): f for f in fieldnames}
    for c in PRICE_COL_CANDIDATES:
        k = re.sub(r"\s+", "", c).lower()
        if k in norm_map:
            return norm_map[k]
    return None

def parse_price(v: str) -> Decimal | None:
    """
    允许输入：'12.34', '12', '¥99', '$19.99', '19.99 USD' 等
    仅抽取数字部分。
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    # 抽取第一个数字（含小数）
    m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", ""))
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except (InvalidOperation, ValueError):
        return None

def build_rows(src_rows: list[dict], price_col: str) -> list[dict]:
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

        price_raw = src.get(price_col)
        price = parse_price(price_raw)

        # ===== 缺价处理策略（二选一） =====
        # 策略A：缺价就跳过（最稳）
        # if price is None:
        #     continue

        # 策略B：缺价默认 0，并标 out of stock（你说“查不到就默认为0”的更稳版本）
        availability = "in stock"
        if price is None:
            price = Decimal("0")
            availability = "out of stock"

        # 标题加国家标识，方便你在 WhatsApp App 里搜索，创建 Collections
        title2 = f"{title} ({market})"

        desc = remark or ""
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

    price_col = pick_price_col(reader.fieldnames or [])
    if not price_col:
        raise RuntimeError(f"找不到价格列。当前表头: {reader.fieldnames}")

    all_rows = build_rows(src_rows, price_col)

    # 主 Feed：全国家合并
    write_csv("docs/meta_all.csv", all_rows)

    # 可选：分国家输出，方便你核对
    by_market: dict[str, list[dict]] = {}
    for row in all_rows:
        m = row["id"].split("_", 1)[0]
        by_market.setdefault(m, []).append(row)
    for m, rows in by_market.items():
        write_csv(f"docs/{m.lower()}.csv", rows)

    print(f"done: {len(all_rows)} rows; price_col={price_col}; markets={sorted(by_market.keys())}")

if __name__ == "__main__":
    main()
