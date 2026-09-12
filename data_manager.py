import time
import requests
import pandas as pd

USD_M_URL = "https://fapi.binance.com/fapi/v1/klines"
COIN_M_URL = "https://dapi.binance.com/dapi/v1/klines"


def fetch_klines(symbol, interval, start_date, end_date=None, limit=1000, market_type=None):
    start_ms = int(pd.Timestamp(start_date, tz="UTC").timestamp() * 1000)
    end_ms = None
    if end_date:
        end_ms = int(pd.Timestamp(end_date, tz="UTC").timestamp() * 1000)

    rows = []
    if market_type is None:
        market_type = "COIN_M" if symbol.endswith("_PERP") or symbol.endswith("_PERP".upper()) else "USD_M"
    url = COIN_M_URL if market_type == "COIN_M" else USD_M_URL
    while True:
        params = {"symbol": symbol, "interval": interval, "limit": limit, "startTime": start_ms}
        if end_ms is not None:
            params["endTime"] = end_ms

        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        rows.extend(data)

        last_open_time = data[-1][0]
        next_start = last_open_time + 1
        if len(data) < limit or (end_ms is not None and last_open_time >= end_ms):
            break
        if next_start <= start_ms:
            break
        start_ms = next_start
        time.sleep(0.15)

    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        raise RuntimeError(f"No Binance Futures data returned for {symbol}.")

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    numeric = ["open", "high", "low", "close", "volume", "quote_volume"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    if end_date:
        end_ts = pd.Timestamp(end_date, tz="UTC")
        df = df[df["open_time"] < end_ts].reset_index(drop=True)
    return df
