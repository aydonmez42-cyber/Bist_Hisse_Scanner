"""
Pine Script v6 yerlesik fonksiyonlarinin bire bir Python karsiliklari.

Amac: TradingView'de gordugunuz degerlerin aynisini uretmek. Bu yuzden
Wilder yumusatmasi (RMA), ta.dev, ta.linreg, ta.sar gibi fonksiyonlar
TradingView referans kodlarina sadik kalinarak yazildi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- ortalamalar

def sma(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).mean()


def ema(src: pd.Series, length: int) -> pd.Series:
    return src.ewm(span=length, adjust=False).mean()


def rma(src: pd.Series, length: int) -> pd.Series:
    """Wilder yumusatmasi. ta.rsi, ta.atr, ta.dmi bunu kullanir."""
    return src.ewm(alpha=1.0 / length, adjust=False).mean()


def wma(src: pd.Series, length: int) -> pd.Series:
    w = np.arange(1, length + 1, dtype=float)
    return src.rolling(length, min_periods=length).apply(
        lambda x: np.dot(x, w) / w.sum(), raw=True
    )


def highest(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).max()


def lowest(src: pd.Series, length: int) -> pd.Series:
    return src.rolling(length, min_periods=length).min()


def stdev(src: pd.Series, length: int) -> pd.Series:
    """Pine'in ta.stdev'i populasyon standart sapmasidir (ddof=0)."""
    return src.rolling(length, min_periods=length).std(ddof=0)


def dev(src: pd.Series, length: int) -> pd.Series:
    """ta.dev - ortalamadan ortalama mutlak sapma. ta.cci icinde kullanilir."""
    return src.rolling(length, min_periods=length).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )


# ------------------------------------------------------------------ osilator

def rsi(src: pd.Series, length: int = 14) -> pd.Series:
    delta = src.diff()
    up = rma(delta.clip(lower=0.0), length)
    down = rma((-delta).clip(lower=0.0), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / down
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(down != 0, 100.0)
    out = out.where(up != 0, 0.0)
    return out


def stoch(src: pd.Series, high_s: pd.Series, low_s: pd.Series, length: int) -> pd.Series:
    hh = highest(high_s, length)
    ll = lowest(low_s, length)
    rng = (hh - ll).replace(0.0, np.nan)
    return (100.0 * (src - ll) / rng).fillna(50.0)


def cci(src: pd.Series, length: int) -> pd.Series:
    ma = sma(src, length)
    return (src - ma) / (0.015 * dev(src, length))


def true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = (h.iloc[0] - l.iloc[0]) if len(h) else np.nan
    return tr


def atr(h: pd.Series, l: pd.Series, c: pd.Series, length: int) -> pd.Series:
    return rma(true_range(h, l, c), length)


def dmi(h: pd.Series, l: pd.Series, c: pd.Series, di_len: int = 14, adx_len: int = 14):
    """ta.dmi(14, 14) -> (+DI, -DI, ADX)"""
    up = h.diff()
    down = -l.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    trur = rma(true_range(h, l, c), di_len)
    plus = 100.0 * rma(pd.Series(plus_dm, index=h.index), di_len) / trur
    minus = 100.0 * rma(pd.Series(minus_dm, index=h.index), di_len) / trur
    total = (plus + minus).replace(0.0, 1.0)
    adx = 100.0 * rma((plus - minus).abs() / total, adx_len)
    return plus, minus, adx


def obv(c: pd.Series, v: pd.Series) -> pd.Series:
    direction = np.sign(c.diff().fillna(0.0))
    return (direction * v).cumsum()


def linreg(src: pd.Series, length: int, offset: int = 0) -> pd.Series:
    """
    ta.linreg - dogrusal regresyon dogrusunun son bardaki degeri.
    Sonuc y degerlerinin sabit agirlikli toplami oldugu icin tek konvolusyonla
    hesaplanir; 600 hisse taramasinda polyfit'ten cok daha hizli.
    """
    n = length
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    sxx = ((x - x_mean) ** 2).sum()
    x_target = (n - 1 - offset) - x_mean
    weights = 1.0 / n + (x - x_mean) * x_target / sxx
    return src.rolling(n, min_periods=n).apply(lambda y: float(np.dot(y, weights)), raw=True)


def sar(h: pd.Series, l: pd.Series, c: pd.Series,
        start: float = 0.02, inc: float = 0.02, maximum: float = 0.2) -> pd.Series:
    """ta.sar - TradingView'in yayinladigi referans uygulamasinin birebir cevirisi."""
    high = h.to_numpy(dtype=float)
    low = l.to_numpy(dtype=float)
    close = c.to_numpy(dtype=float)
    n = len(high)
    out = np.full(n, np.nan)
    if n < 3:
        return pd.Series(out, index=h.index)

    result = max_min = accel = np.nan
    is_below = True

    for i in range(1, n):
        is_first = False
        if i == 1:
            if close[1] > close[0]:
                is_below, max_min, result = True, high[1], low[0]
            else:
                is_below, max_min, result = False, low[1], high[0]
            is_first, accel = True, start

        result = result + accel * (max_min - result)

        if is_below:
            if result > low[i]:
                is_first, is_below = True, False
                result = max(high[i], max_min)
                max_min, accel = low[i], start
        else:
            if result < high[i]:
                is_first, is_below = True, True
                result = min(low[i], max_min)
                max_min, accel = high[i], start

        if not is_first:
            if is_below:
                if high[i] > max_min:
                    max_min = high[i]
                    accel = min(accel + inc, maximum)
            else:
                if low[i] < max_min:
                    max_min = low[i]
                    accel = min(accel + inc, maximum)

        if is_below:
            result = min(result, low[i - 1])
            if i > 1:
                result = min(result, low[i - 2])
        else:
            result = max(result, high[i - 1])
            if i > 1:
                result = max(result, high[i - 2])

        out[i] = result

    return pd.Series(out, index=h.index)


def crossover(a: pd.Series, b) -> pd.Series:
    b = pd.Series(b, index=a.index) if np.isscalar(b) else b
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b) -> pd.Series:
    b = pd.Series(b, index=a.index) if np.isscalar(b) else b
    return (a < b) & (a.shift(1) >= b.shift(1))
