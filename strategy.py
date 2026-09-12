import pandas as pd

def recent_true(series, current_pos, max_bars):
    start = max(0, current_pos - max_bars + 1)
    window = series.iloc[start:current_pos + 1]
    return bool(window.fillna(False).any())


def long_signal(df, i, cfg):
    row = df.iloc[i]

    if i < 1:
        return False

    # EMA50/EMA200 define the main trend regime; Supertrend is the trend filter.
    if not (row["close"] > row["ema100"]):
        return False
    if not (row["ema50"] > row["ema100"]):
        return False
    if not (row["adx"] > cfg.ADX_THRESHOLD):
        return False
    if not bool(row["supertrend_bullish"]):
        return False
    if not (row["rsi"] > cfg.RSI_LONG_THRESHOLD):
        return False
    if cfg.USE_MACD_LONG_FILTER and not bool(row["macd_long_ok"]):
        return False

    if not recent_true(
        df["cci"] > cfg.CCI_LONG_THRESHOLD, i, cfg.CCI_VALID_BARS
    ):
        return False

    if not recent_true(
        df["stoch_bull_cross"], i, cfg.STOCH_VALID_BARS
    ):
        return False

    if not (row["stoch_d"] > cfg.STOCH_LONG_D_THRESHOLD):
        return False

    return True


def short_signal(df, i, cfg):
    row = df.iloc[i]

    if i < 1:
        return False

    if not (row["close"] < row["ema100"]):
        return False
    if not (row["ema50"] < row["ema100"]):
        return False
    if not (row["adx"] > cfg.ADX_THRESHOLD):
        return False
    if not bool(row["supertrend_bearish"]):
        return False
    if not (row["rsi"] < cfg.RSI_SHORT_THRESHOLD):
        return False

    # Bollinger short filter disabled for this test.
    # 
    if cfg.USE_BB_SHORT_FILTER and not bool(row["bb_short_reentry"]):
        return False

    if not recent_true(
        df["cci"] < cfg.CCI_SHORT_THRESHOLD, i, cfg.CCI_VALID_BARS
    ):
        return False

    if not recent_true(
        df["stoch_bear_cross"], i, cfg.STOCH_VALID_BARS
    ):
        return False

    if not (row["stoch_k"] < cfg.STOCH_SHORT_THRESHOLD):
        return False

    return True


def exit_signal(position, row):
    if position == "LONG":
        return row["close"] < row["ema100"]
    if position == "SHORT":
        return row["close"] > row["ema100"]
    return False
