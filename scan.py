"""
Tarayici. Tum BIST hisselerini gezer, indikatoru calistirir, sinyal ureten
hisseleri tabloya doker.

Komut satirindan:
    python -m bist_screener.scan --lookback 1 --min-hacim 1000000
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from . import data as bist_data
from .engine import Settings, compute, last_row_summary

COLUMNS = [
    "Hisse", "Sinyal", "Fiyat", "Degisim %", "AL", "SAT", "SBS", "YZ Durum",
    "YZ Guven %", "CCI", "Supertrend", "Bolge", "ADX", "Volatilite %", "Hacim",
]


def _label(row: dict) -> str:
    tags = []
    if row["Strong Buy"]:
        tags.append("STRONG BUY")
    if row["AI Buy"]:
        tags.append("AI Buy")
    if row["CCI Long"]:
        tags.append("CCI Long")
    if row["Long Giris"] and "STRONG BUY" not in tags:
        tags.append("Long Giris")
    return " + ".join(tags)


def scan(symbols: list[str] | None = None, lookback: int = 1,
         cfg: Settings | None = None, min_volume: float = 0.0,
         use_cache: bool = True, progress_cb=None) -> pd.DataFrame:
    """
    lookback: kac bar geriye kadar tetiklenen sinyaller kabul edilsin (1 = son bar)
    min_volume: son barda bu lotun altinda kalan hisseler elenir
    """
    cfg = cfg or Settings()
    symbols = symbols or bist_data.get_symbols()
    frames = bist_data.download(symbols, use_cache=use_cache, progress_cb=progress_cb)

    rows = []
    for sym, df in frames.items():
        try:
            res = compute(df, cfg)
        except Exception:
            continue
        row = last_row_summary(sym, res, lookback=lookback)
        if not (row["AI Buy"] or row["CCI Long"]):
            continue
        if row["Hacim"] < min_volume:
            continue
        row["Sinyal"] = _label(row)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=COLUMNS)

    out = pd.DataFrame(rows)
    # Once Strong Buy, sonra iki sinyali birden verenler, sonra SBS skoru
    out["_rank"] = (
        out["Strong Buy"].astype(int) * 100
        + (out["AI Buy"] & out["CCI Long"]).astype(int) * 50
        + out["AL"]
    )
    out = out.sort_values("_rank", ascending=False).drop(columns="_rank")
    return out[COLUMNS].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="BIST Long sinyal tarayici")
    ap.add_argument("--lookback", type=int, default=1,
                    help="Son kac barda tetiklenen sinyaller listelensin")
    ap.add_argument("--min-hacim", type=float, default=0.0,
                    help="Minimum son bar hacmi (lot)")
    ap.add_argument("--bist100", action="store_true",
                    help="Tum piyasa yerine sadece hazir listeyi tara")
    ap.add_argument("--cikti", type=str, default="",
                    help="Sonucu CSV olarak kaydet")
    args = ap.parse_args()

    syms = bist_data.get_symbols(full_market=not args.bist100)
    print(f"{len(syms)} hisse taraniyor...")

    def prog(done, total):
        print(f"  veri: {done}/{total}", end="\r")

    df = scan(syms, lookback=args.lookback, min_volume=args.min_hacim,
              progress_cb=prog)
    print()
    if df.empty:
        print("Bugun kriterlere uyan hisse yok.")
    else:
        print(df.to_string(index=False))

    path = args.cikti or f"bist_long_{dt.date.today():%Y%m%d}.csv"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nKaydedildi: {path}")


if __name__ == "__main__":
    main()
