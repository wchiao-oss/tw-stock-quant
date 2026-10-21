import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 資料位置
INPUT_DIR = Path("data/stock_history")
OUTPUT_FILE = Path("data/indicators.json")


def sma(values, period):
    """簡單移動平均線"""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def bollinger(values, period=20, multiplier=2):
    """布林通道：中軌、上軌、下軌"""
    if len(values) < period:
        return None

    recent = values[-period:]
    middle = sum(recent) / period

    variance = sum(
        (price - middle) ** 2 for price in recent
    ) / period

    std = math.sqrt(variance)

    return {
        "upper": round(middle + multiplier * std, 4),
        "middle": round(middle, 4),
        "lower": round(middle - multiplier * std, 4),
    }


def rsi(values, period=14):
    """RSI：使用 Wilder 平滑算法"""
    if len(values) < period + 1:
        return None

    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (
            avg_gain * (period - 1) + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1) + losses[i]
        ) / period

    if avg_gain == 0 and avg_loss == 0:
        return 50.0

    if avg_loss == 0:
        return 100.0

    if avg_gain == 0:
        return 0.0

    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 4)


def calculate_stock(file_path):
    """讀取單一股票歷史資料並計算指標"""
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    stock_id = str(data.get("stock_id", file_path.stem))
    prices = data.get("prices", [])

    valid_prices = []

    for row in prices:
        try:
            close = float(row["close"])
            date = str(row["date"])

            if not math.isfinite(close) or close <= 0:
                continue

            valid_prices.append({
                "date": date,
                "close": close,
            })
        except (KeyError, ValueError, TypeError):
            continue

    # 依日期排序，避免指標計算順序錯誤
    valid_prices.sort(key=lambda row: row["date"])

    # 同一天只保留一筆
    by_date = {
        row["date"]: row
        for row in valid_prices
    }

    valid_prices = [
        by_date[date]
        for date in sorted(by_date)
    ]

    closes = [row["close"] for row in valid_prices]

    if len(closes) < 60:
        print(f"略過 {stock_id}：不足 60 個交易日")
        return None

    bb = bollinger(closes)

    result = {
        "stock_id": stock_id,
        "date": valid_prices[-1]["date"],
        "trading_days": len(closes),
        "close": closes[-1],
        "ma20": round(sma(closes, 20), 4),
        "ma60": round(sma(closes, 60), 4),
        "rsi6": rsi(closes, 6),
        "rsi14": rsi(closes, 14),
        "bollinger": bb,
    }

    # 常用的布林與均線條件
    result["signals"] = {
        "above_upper": closes[-1] > bb["upper"],
        "below_lower": closes[-1] < bb["lower"],
        "above_ma20": closes[-1] > result["ma20"],
        "above_ma60": closes[-1] > result["ma60"],
        "rsi6_below_20": result["rsi6"] < 20,
        "rsi6_above_80": result["rsi6"] > 80,
        "rsi14_below_20": result["rsi14"] < 20,
        "rsi14_above_80": result["rsi14"] > 80,
    }

    return result


def main():
    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"找不到歷史資料資料夾：{INPUT_DIR}"
        )

    results = {}

    for file_path in sorted(INPUT_DIR.glob("*.json")):
        result = calculate_stock(file_path)

        if result is not None:
            results[result["stock_id"]] = result
            print(
                f"完成 {result['stock_id']}："
                f"{result['trading_days']} 個交易日"
            )

    if not results:
        raise RuntimeError("沒有足夠的歷史資料可計算")

    taiwan_time = timezone(timedelta(hours=8))

    output = {
        "generated_at": datetime.now(
            taiwan_time
        ).isoformat(),
        "stocks": results,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"成功產生：{OUTPUT_FILE}")
    print(f"股票數量：{len(results)}")


if __name__ == "__main__":
    main()
