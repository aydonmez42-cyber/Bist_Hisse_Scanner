"""
Binance USDT-M Futures veri katmani.

bist_screener.data ile ayni arayuzu sunar (get_symbols, download, LAST_SOURCE),
boylece dashboard iki piyasa arasinda modul referansini degistirerek gecis yapar.

ONEMLI: Buradaki "Hacim" sutunu coin'in kendi biriminde (BTC, DOGE, ...) degil,
Binance klines'in quoteVolume alani uzerinden USDT cinsindendir. Boylece farkli
fiyattaki coinlerin hacmi ayni olcekte karsilastirilabilir. 26 gostergenin hicbiri
mutlak bir hacim esigi kullanmiyor (hepsi kendi hareketli ortalamasiyla kiyaslanir),
bu yuzden birim degisikligi hesaplama mantigini etkilemez.

Kimlik dogrulama gerektirmeyen genel (public) uc noktalar kullanilir:
  GET /fapi/v1/exchangeInfo   -> sembol listesi
  GET /fapi/v1/klines         -> gunluk OHLCV

Not: Binance bazi bolgelerden (orn. bir kismi ABD IP'leri) fapi.binance.com'a
erisimi kisitlayabiliyor. Railway sunucunuzun bolgesi engellenmisse exchangeInfo
cagrisi basarisiz olur ve asagidaki FALLBACK_SYMBOLS listesine dusulur; per-sembol
klines cagrilari da ayni ana makineden gittigi icin muhtemelen basarisiz olur.
Bu durumda dashboard'da sembol kaynagi satirinda uyari gorunur.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

BASE_URL = "https://fapi.binance.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; bist-screener/1.0)"}

CACHE_DIR = Path(os.environ.get("BIST_CACHE", Path.home() / ".bist_screener_cache")) / "crypto"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

LAST_SOURCE = "?"

# Son care yedek liste: sadece exchangeInfo cagrisi basarisiz olursa kullanilir.
# Cok uzun sureli, delisting riski dusuk majorler secildi; guncel liste degil,
# sadece agirlikli bir "hicbir sey donmesin" guvencesi.
FALLBACK_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT", "DOTUSDT", "LTCUSDT",
    "BCHUSDT", "ATOMUSDT", "ETCUSDT", "XLMUSDT", "NEARUSDT", "UNIUSDT",
    "AAVEUSDT", "FILUSDT", "ICPUSDT", "HBARUSDT", "APTUSDT", "ARBUSDT",
    "OPUSDT",
]


def _from_binance(timeout: int = 15) -> list[str]:
    """USDT-M perpetual (surekli) futures sembollerini canli ceker."""
    req = urllib.request.Request(f"{BASE_URL}/fapi/v1/exchangeInfo", headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8"))

    out = [
        s["symbol"] for s in body.get("symbols", [])
        if s.get("status") == "TRADING"
        and s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
    ]
    return sorted(set(out))


def get_symbols(full_market: bool = True) -> list[str]:
    """
    full_market=True  -> tum USDT-M perpetual futures sembolleri (canli).
    full_market=False -> majör coin listesi (agdan bagimsiz, aninda doner).
    """
    global LAST_SOURCE

    if not full_market:
        LAST_SOURCE = f"majör liste ({len(FALLBACK_SYMBOLS)} coin)"
        return FALLBACK_SYMBOLS

    try:
        syms = _from_binance()
        if len(syms) > 20:
            LAST_SOURCE = f"Binance Futures ({len(syms)} coin)"
            return syms
    except Exception:
        pass

    LAST_SOURCE = f"majör liste ({len(FALLBACK_SYMBOLS)} coin) — Binance API'ye ulaşılamadı"
    return FALLBACK_SYMBOLS


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.parquet"


def _fetch_klines(symbol: str, limit: int = 1000, timeout: int = 15) -> pd.DataFrame:
    """Gunluk kline verisi. 'volume' sutunu USDT cinsinden quoteVolume'dur."""
    qs = urllib.parse.urlencode({"symbol": symbol, "interval": "1d", "limit": limit})
    req = urllib.request.Request(f"{BASE_URL}/fapi/v1/klines?{qs}", headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.loads(r.read().decode("utf-8"))

    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{symbol}: boş veya geçersiz yanıt")

    df = pd.DataFrame(raw, columns=[
        "open_time", "open", "high", "low", "close", "base_volume",
        "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    out = df[["open", "high", "low", "close", "quote_volume"]].astype(float)
    out = out.rename(columns={"quote_volume": "volume"})
    return out.dropna()


def download(symbols: list[str], years: int | None = None, use_cache: bool = True,
             progress_cb=None, max_workers: int = 8) -> dict[str, pd.DataFrame]:
    """
    Gunluk OHLCV indirir. `years` parametresi bist_data.download ile ayni
    imzayi korumak icin var, Binance'te kullanilmiyor (limit=1000 gun ~ 2.7 yil,
    coinlerin cogunda zaten tum gecmisi kapsiyor).
    """
    today = dt.date.today()
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

    def _one(sym: str):
        try:
            df = _fetch_klines(sym)
            if len(df) < 400:      # EMA365 icin yeterli gecmis yoksa atla
                return sym, None
            df.to_parquet(_cache_path(sym))
            return sym, df
        except Exception:
            return sym, None

    done = 0
    if to_fetch:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_one, s) for s in to_fetch]
            for fut in as_completed(futures):
                sym, df = fut.result()
                if df is not None:
                    result[sym] = df
                done += 1
                if progress_cb and done % 10 == 0:
                    progress_cb(done, len(to_fetch))

    return result
