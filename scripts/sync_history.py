import json
from pathlib import Path
from datetime import datetime

# 每日股價資料
LATEST_FILE = Path("data/latest.json")

# 每檔股票的歷史資料
HISTORY_DIR = Path("data/stock_history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def number(value):
    try:
        result = float(str(value).replace(",", ""))
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_date(value):
    """支援西元日期及民國日期"""
    text = str(value).strip()

    if "-" in text:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()

    if "/" in text:
        year, month, day = map(int, text.split("/"))

        if year < 1911:
            year += 1911

        return f"{year:04d}-{month:02d}-{day:02d}"

    raise ValueError(f"無法辨識日期：{text}")


def main():
    if not LATEST_FILE.exists():
        raise FileNotFoundError("找不到 data/latest.json")

    with LATEST_FILE.open("r", encoding="utf-8") as file:
        latest = json.load(file)

    stocks = latest.get("stocks", [])

    if not stocks:
        raise RuntimeError("最新股價資料是空的")

    updated = 0

    for stock in stocks:
        stock_id = str(stock.get("code", "")).strip()

        if not stock_id:
            continue

        close = number(stock.get("close"))

        if close is None:
            continue

        try:
            trade_date = normalize_date(stock.get("date"))
        except (ValueError, TypeError):
            continue

        file_path = HISTORY_DIR / f"{stock_id}.json"

        if file_path.exists():
            with file_path.open("r", encoding="utf-8") as file:
                history = json.load(file)
        else:
            history = {
                "stock_id": stock_id,
                "prices": []
            }

        prices = history.get("prices", [])

        # 相同交易日只保留一筆，避免重複累積
        prices = [
            row for row in prices
            if row.get("date") != trade_date
        ]

        prices.append({
            "date": trade_date,
            "close": close,
            "volume_shares": stock.get("volume_shares"),
            "turnover_twd": stock.get("turnover_twd")
        })

        prices.sort(key=lambda row: row["date"])

        history["stock_id"] = stock_id
        history["prices"] = prices

        with file_path.open("w", encoding="utf-8") as file:
            json.dump(
                history,
                file,
                ensure_ascii=False,
                indent=2
            )

        updated += 1

    print(f"成功同步 {updated} 檔股票的歷史資料")


if __name__ == "__main__":
    main()
