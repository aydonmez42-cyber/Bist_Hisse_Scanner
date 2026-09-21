"""
DI+ / DI- Kesisim Sinyal Motoru (ADX/DMI tabanli).

Basit ve seffaf bir sistem, eski 26-gostergeli SBS + YZ + CCI + Supertrend
motorunun yerine gecti:

  - DI+ (yesil), DI-'yi (kirmizi) YUKARI keserse  -> AL sinyali
  - DI- (kirmizi), DI+'yi (yesil) YUKARI keserse  -> SAT sinyali

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
    """DMI/ADX parametreleri. Varsayilanlar standart Wilder degerleridir (14/14)."""
    di_len: int = 14
    adx_len: int = 14


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
    cross_any = (out["AL_CROSS"] | out["SAT_CROSS"]).to_numpy()
    gun = np.zeros(len(out), dtype=int)
    sayac = 0
    for i in range(len(out)):
        if cross_any[i]:
            sayac = 0
        else:
            sayac += 1
        gun[i] = sayac
    out["kesisim_gun"] = gun

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
        "Hacim": float(last["volume"]),
    }
