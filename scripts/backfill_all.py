import json
import os
import time
import random
import urllib.parse
import urllib.request
from datetime import datetime, date

LATEST_FILE = "data/latest.json"
HISTORY_DIR = "data/stock_history"

BATCH_SIZE = 10
MONTHS = 12
MIN_DAYS = 200

os.makedirs(HISTORY_DIR, exist_ok=True)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_date(value):
    text = str(value).strip()

    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").date()

    if "/" in text:
        y, m, d = map(int, text.split("/"))
        if y < 1911:
            y += 1911
        return date(y, m, d)

    if text.isdigit():
        if len(text) == 7:
            return date(
                int(text[:3]) + 1911,
                int(text[3:5]),
                int(text[5:7])
            )

        if len(text) == 8:
            return date(
                int(text[:4]),
                int(text[4:6]),
                int(text[6:8])
            )

    raise ValueError(f"日期格式不支援：{value}")


def get_months(count):
    today = date.today()
    months = []

    for i in range(count):
        total = today.year * 12 + today.month - 1 - i
        year = total // 12
        month = total % 12 + 1
        months.append(f"{year}{month:02d}01")

    return list(reversed(months))


def fetch_month(code, month):
    params = urllib.parse.urlencode({
        "response": "json",
        "date": month,
        "stockNo": code
    })

    url = (
        "https://www.twse.com.tw/exchangeReport/STOCK_DAY?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("stat") != "OK":
        raise RuntimeError(
            f"{code} {month}: {result.get('stat')}"
        )

    rows = []

    for item in result.get("data", []):
        try:
            trading_date = parse_date(item[0]).isoformat()
            close = float(
                str(item[6]).replace(",", "")
            )

            rows.append({
                "date": trading_date,
                "close": close
            })

        except (ValueError, IndexError, TypeError):
            continue

    return rows


def load_history(code):
    path = os.path.join(HISTORY_DIR, f"{code}.json")

    if not os.path.exists(path):
        return [], path

    existing = read_json(path)

    if isinstance(existing, list):
        return existing, path

    if isinstance(existing, dict):
        for key in ("history", "prices", "data"):
            if isinstance(existing.get(key), list):
                return existing[key], path

    raise ValueError(
        f"{code} 的歷史資料格式不支援，請先檢查"
    )


def main():
    latest = read_json(LATEST_FILE)
    stocks = latest.get("stocks", [])

    months = get_months(MONTHS)

    completed = 0
    skipped = 0
    failed = 0

    print(f"找到 {len(stocks)} 檔股票")
    print(f"本次最多回補 {BATCH_SIZE} 檔")

    for stock in stocks:
        code = str(stock.get("code", "")).strip()

        if not code or not code.isdigit():
            continue

        try:
            history, path = load_history(code)

            if len(history) >= MIN_DAYS:
                skipped += 1
                continue

            if completed + failed >= BATCH_SIZE:
                break

            print(f"開始回補 {code}")

            merged = {}

            for row in history:
                if isinstance(row, dict) and row.get("date"):
                    merged[str(row["date"])] = row

            for month in months:
                try:
                    rows = fetch_month(code, month)

                    for row in rows:
                        merged[row["date"]] = row

                    print(
                        f"  {month[:6]}：{len(rows)} 筆"
                    )

                except Exception as error:
                    print(f"  {month[:6]} 失敗：{error}")

                time.sleep(random.uniform(1.5, 3.0))

            result = [
                merged[key]
                for key in sorted(merged)
            ]

            if len(result) >= 60:
                save_json(path, result)
                completed += 1
                print(
                    f"完成 {code}：{len(result)} 個交易日"
                )
            else:
                failed += 1
                print(
                    f"略過 {code}：只有 {len(result)} 筆"
                )

        except Exception as error:
            failed += 1
            print(f"{code} 發生錯誤：{error}")

    print("========== 回補結果 ==========")
    print(f"成功：{completed} 檔")
    print(f"已有足夠資料：{skipped} 檔")
    print(f"未完成：{failed} 檔")


if __name__ == "__main__":
    main()
