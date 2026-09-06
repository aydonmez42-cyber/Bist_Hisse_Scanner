"""
BIST veri katmani.

Sembol listesi once canli kaynaktan alinir (isyatirimhisse), olmazsa asagidaki
statik listeye duser. Fiyat verisi yfinance uzerinden ".IS" ekiyle cekilir ve
diske parquet olarak onbelleklenir, boylece gun icinde tekrar tarama yaparken
600 hisseyi bastan indirmezsiniz.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(os.environ.get("BIST_CACHE", Path.home() / ".bist_screener_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# BIST 100 + yuksek hacimli isimler. Canli liste cekilemezse bu kullanilir.
FALLBACK_SYMBOLS = [
    "AEFES", "AGHOL", "AKBNK", "AKCNS", "AKFGY", "AKFYE", "AKSA", "AKSEN",
    "ALARK", "ALBRK", "ALFAS", "ANSGR", "ARCLK", "ASELS", "ASTOR", "ASUZU",
    "AYDEM", "AYGAZ", "BERA", "BIENY", "BIMAS", "BIOEN", "BOBET", "BRSAN",
    "BRYAT", "BUCIM", "CANTE", "CCOLA", "CEMTS", "CIMSA", "CWENE", "DOAS",
    "DOHOL", "ECILC", "ECZYT", "EGEEN", "EKGYO", "ENERY", "ENJSA", "ENKAI",
    "EREGL", "EUPWR", "EUREN", "FROTO", "GARAN", "GENIL", "GESAN", "GLYHO",
    "GUBRF", "GWIND", "HALKB", "HEKTS", "IPEKE", "ISCTR", "ISDMR", "ISGYO",
    "ISMEN", "IZMDC", "KARSN", "KAYSE", "KCAER", "KCHOL", "KLSER", "KMPUR",
    "KONTR", "KONYA", "KORDS", "KOZAA", "KOZAL", "KRDMD", "MAVI", "MGROS",
    "MIATK", "MPARK", "ODAS", "OTKAR", "OYAKC", "PENTA", "PETKM", "PGSUS",
    "PSGYO", "QUAGR", "SAHOL", "SASA", "SDTTR", "SELEC", "SISE", "SKBNK",
    "SMRTG", "SOKM", "TAVHL", "TCELL", "THYAO", "TKFEN", "TOASO", "TSKB",
    "TTKOM", "TTRAK", "TUKAS", "TUPRS", "TURSG", "ULKER", "VAKBN", "VESBE",
    "VESTL", "YEOTK", "YKBNK", "YYLGD", "ZOREN",
]


def get_symbols(full_market: bool = True) -> list[str]:
    """
    full_market=True ise tum BIST pay listesini canli kaynaktan almayi dener.
    Basarisiz olursa FALLBACK_SYMBOLS doner.
    """
    if full_market:
        try:
            from isyatirimhisse import fetch_stock_list  # type: ignore

            data = fetch_stock_list()
            col = "CODE" if "CODE" in data.columns else data.columns[0]
            syms = sorted({str(x).strip().upper() for x in data[col] if str(x).strip()})
            syms = [s for s in syms if s.isalpha() and 4 <= len(s) <= 5]
            if len(syms) > 100:
                return syms
        except Exception:
            pass
    return FALLBACK_SYMBOLS


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.parquet"


def download(symbols: list[str], years: int = 4, use_cache: bool = True,
             progress_cb=None) -> dict[str, pd.DataFrame]:
    """
    Gunluk OHLCV verisi indirir. Cikti: {sembol: DataFrame}.
    Onbellek ayni gun icinde tekrar indirmeyi engeller.
    """
    import yfinance as yf

    today = dt.date.today()
    start = today - dt.timedelta(days=365 * years + 30)
    result: dict[str, pd.DataFrame] = {}
    to_fetch: list[str] = []

    for s in symbols:
        p = _cache_path(s)
        if use_cache and p.exists():
            age = dt.date.fromtimestamp(p.stat().st_mtime)
            if age == today:
                try:
                    result[s] = pd.read_parquet(p)
                    continue
                except Exception:
                    pass
        to_fetch.append(s)

    batch_size = 40
    for i in range(0, len(to_fetch), batch_size):
        batch = to_fetch[i:i + batch_size]
        tickers = [f"{s}.IS" for s in batch]
        try:
            raw = yf.download(
                tickers, start=start.isoformat(), interval="1d",
                group_by="ticker", auto_adjust=False, threads=True,
                progress=False,
            )
        except Exception:
            continue

        for s, t in zip(batch, tickers):
            try:
                sub = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                sub = sub.rename(columns=str.lower)[
                    ["open", "high", "low", "close", "volume"]
                ].dropna()
                if len(sub) < 400:      # EMA365 icin yeterli gecmis yoksa atla
                    continue
                sub.to_parquet(_cache_path(s))
                result[s] = sub
            except Exception:
                continue

        if progress_cb:
            progress_cb(min(i + batch_size, len(to_fetch)), len(to_fetch))

    return result
