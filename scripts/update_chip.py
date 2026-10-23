
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# 台灣證券交易所：三大法人買賣超日報
API_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
OUTPUT_FILE = "data/chip_history.json"
TW_TIMEZONE = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

def get_number(value):
    text = str(value).replace(",", "").strip()
    if text in ("", "--", "---", "N/A"):
        return None
    try:
        return int(text)
    except ValueError:
        return None

def find_column(fields, prefix):
    matches = [
        i for i, name in enumerate(fields)
        if str(name).startswith(prefix)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"找不到唯一欄位：{prefix}，找到 {len(matches)} 個"
        )
    return matches[0]

def fetch_day(day):
    params = urllib.parse.urlencode({
        "response": "json",
        "date": day.strftime("%Y%m%d"),
        "selectType": "ALLBUT0999",
    })
    request = urllib.request.Request(
        API_URL + "?" + params,
        headers=HEADERS,
    )

    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.load(response)

    if payload.get("stat") != "OK":
        print(f"{day}: 無資料或非交易日")
        return {}

    fields = payload.get("fields", [])
    rows = payload.get("data", [])

    code_i = find_column(fields, "證券代號")
    foreign_i = find_column(
        fields, "外陸資買賣超股數(不含外資自營商)"
    )
    trust_i = find_column(fields, "投信買賣超股數")

    result = {}
    for row in rows:
        if max(code_i, foreign_i, trust_i) >= len(row):
            continue

        code = str(row[code_i]).strip()
        if not (len(code) == 4 and code.isdigit()):
            continue

        foreign = get_number(row[foreign_i])
        trust = get_number(row[trust_i])

        if foreign is None or trust is None:
            continue

        result[code] = {
            "foreign_net_shares": foreign,
            "trust_net_shares": trust,
        }

    if not result:
        raise ValueError("回傳成功，但沒有解析出任何股票")

    print(f"{day}: 成功取得 {len(result)} 檔法人資料")
    return result

def main():
    today = datetime.now(TW_TIMEZONE).date()

    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = {}

    # 第一次執行回補最近 7 個日曆日
    # 之後每天執行時，仍會補查最近 7 日
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()

        if key in history and history[key]:
            continue

        try:
            records = fetch_day(day)
            if records:
                history[key] = records
        except Exception as exc:
            print(f"{key}: 抓取失敗：{exc}")

        time.sleep(2)

    if not history:
        raise RuntimeError("沒有取得任何法人資料，未建立空檔案")

    os.makedirs("data", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            dict(sorted(history.items())),
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"成功儲存：{OUTPUT_FILE}")
    print(f"累積交易日：{len(history)}")

if __name__ == "__main__":
    main()
