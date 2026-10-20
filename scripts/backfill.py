import json
import pathlib
import datetime

# 資料夾設定
DATA_DIR = pathlib.Path("data")
HISTORY_DIR = DATA_DIR / "history"
LATEST_FILE = DATA_DIR / "latest.json"

HISTORY_DIR.mkdir(parents=True, exist_ok=True)

# 讀取最新股價資料
if not LATEST_FILE.exists():
    raise FileNotFoundError(
        "找不到 data/latest.json，請先執行 update.py"
    )

with LATEST_FILE.open("r", encoding="utf-8") as f:
    data = json.load(f)

stocks = data.get("stocks", [])

if not stocks:
    raise ValueError("沒有找到股票資料")

# 取得交易所提供的交易日期
trade_date = str(stocks[0].get("date", ""))

if not trade_date:
    raise ValueError("找不到交易日期")

# 確認所有股票屬於同一交易日
if not all(
    str(stock.get("date", "")) == trade_date
    for stock in stocks
):
    raise ValueError("股票交易日期不一致")

# 建立歷史資料檔案
history_file = HISTORY_DIR / f"{trade_date}.json"

# 避免覆蓋已經儲存的歷史資料
if history_file.exists():
    print(f"歷史資料已存在：{history_file}")
else:
    with history_file.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    print(f"成功儲存歷史股價：{history_file}")
    print(f"股票數量：{len(stocks)}")
