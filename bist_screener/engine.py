"""
DI+ / DI- Kesisim Sinyal Motoru (ADX/DMI tabanli).

Basit ve seffaf bir sistem, eski 26-gostergeli SBS + YZ + CCI + Supertrend
motorunun yerine gecti:

  - DI+ (yesil), DI-'yi (kirmizi) YUKARI keserse  -> AL sinyali
  - DI- (kirmizi), DI+'yi (yesil) YUKARI keserse  -> SAT sinyali

Ikinci bir tarama secenegi olarak Supertrend (ATR 10 x 7.8) de hesaplanir:
  - Supertrend yukari donerse (fiyat ust bandi asarsa)  -> AL sinyali
  - Supertrend asagi donerse  (fiyat alt bandi kirarsa) -> SAT sinyali
Dashboard hangi sistemin sinyalinin listelenecegini "Sinyal sistemi" ile secer;
ikisi de her taramada hesaplanir.

ADX aynı hesaptan gelir ve sinyalin YONUNU degil, mevcut trendin GUCUNU
gosterir; "Minimum ADX" filtresiyle yatay/kararsiz piyasadaki gurultulu
kesisimleri elemek icin kullanilir.

Gunluk zaman diliminde calisir (df'in her satiri bir gunluk bar kabul edilir).
Hesaplama Pine'daki ta.dmi(diLen, adxLen) ile birebir ayni Wilder yontemini
kullanir (bkz. pine.dmi).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import pine as ta


@dataclass
class Settings:
    """DMI/ADX (14/14, Wilder) ve Supertrend (10 / 7.8) parametreleri."""
    di_len: int = 14
    adx_len: int = 14
    st_len: int = 10          # Supertrend ATR periyodu
    st_mult: float = 7.8      # Supertrend ATR carpani


def _supertrend(close: np.ndarray, atr: np.ndarray, mult: float):
    """
    ATR tabanli takip eden stop ve yon (Pine BOLUM 2'deki uygulama: bantlar
    kapanisin +/- mult*ATR'sidir). trend: 1 = yukari, -1 = asagi.
    """
    n = len(close)
    up = close - mult * atr
    dn = close + mult * atr
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


def _bars_since(flag: np.ndarray) -> np.ndarray:
    """Her barda, son True'dan bu yana gecen bar sayisi (True barinda 0)."""
    out = np.zeros(len(flag), dtype=int)
    sayac = 0
    for i, f in enumerate(flag):
        sayac = 0 if f else sayac + 1
        out[i] = sayac
    return out


def compute(df: pd.DataFrame, cfg: Settings | None = None) -> pd.DataFrame:
    """
    Girdi: open/high/low/close/volume sutunlari olan, tarihe gore artan DataFrame.
    Cikti: ayni indeksli DataFrame - DI+, DI-, ADX ve AL/SAT kesisim sutunlari.
    """
    cfg = cfg or Settings()
    h, l, c, v = df["high"], df["low"], df["close"], df["volume"]

    di_plus, di_minus, adx_v = ta.dmi(h, l, c, cfg.di_len, cfg.adx_len)

    al_cross = ta.crossover(di_plus, di_minus)   # DI+ DI-'yi yukari kesti  -> AL
    sat_cross = ta.crossover(di_minus, di_plus)  # DI- DI+'yi yukari kesti  -> SAT

    out = pd.DataFrame(index=df.index)
    out["close"] = c
    out["volume"] = v
    out["di_plus"] = di_plus
    out["di_minus"] = di_minus
    out["adx"] = adx_v
    out["yon"] = np.where(di_plus > di_minus, "AL", "SAT")
    out["AL_CROSS"] = al_cross.fillna(False)
    out["SAT_CROSS"] = sat_cross.fillna(False)

    # Son kesisimden bu yana gecen bar sayisi - sinyalin ne kadar "taze"
    # oldugunu gostermek icin (0 = tam bugun kesisti).
    out["kesisim_gun"] = _bars_since((out["AL_CROSS"] | out["SAT_CROSS"]).to_numpy())

    # --- Supertrend -----------------------------------------------------------
    atr_st = ta.atr(h, l, c, cfg.st_len)
    st_up, st_dn, st_trend = _supertrend(
        c.to_numpy(float), atr_st.to_numpy(float), cfg.st_mult)
    trend = pd.Series(st_trend, index=df.index)
    prev = trend.shift(1)
    # ATR isinma doneminde (ilk st_len bar) yon henuz anlamsiz: sahte donus yok.
    olgun = pd.Series(np.arange(len(df)) > cfg.st_len, index=df.index)
    st_al = ((trend == 1) & (prev == -1) & olgun).fillna(False)
    st_sat = ((trend == -1) & (prev == 1) & olgun).fillna(False)

    out["st_yon"] = np.where(trend == 1, "AL", "SAT")
    out["st_seviye"] = np.where(trend == 1, st_up, st_dn)
    out["ST_AL"] = st_al
    out["ST_SAT"] = st_sat
    out["st_gun"] = _bars_since((st_al | st_sat).to_numpy())

    return out


def last_row_summary(symbol: str, res: pd.DataFrame, lookback: int = 1) -> dict:
    """
    Son `lookback` bar icinde tetiklenen AL/SAT kesisimlerini isaretler.
    lookback=1 => sadece en son kapanmis bar.
    """
    tail = res.tail(lookback)
    last = res.iloc[-1]
    prev_close = res["close"].iloc[-2] if len(res) > 1 else np.nan

    def fired(col):
        return bool(tail[col].any())

    def num(x):
        return round(float(x), 1) if x == x else np.nan  # x==x -> NaN degil

    return {
        "Hisse": symbol,
        "Fiyat": round(float(last["close"]), 2),
        "Degisim %": round(float((last["close"] / prev_close - 1) * 100), 2)
        if prev_close == prev_close else np.nan,
        "Yon": str(last["yon"]),
        "AL": fired("AL_CROSS"),
        "SAT": fired("SAT_CROSS"),
        "DI+": num(last["di_plus"]),
        "DI-": num(last["di_minus"]),
        "ADX": num(last["adx"]),
        "Kesisim Gun": int(last["kesisim_gun"]),
        "ST Yon": str(last["st_yon"]),
        "ST AL": fired("ST_AL"),
        "ST SAT": fired("ST_SAT"),
        "ST Seviye": round(float(last["st_seviye"]), 6)
        if last["st_seviye"] == last["st_seviye"] else np.nan,
        "ST Gun": int(last["st_gun"]),
        "Hacim": float(last["volume"]),
    }
