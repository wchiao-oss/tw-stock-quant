import json
import os
import time
import random
import urllib.parse
import urllib.request
from datetime import datetime, date

LATEST_FILE = "data/latest.json"
HISTORY_DIR = "data/stock_history"

# 每次最多回補 30 檔
BATCH_SIZE = 30

# 回補最近 12 個月份
MONTHS = 12

# 已有 200 個交易日就跳過
MIN_DAYS = 200

# 預留時間給 GitHub 提交資料
MAX_RUNTIME_SECONDS = 900

os.makedirs(HISTORY_DIR, exist_ok=True)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    temp_path = path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    os.replace(temp_path, path)


def parse_date(value):
    text = str(value).strip()

    if "-" in text:
        return datetime.strptime(
            text,
            "%Y-%m-%d"
        ).date()

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

    raise ValueError(
        f"日期格式不支援：{value}"
    )


def get_months(count):
    today = date.today()
    months = []

    for i in range(count):

        total = (
            today.year * 12
            + today.month
            - 1
            - i
        )

        year = total // 12
        month = total % 12 + 1

        months.append(
            f"{year}{month:02d}01"
        )

    return list(reversed(months))


def fetch_month(code, month):
    params = urllib.parse.urlencode({
        "response": "json",
        "date": month,
        "stockNo": code
    })

    url = (
        "https://www.twse.com.tw/"
        "exchangeReport/STOCK_DAY?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        result = json.load(response)

    if result.get("stat") != "OK":
        raise RuntimeError(
            f"{code} {month}: "
            f"{result.get('stat')}"
        )

    rows = []

    for item in result.get("data", []):

        try:
            trading_date = parse_date(
                item[0]
            ).isoformat()

            close = float(
                str(item[6]).replace(",", "")
            )

            if close <= 0:
                continue

            rows.append({
                "date": trading_date,
                "close": close
            })

        except (
            ValueError,
            IndexError,
            TypeError
        ):
            continue

    return rows


def load_history(code):
    path = os.path.join(
        HISTORY_DIR,
        f"{code}.json"
    )

    if not os.path.exists(path):
        return [], path

    existing = read_json(path)

    if isinstance(existing, dict):

        if str(
            existing.get("stock_id", code)
        ) != code:
            raise ValueError(
                "股票代碼不一致"
            )

        prices = existing.get("prices")

        if isinstance(prices, list):
            return prices, path

        raise ValueError(
            "原有資料缺少 prices 欄位"
        )

    raise ValueError(
        "原有歷史資料不是預期格式，"
        "為保護資料已停止處理"
    )


def main():
    start_time = time.monotonic()

    latest = read_json(LATEST_FILE)
    stocks = latest.get("stocks", [])
    months = get_months(MONTHS)

    completed = 0
    skipped = 0
    failed = 0
    attempted = 0

    print(
        f"找到 {len(stocks)} 檔股票",
        flush=True
    )

    print(
        f"本次最多處理 {BATCH_SIZE} 檔",
        flush=True
    )

    for stock in stocks:

        elapsed = (
            time.monotonic() - start_time
        )

        if elapsed >= MAX_RUNTIME_SECONDS:
            print(
                "接近時間限制，"
                "本批提前結束",
                flush=True
            )
            break

        code = str(
            stock.get("code", "")
        ).strip()

        if not code or not code.isdigit():
            continue

        try:
            history, path = load_history(code)

            merged = {}

            for row in history:

                if not isinstance(row, dict):
                    continue

                try:
                    day = parse_date(
                        row["date"]
                    ).isoformat()

                    close = float(
                        row["close"]
                    )

                    if close > 0:
                        merged[day] = {
                            "date": day,
                            "close": close
                        }

                except (
                    KeyError,
                    ValueError,
                    TypeError
                ):
                    continue

            if len(merged) >= MIN_DAYS:
                skipped += 1
                continue

            if attempted >= BATCH_SIZE:
                break

            attempted += 1

            print(
                f"開始回補 {code}",
                flush=True
            )

            fetched_months = 0

            for month in months:

                elapsed = (
                    time.monotonic()
                    - start_time
                )

                if (
                    elapsed
                    >= MAX_RUNTIME_SECONDS
                ):
                    print(
                        "接近時間限制，"
                        "儲存目前進度",
                        flush=True
                    )
                    break

                try:
                    rows = fetch_month(
                        code,
                        month
                    )

                    for row in rows:
                        merged[
                            row["date"]
                        ] = row

                    fetched_months += 1

                    print(
                        f"  {month[:6]}："
                        f"{len(rows)} 筆",
                        flush=True
                    )

                except Exception as error:
                    print(
                        f"  {month[:6]} "
                        f"失敗：{error}",
                        flush=True
                    )

                time.sleep(
                    random.uniform(
                        1.5,
                        3.0
                    )
                )

            result = [
                merged[key]
                for key in sorted(merged)
            ]

            if (
                len(result) >= 60
                and fetched_months > 0
            ):

                save_json(
                    path,
                    {
                        "stock_id": code,
                        "prices": result
                    }
                )

                completed += 1

                print(
                    f"完成 {code}："
                    f"{len(result)} "
                    "個交易日",
                    flush=True
                )

            else:
                failed += 1

                print(
                    f"未完成 {code}："
                    f"{len(result)} 筆，"
                    f"成功取得 "
                    f"{fetched_months} "
                    "個月份",
                    flush=True
                )

        except Exception as error:
            failed += 1

            print(
                f"{code} 發生錯誤："
                f"{error}",
                flush=True
            )

    print(
        "========== 回補結果 ==========",
        flush=True
    )

    print(
        f"成功：{completed} 檔",
        flush=True
    )

    print(
        f"已有足夠資料：{skipped} 檔",
        flush=True
    )

    print(
        f"未完成：{failed} 檔",
        flush=True
    )

    print(
        f"本次實際處理：{attempted} 檔",
        flush=True
    )


if __name__ == "__main__":
    main()
