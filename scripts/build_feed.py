import csv
import io
import os
import re
import hashlib
from decimal import Decimal, InvalidOperation
import requests

# ======================
# Config
# ======================
EXPORT_URL = os.getenv(
    "EXPORT_URL",
    "http://154.48.226.95:5001/admin/Product/export_csv",
)

# 你的源 CSV 价格列名已确认
PRICE_COL = "Discount Price"

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

# Meta Feed 输出字段（加入 item_group_id 便于归组）
OUT_FIELDS = [
    "id",
    "item_group_id",
    "title",
    "description",
    "availability",
    "condition",
    "price",
    "link",
    "image_link",
    "brand",
]

# ======================
# Helpers
# ======================
def parse_price(v) -> Decimal | None:
    """
    允许输入：'0', '0.00', '¥99', '$19.99', '19.99 USD' 等
    仅抽取第一个数字。
    """
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except (InvalidOperation, ValueError):
        return None


def normalize_market(market: str) -> str:
    m = (market or "").strip().upper()
    # 可按你需要补充别名映射
    return m


def normalize_asin(asin: str) -> str:
    return (asin or "").strip().upper()


def stable_unique_id(
    base_id: str,
    store: str,
    keyword: str,
    remark: str,
    link: str,
    image_url: str,
    commission: str,
    status: str,
) -> str:
    """
    生成稳定且唯一的 id（同一行内容每次生成都一致）。
    你要求“重复项保留”，所以不能让 id 重复；用哈希后缀区分每一行。
    """
    raw = "|".join(
        [
            base_id,
            (store or "").strip(),
            (keyword or "").strip(),
            (remark or "").strip(),
            (link or "").strip(),
            (image_url or "").strip(),
            (commission or "").strip(),
            (status or "").strip(),
        ]
    )
    suffix = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{base_id}_{suffix}"


def build_rows(src_rows: list[dict]) -> list[dict]:
    out: list[dict] = []

    for src in src_rows:
        market = normalize_market(src.get("market"))
        asin = normalize_asin(src.get("asin"))

        title = (src.get("title") or "").strip()
        keyword = (src.get("keyword") or "").strip()
        store = (src.get("store") or "").strip()
        remark = (src.get("remark") or "").strip()
        link = (src.get("link") or "").strip()
        image_url = (src.get("image_url") or "").strip()

        commission = (src.get("Commission") or "").strip()
        status = (src.get("status") or "").strip()

        # 基本字段校验：缺关键内容就跳过（否则 Meta 也会报错）
        if not market or not asin or not title or not link or not image_url:
            continue

        currency = CURRENCY_BY_MARKET.get(market, "USD")

        price_raw = src.get(PRICE_COL)
        price = parse_price(price_raw)
        # 你坚持 0 合法：允许 0；如果解析不到，默认 0
        if price is None:
            price = Decimal("0")

        # item_group_id 用于归组（同一 market+asin 的多条记录属于同一组）
        base_id = f"{market}_{asin}"
        unique_id = stable_unique_id(
            base_id=base_id,
            store=store,
            keyword=keyword,
            remark=remark,
            link=link,
            image_url=image_url,
            commission=commission,
            status=status,
        )

        # 标题附加国家标识，方便你在 WhatsApp/目录里搜索
        title2 = f"{title} ({market})"

        # 描述：优先 remark，其次拼 keyword
        # 描述：固定展示 Keyword + Store，其它不变
lines = []
if keyword:
    lines.append(f"Keyword: {keyword}")
if store:
    lines.append(f"Store: {store}")

# 备注仍然保留（不改变你原本 remark 的使用方式）
if remark:
    lines.append(remark)

desc = "\n".join(lines).strip()


        # 这里统一给 in stock/new（你也可以按 status 决定）
        availability = "in stock"
        condition = "new"

        out.append(
            {
                "id": unique_id,
                "item_group_id": base_id,
                "title": title2,
                "description": desc,
                "availability": availability,
                "condition": condition,
                "price": f"{price:.2f} {currency}",
                "link": link,
                "image_link": image_url,
                "brand": store or "Generic",
            }
        )

    # 排序：你想“重复情况下再排序”，这里按组+标题+链接排序（仅影响文件顺序，不影响 Meta 处理逻辑）
    out.sort(key=lambda r: (r["item_group_id"], r["title"], r["link"], r["id"]))
    return out


def write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    r = requests.get(EXPORT_URL, timeout=60)
    r.raise_for_status()

    text = r.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    fieldnames = reader.fieldnames or []
    if PRICE_COL not in fieldnames:
        raise RuntimeError(f"找不到价格列 '{PRICE_COL}'，当前表头: {fieldnames}")

    src_rows = list(reader)
    rows = build_rows(src_rows)

    # 主文件：全国家合并
    write_csv("docs/meta_all.csv", rows)

    # 可选：按 market 拆分（便于你检查）
    by_market: dict[str, list[dict]] = {}
    for row in rows:
        m = row["item_group_id"].split("_", 1)[0]
        by_market.setdefault(m, []).append(row)

    for m, mr in by_market.items():
        write_csv(f"docs/{m.lower()}.csv", mr)

    print(
        f"done: {len(rows)} rows; markets={sorted(by_market.keys())}; "
        f"example_url=docs/meta_all.csv"
    )


if __name__ == "__main__":
    main()
