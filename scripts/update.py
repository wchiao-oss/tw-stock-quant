import json
import urllib.request
import datetime
import pathlib

URL = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'

req = urllib.request.Request(
    URL,
    headers={'User-Agent': 'Mozilla/5.0 (personal research dashboard)'}
)

with urllib.request.urlopen(req, timeout=45) as r:
    rows = json.load(r)

if not isinstance(rows, list) or len(rows) < 100:
    raise RuntimeError('Unexpected TWSE response; preserving prior data')

def num(v):
    try:
        return float(str(v).replace(',', '').replace('+', ''))
    except (TypeError, ValueError):
        return None

items = []

for r in rows:
    code = str(r.get('Code', '')).strip()

    if not (len(code) == 4 and code.isdigit()):
        continue

    items.append({
        'code': code,
        'name': r.get('Name', ''),
        'date': r.get('Date', ''),
        'close': num(r.get('ClosingPrice')),
        'change': num(r.get('Change')),
        'volume_shares': num(r.get('TradeVolume')),
        'turnover_twd': num(r.get('TradeValue'))
    })

if len(items) < 100:
    raise RuntimeError('Too few stock rows; preserving prior data')

output = {
    'source': 'TWSE STOCK_DAY_ALL',
    'fetched_at_utc': datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(),
    'market': 'TWSE listed (EOD)',
    'stocks': items
}

path = pathlib.Path('data/latest.json')
path.parent.mkdir(exist_ok=True)

path.write_text(
    json.dumps(output, ensure_ascii=False, separators=(',', ':')),
    encoding='utf-8'
)

print(f'Wrote {len(items)} listed securities')
# ===== 儲存每日歷史股價 =====

# 使用證交所提供的交易日期，不使用執行日期
trade_date = str(items[0]['date'])

# 檢查所有股票是否屬於同一交易日
if not all(str(stock['date']) == trade_date for stock in items):
    raise RuntimeError('Inconsistent trading dates')

# 建立歷史資料夾
history_dir = pathlib.Path('data/history')
history_dir.mkdir(parents=True, exist_ok=True)

# 每個交易日儲存一個 JSON 檔案
history_file = history_dir / f'{trade_date}.json'

history_file.write_text(
    json.dumps(output, ensure_ascii=False, separators=(',', ':')),
    encoding='utf-8'
)

print(f'Saved historical data: {history_file}')
