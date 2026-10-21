import json
import time
import pathlib
import datetime
import urllib.request
import urllib.parse

# 測試股票
STOCKS = ["2330", "2317", "2454"]

# 歷史資料儲存位置
OUTPUT = pathlib.Path("data/stock_history")
OUTPUT.mkdir(parents=True, exist_ok=True)

# 以今天為基準，回補過去一年
today = datetime.date.today()
start = today - datetime.timedelta(days=365)


def fetch_month(stock_id, year, month):
    date_str = f"{year}{month:02d}01"

    params = urllib.parse.urlencode({
        "response": "json",
        "date": date_str,
        "stockNo": stock_id
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
        return json.load(response)


def parse_number(value):
    value = str(value).replace(",", "").strip()

    if value in ["", "--", "---", "X", "除權息"]:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def parse_date(roc_date):
    year, month, day = map(int, roc_date.split("/"))
    return datetime.date(year + 1911, month, day)


def month_range(start_date, end_date):
    year = start_date.year
    month = start_date.month

    while (year, month) <= (end_date.year, end_date.month):
        yield year, month

        month += 1

        if month > 12:
            month = 1
            year += 1


for stock_id in STOCKS:
    records = {}

    print(f"開始下載 {stock_id}")

    for year, month in month_range(start, today):
        try:
            result = fetch_month(stock_id, year, month)

            if result.get("stat") != "OK":
                print(f"{stock_id} {year}/{month}: 無資料")
                continue

            for row in result.get("data", []):
                trade_date = parse_date(row[0])

                if not start <= trade_date <= today:
                    continue

                close = parse_number(row[6])

                if close is None:
                    continue

                records[trade_date.isoformat()] = {
                    "date": trade_date.isoformat(),
                    "open": parse_number(row[3]),
                    "high": parse_number(row[4]),
                    "low": parse_number(row[5]),
                    "close": close,
                    "volume_shares": parse_number(row[1]),
                    "turnover_twd": parse_number(row[2])
                }

            print(f"{stock_id} {year}/{month}: 完成")

        except Exception as error:
            print(f"{stock_id} {year}/{month}: 失敗 {error}")

        # 降低請求頻率，避免造成交易所負擔
        time.sleep(3)

    if not records:
        print(f"{stock_id}: 沒有成功取得資料")
        continue

    output_file = OUTPUT / f"{stock_id}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "stock_id": stock_id,
                "source": "TWSE STOCK_DAY",
                "prices": [
                    records[key] for key in sorted(records)
                ]
            },
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"{stock_id}: 已儲存 {len(records)} 筆交易日資料")

print("歷史股價測試下載完成")
