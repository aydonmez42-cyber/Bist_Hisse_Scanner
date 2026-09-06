"""
Global-100 Trade Intelligence indikatorunun sinyal motoru.

Pine kaynagindaki BOLUM 2, 3, 4 ve 4.1 buraya cevrildi:
  - 26 gostergeli SuperBuySell (SBS) skoru
  - Supertrend (ATR 10 x 7.4)
  - YZ AI trend motoru ve ai_score
  - Commodity Trends AI (CCI 30) uzun/kisa sinyalleri
  - Golden / Death bolgesi (EMA50 vs EMA200)

Cikti her bar icin degil, taramanin ihtiyac duydugu son bar icin ozetlenir;
ancak butun seriler DataFrame olarak da doner, boylece gecmis dogrulama
(backtest) yapabilirsiniz.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from . import pine as ta


# 26 gostergenin ekranda gorunecek adlari (Pine'daki detail_names ile ayni sira)
SBS_NAMES = [
    "Supertrend Yonu", "RSI (>50)", "Stochastic RSI (K>D)", "MACD (MACD>Sinyal)",
    "MACD Kesisim", "PPO", "Bollinger Bands", "BB% EMA", "DEMA", "Ichimoku Bulutu",
    "Klinger Osilator (KVO)", "Momentum (10 Bar)", "Awesome Oscillator",
    "Parabolic SAR", "Vortex Indicator", "UT Bot Trend", "Alligator (Gator)",
    "Ultimate Oscillator", "MA Konsensusu (10)", "EMA 365",
    "Golden Zone (EMA50>EMA200)", "ATR Volatilite Artisi", "OBV", "VWAP",
    "ADX / DI Yonu", "Linear Regression (Squeeze)",
]


@dataclass
class Settings:
    """Pine'daki input.* alanlarinin karsiligi. Varsayilanlar indikatorle ayni."""
    min_al_sayisi: int = 17
    min_sat_sayisi: int = 16
    use_gc_filter: bool = True
    ai_sens: int = 25
    cci_len: int = 30
    trail_len: int = 20
    upper: int = 50
    lower: int = -50
    long_threshold: int = 50
    short_threshold: int = -50


# ------------------------------------------------------- ozyinelemeli bloklar

def _supertrend(close: np.ndarray, atr10: np.ndarray, mult: float = 7.4):
    """Pine BOLUM 2 - ATR tabanli takip eden stop ve yon."""
    n = len(close)
    up = close - mult * atr10
    dn = close + mult * atr10
    trend = np.ones(n, dtype=int)

    for i in range(1, n):
        prev_up = up[i - 1] if not np.isnan(up[i - 1]) else up[i]
        prev_dn = dn[i - 1] if not np.isnan(dn[i - 1]) else dn[i]
        if close[i - 1] > prev_up:
            up[i] = max(up[i], prev_up)
        if close[i - 1] < prev_dn:
            dn[i] = min(dn[i], prev_dn)

        t = trend[i - 1]
        if t == -1 and close[i] > prev_dn:
            t = 1
        elif t == 1 and close[i] < prev_up:
            t = -1
        trend[i] = t

    return up, dn, trend


def _ut_bot(close: np.ndarray, nloss: np.ndarray):
    """UT Bot takip eden stop ve pozisyon yonu."""
    n = len(close)
    ts = np.zeros(n)
    pos = np.zeros(n, dtype=int)

    for i in range(1, n):
        prev = ts[i - 1]
        nl = nloss[i] if not np.isnan(nloss[i]) else 0.0
        if close[i] > prev and close[i - 1] > prev:
            ts[i] = max(prev, close[i] - nl)
        elif close[i] < prev and close[i - 1] < prev:
            ts[i] = min(prev, close[i] + nl)
        elif close[i] > prev:
            ts[i] = close[i] - nl
        else:
            ts[i] = close[i] + nl

        if close[i - 1] < prev and close[i] > prev:
            pos[i] = 1
        elif close[i - 1] > prev and close[i] < prev:
            pos[i] = -1
        else:
            pos[i] = pos[i - 1]

    return ts, pos


def _klinger_cm(dm: np.ndarray, trend: np.ndarray) -> np.ndarray:
    """Klinger kumulatif olcumu - yon degisince sifirlanir."""
    n = len(dm)
    cm = np.zeros(n)
    for i in range(1, n):
        cm[i] = dm[i] + (0.0 if trend[i] != trend[i - 1] else cm[i - 1])
    return cm


def _cci_trend(cci: pd.Series, upper: int, lower: int) -> pd.Series:
    """Pine BOLUM 4.1 - CCI esiklerini kirdikca yon tutan durum degiskeni."""
    up_cross = ta.crossover(cci, upper).to_numpy()
    dn_cross = ta.crossunder(cci, lower).to_numpy()
    n = len(cci)
    out = np.full(n, np.nan)
    state = np.nan
    for i in range(n):
        if up_cross[i]:
            state = 1.0
        elif dn_cross[i]:
            state = 0.0
        out[i] = state
    return pd.Series(out, index=cci.index)


# ------------------------------------------------------------- ana hesaplama

def compute(df: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    """
    Girdi: open/high/low/close/volume sutunlari olan, tarihe gore artan DataFrame.
    Cikti: ayni indeksli, tum sinyal sutunlarini iceren DataFrame.
    """
    cfg = cfg or Settings()
    o, h, l, c, v = (df["open"], df["high"], df["low"], df["close"], df["volume"])
    out = pd.DataFrame(index=df.index)

    # --- BOLUM 2: Supertrend -------------------------------------------------
    atr10 = ta.atr(h, l, c, 10)
    st_up, st_dn, st_trend = _supertrend(
        c.to_numpy(float), atr10.to_numpy(float), 7.4
    )
    sbs_trend = pd.Series(st_trend, index=df.index)

    # --- 26 gosterge ---------------------------------------------------------
    rsi_v = ta.rsi(c, 14)
    k_v = ta.sma(ta.stoch(rsi_v, rsi_v, rsi_v, 14), 3)
    d_v = ta.sma(k_v, 3)

    macd_v = ta.ema(c, 12) - ta.ema(c, 26)
    sig_v = ta.ema(macd_v, 9)

    ppo_s, ppo_l = ta.ema(c, 18), ta.ema(c, 24)
    ppo_v = ((ppo_s - ppo_l) / ppo_l) * 100.0

    bb_basis = ta.sma(c, 20)
    bb_sd = ta.stdev(c, 20)
    bbp_e = ta.ema(c, 13)

    de1 = ta.ema(c, 21)
    dema_v = 2 * de1 - ta.ema(de1, 21)

    ich_t = (ta.highest(h, 9) + ta.lowest(l, 9)) / 2
    ich_k = (ta.highest(h, 26) + ta.lowest(l, 26)) / 2
    ich_sa = (ich_t + ich_k) / 2
    ich_sb = (ta.highest(h, 52) + ta.lowest(l, 52)) / 2

    kl_tr = np.where(c > c.shift(1), 1, -1)
    kl_dm = (h - l).to_numpy(float)
    kl_cm = _klinger_cm(kl_dm, kl_tr)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(kl_cm != 0, np.abs(2 * (kl_dm / kl_cm) - 1), 0.0)
    kl_vf = pd.Series(
        np.where(kl_cm != 0, v.to_numpy(float) * ratio * kl_tr * 100.0, 0.0),
        index=df.index,
    )
    kl_kvo = ta.ema(kl_vf, 34) - ta.ema(kl_vf, 55)

    hl2 = (h + l) / 2
    ao_v = ta.sma(hl2, 5) - ta.sma(hl2, 34)
    sar_v = ta.sar(h, l, c, 0.02, 0.02, 0.2)

    tr_s = ta.true_range(h, l, c)
    vi_p = (h - l.shift(1)).abs().rolling(14).sum() / tr_s.rolling(14).sum()
    vi_m = (l - h.shift(1)).abs().rolling(14).sum() / tr_s.rolling(14).sum()

    _, ut_pos_arr = _ut_bot(c.to_numpy(float), ta.atr(h, l, c, 10).to_numpy(float))
    ut_pos = pd.Series(ut_pos_arr, index=df.index)

    g_jaw, g_tth, g_lip = ta.sma(hl2, 13), ta.sma(hl2, 8), ta.sma(hl2, 5)

    uo_bp = c - pd.concat([l, c.shift(1)], axis=1).min(axis=1)
    uo_tr = (pd.concat([h, c.shift(1)], axis=1).max(axis=1)
             - pd.concat([l, c.shift(1)], axis=1).min(axis=1))
    uo_v = 100.0 * (
        4 * uo_bp.rolling(7).sum() / uo_tr.rolling(7).sum()
        + 2 * uo_bp.rolling(14).sum() / uo_tr.rolling(14).sum()
        + uo_bp.rolling(28).sum() / uo_tr.rolling(28).sum()
    ) / 7.0

    ema_50, ema_200 = ta.ema(c, 50), ta.ema(c, 200)
    ema_300, ema_365 = ta.ema(c, 300), ta.ema(c, 365)
    atr14 = ta.atr(h, l, c, 14)
    adx_p, adx_m, adx_v = ta.dmi(h, l, c, 14, 14)

    ma_cnt = sum(
        (c > f(c, n)).astype(int)
        for f, n in [(ta.sma, 10), (ta.sma, 20), (ta.sma, 30), (ta.sma, 50),
                     (ta.sma, 100), (ta.sma, 150), (ta.sma, 200),
                     (ta.ema, 10), (ta.ema, 20), (ta.ema, 50)]
    )

    macd_cross_al = ta.crossover(macd_v, sig_v)
    macd_cross_sat = ta.crossunder(macd_v, sig_v)
    macd_cs_al = macd_cross_al | (~macd_cross_sat & (macd_v > sig_v))

    bb_cond = pd.Series(
        np.where(c > bb_basis + 2 * bb_sd, 0,
                 np.where(c < bb_basis - 2 * bb_sd, 1,
                          np.where(c > bb_basis, 1, 0))),
        index=df.index,
    )

    sq_val = ta.linreg(
        c - ((ta.highest(h, 20) + ta.lowest(l, 20)) / 2 + ta.sma(c, 20)) / 2, 20, 0
    )

    # Gunluk periyotta Pine'in ta.vwap'i her barda sifirlandigi icin hlc3'e esittir.
    vwap_v = (h + l + c) / 3

    checks = [
        sbs_trend == 1,
        rsi_v > 50,
        k_v > d_v,
        macd_v > sig_v,
        macd_cs_al,
        ppo_v > ta.ema(ppo_v, 12),
        bb_cond == 1,
        (h - bbp_e > 0) & ((h - bbp_e) > (l - bbp_e)),
        c > dema_v,
        (c > ich_sa) & (c > ich_sb) & (ich_t > ich_k),
        kl_kvo > ta.ema(kl_kvo, 13),
        (c - c.shift(10)) > 0,
        (ao_v > 0) & (ao_v > ao_v.shift(1)),
        c > sar_v,
        vi_p > vi_m,
        ut_pos == 1,
        (g_lip > g_tth) & (g_tth > g_jaw),
        uo_v > 50,
        ma_cnt >= 6,
        c > ema_365,
        ema_50 > ema_200,
        atr14 > atr14.shift(1),
        ta.obv(c, v) > ta.sma(ta.obv(c, v), 20),
        c > vwap_v,
        (adx_v >= 25) & (adx_p > adx_m),
        sq_val > 0,
    ]
    for name, s in zip(SBS_NAMES, checks):
        out["sbs_" + name] = s.fillna(False).astype(bool)

    al_sayisi = sum(s.fillna(False).astype(int) for s in checks)
    sat_sayisi = 26 - al_sayisi

    golden_zone = ema_50 > ema_200

    # --- BOLUM 3: YZ AI motoru ----------------------------------------------
    f_rsi = ta.rsi(c, cfg.ai_sens)
    f_cci = ta.cci(c, cfg.ai_sens)
    f_atr = ta.atr(h, l, c, cfg.ai_sens)
    f_macd = ta.ema(c, 12) - ta.ema(c, 26)

    norm_cci = (f_cci + 200) / 4
    norm_macd = pd.Series(np.where(f_macd > 0, 80.0, 20.0), index=df.index)
    ai_score = ((f_rsi + norm_cci + norm_macd) / 3) * 2 - 100

    is_bull_ai = ai_score > 20
    is_bear_ai = ai_score < -20
    base_ai = ta.wma(c, cfg.ai_sens)

    bull_signal_ai = is_bull_ai & ~is_bull_ai.shift(1).fillna(False)
    bear_signal_ai = is_bear_ai & ~is_bear_ai.shift(1).fillna(False)

    # --- BOLUM 4: Long / Short kosullari ------------------------------------
    gc_long_ok = golden_zone if cfg.use_gc_filter else pd.Series(True, index=df.index)
    gc_short_ok = ~golden_zone if cfg.use_gc_filter else pd.Series(True, index=df.index)

    long_condition = (is_bull_ai & (al_sayisi >= cfg.min_al_sayisi)
                      & (sbs_trend == 1) & gc_long_ok)
    short_condition = (is_bear_ai & (sat_sayisi >= cfg.min_sat_sayisi)
                       & (sbs_trend == -1) & gc_short_ok)

    is_long_entry = long_condition & ~long_condition.shift(1).fillna(False)
    is_short_entry = short_condition & ~short_condition.shift(1).fillna(False)

    strong_buy = bull_signal_ai & is_long_entry
    strong_sell = bear_signal_ai & is_short_entry

    # Pine'da "AI Buy" etiketi Strong Buy varken gizlenir; ikisini de tutuyoruz.
    show_bull_ai = bull_signal_ai & ~strong_buy
    show_bear_ai = bear_signal_ai & ~strong_sell

    # --- BOLUM 4.1: Commodity Trends AI (CCI) -------------------------------
    cci_v = ta.cci(c, cfg.cci_len)
    cci_state = _cci_trend(cci_v, cfg.upper, cfg.lower)
    cci_long = ta.crossover(cci_v, cfg.long_threshold)
    cci_long_exit = ta.crossunder(cci_v, 0)
    cci_short = ta.crossunder(cci_v, cfg.short_threshold)
    cci_short_exit = ta.crossover(cci_v, 0)

    # --- ciktilar ------------------------------------------------------------
    out["close"] = c
    out["volume"] = v
    out["al_sayisi"] = al_sayisi
    out["sat_sayisi"] = sat_sayisi
    out["genel_sinyal"] = np.where(al_sayisi > sat_sayisi, "AL",
                                   np.where(sat_sayisi > al_sayisi, "SAT", "NOTR"))
    out["sbs_trend"] = sbs_trend
    out["golden_zone"] = golden_zone
    out["ai_score"] = ai_score
    out["ai_guven"] = ((ai_score + 100) / 2).round(1)
    out["ai_state"] = np.where(is_bull_ai, "BULLISH",
                               np.where(is_bear_ai, "BEARISH", "NEUTRAL"))
    out["base_ai"] = base_ai
    out["cci"] = cci_v
    out["cci_state"] = cci_state
    out["ema_50"], out["ema_200"] = ema_50, ema_200
    out["ema_300"], out["ema_365"] = ema_300, ema_365
    out["atr_pct"] = (atr14 / c * 100).round(2)
    out["adx"] = adx_v

    out["AI_BUY"] = show_bull_ai.fillna(False)
    out["AI_SELL"] = show_bear_ai.fillna(False)
    out["CCI_LONG"] = cci_long.fillna(False)
    out["CCI_LONG_EXIT"] = cci_long_exit.fillna(False)
    out["CCI_SHORT"] = cci_short.fillna(False)
    out["CCI_SHORT_EXIT"] = cci_short_exit.fillna(False)
    out["STRONG_BUY"] = strong_buy.fillna(False)
    out["STRONG_SELL"] = strong_sell.fillna(False)
    out["LONG_ENTRY"] = is_long_entry.fillna(False)
    out["SHORT_ENTRY"] = is_short_entry.fillna(False)

    return out


# Modul disina acilan yardimci: son bar ozeti
def last_row_summary(symbol: str, res: pd.DataFrame, lookback: int = 1) -> dict:
    """
    Son `lookback` bar icinde tetiklenen sinyalleri isaretler.
    lookback=1 => sadece en son kapanmis bar.
    """
    tail = res.tail(lookback)
    last = res.iloc[-1]
    prev_close = res["close"].iloc[-2] if len(res) > 1 else np.nan

    def fired(col):
        return bool(tail[col].any())

    return {
        "Hisse": symbol,
        "Fiyat": round(float(last["close"]), 2),
        "Degisim %": round(float((last["close"] / prev_close - 1) * 100), 2)
        if prev_close == prev_close else np.nan,
        "AI Buy": fired("AI_BUY"),
        "CCI Long": fired("CCI_LONG"),
        "Strong Buy": fired("STRONG_BUY"),
        "Long Giris": fired("LONG_ENTRY"),
        "AL": int(last["al_sayisi"]),
        "SAT": int(last["sat_sayisi"]),
        "SBS": str(last["genel_sinyal"]),
        "YZ Durum": str(last["ai_state"]),
        "YZ Guven %": float(last["ai_guven"]),
        "CCI": round(float(last["cci"]), 1) if last["cci"] == last["cci"] else np.nan,
        "Supertrend": "YUKARI" if last["sbs_trend"] == 1 else "ASAGI",
        "Bolge": "GOLDEN" if last["golden_zone"] else "DEATH",
        "ADX": round(float(last["adx"]), 1) if last["adx"] == last["adx"] else np.nan,
        "Volatilite %": float(last["atr_pct"]),
        "Hacim": float(last["volume"]),
    }
