"""
Tarayici. Tum BIST hisselerini gezer, DI+/DI- kesisim motorunu calistirir,
AL veya SAT sinyali veren hisseleri tabloya doker.

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
    "Hisse", "Sinyal", "Fiyat", "Degisim %", "DI+", "DI-", "ADX",
    "Kesisim Gun", "Hacim",
]


def _label(row: dict) -> str:
    """Satirin gosterilecek sinyal etiketi: 'AL' ya da 'SAT'."""
    if row.get("AL"):
        return "AL"
    if row.get("SAT"):
        return "SAT"
    return str(row.get("Yon", ""))


def scan(symbols: list[str] | None = None, lookback: int = 1,
         cfg: Settings | None = None, min_volume: float = 0.0,
         min_adx: float = 0.0, use_cache: bool = True,
         progress_cb=None) -> pd.DataFrame:
    """
    lookback: kac bar geriye kadar tetiklenen kesisimler kabul edilsin (1 = son bar)
    min_volume: son barda bu hacmin altinda kalan hisseler elenir
    min_adx: bu ADX'in altindaki (zayif trend) sinyaller elenir
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
        if not (row["AL"] or row["SAT"]):
            continue
        if row["Hacim"] < min_volume:
            continue
        if row["ADX"] == row["ADX"] and row["ADX"] < min_adx:
            continue
        row["Sinyal"] = _label(row)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=COLUMNS)

    out = pd.DataFrame(rows)
    # Once AL sinyalleri, sonra SAT sinyalleri; her grup icinde ADX'e (trend
    # gucune) gore azalan sirada.
    out["_yon_sira"] = out["Sinyal"].map({"AL": 0, "SAT": 1}).fillna(2)
    out = out.sort_values(["_yon_sira", "ADX"], ascending=[True, False])
    out = out.drop(columns="_yon_sira")
    return out[COLUMNS].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="BIST DI+/DI- sinyal tarayici")
    ap.add_argument("--lookback", type=int, default=1,
                    help="Son kac barda tetiklenen kesisimler listelensin")
    ap.add_argument("--min-hacim", type=float, default=0.0,
                    help="Minimum son bar hacmi (lot)")
    ap.add_argument("--min-adx", type=float, default=0.0,
                    help="Bu ADX'in altindaki sinyaller elenir")
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
              min_adx=args.min_adx, progress_cb=prog)
    print()
    if df.empty:
        print("Bugun kriterlere uyan hisse yok.")
    else:
        print(df.to_string(index=False))

    path = args.cikti or f"bist_di_{dt.date.today():%Y%m%d}.csv"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nKaydedildi: {path}")


if __name__ == "__main__":
    main()
