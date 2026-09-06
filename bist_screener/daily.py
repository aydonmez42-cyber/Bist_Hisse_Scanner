"""
Gunluk otomatik tarama isi.

Her aksam 18:30'da calistirilir; gunluk barda AI Buy veya CCI Long ureten
hisseleri Telegram'a gonderir.

    python -m bist_screener.daily
    python -m bist_screener.daily --test          # baglantiyi dogrula, tarama yapma
    python -m bist_screener.daily --zorla         # hafta sonu / bayat veri olsa da gonder
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from . import data as bist_data
from . import notify
from .engine import Settings, compute, last_row_summary
from .scan import _label

TZ = ZoneInfo("Europe/Istanbul")
LOG_DIR = Path.home() / ".bist_screener_cache" / "log"

# Tarama esikleri — burayi kendinize gore degistirin
MIN_HACIM = 500_000        # lot
MIN_AL = 13                # 26 gostergeden en az kaci AL demeli
LOOKBACK = 1               # sadece son kapanmis bar
MAX_SATIR = 40             # mesajda listelenecek azami hisse


def _fmt_row(r: dict) -> str:
    ok = "▲" if r["Degisim %"] >= 0 else "▼"
    return (f"<code>{r['Hisse']:<6}</code> {r['Fiyat']:>8.2f}  "
            f"{ok}{abs(r['Degisim %']):>5.2f}%  "
            f"AL {r['AL']:>2}/26  YZ {r['YZ Guven %']:.0f}")


def build_message(df: pd.DataFrame, taranan: int, veri_tarihi: dt.date,
                  bayat: bool) -> str:
    now = dt.datetime.now(TZ)
    head = [
        f"<b>BIST Long Tarama</b> · {now:%d.%m.%Y %H:%M}",
        f"Taranan {taranan} hisse · {len(df)} sinyal · veri {veri_tarihi:%d.%m}",
    ]
    if bayat:
        head.append("⚠️ Son bar bugüne ait değil — borsa kapalı olabilir "
                    "ya da veri gecikmiş.")
    if df.empty:
        head.append("\nBugün kriterlere uyan hisse yok.")
        return "\n".join(head)

    gruplar = [
        ("🔷 <b>STRONG BUY</b>", df[df["Strong Buy"]]),
        ("🟩 <b>AI Buy + CCI Long</b>",
         df[~df["Strong Buy"] & df["AI Buy"] & df["CCI Long"]]),
        ("🟢 <b>AI Buy</b>", df[~df["Strong Buy"] & df["AI Buy"] & ~df["CCI Long"]]),
        ("🔵 <b>CCI Long</b>", df[~df["Strong Buy"] & ~df["AI Buy"] & df["CCI Long"]]),
    ]

    body, yazilan = [], 0
    for baslik, g in gruplar:
        if g.empty:
            continue
        body.append("\n" + baslik)
        for _, r in g.iterrows():
            if yazilan >= MAX_SATIR:
                body.append(f"… ve {len(df) - yazilan} hisse daha (CSV'de)")
                yazilan = 10**9
                break
            body.append(_fmt_row(r))
            yazilan += 1
        if yazilan > MAX_SATIR:
            break

    tail = ["", "<i>Ön eleme listesidir, yatırım tavsiyesi değildir.</i>"]
    return "\n".join(head + body + tail)


def run(cfg: Settings | None = None, gonder: bool = True,
        zorla: bool = False) -> pd.DataFrame:
    cfg = cfg or Settings()
    now = dt.datetime.now(TZ)

    if now.weekday() >= 5 and not zorla:
        print("Hafta sonu — tarama atlandı.")
        return pd.DataFrame()

    symbols = bist_data.get_symbols(full_market=True)
    frames = bist_data.download(symbols, use_cache=False)
    if not frames:
        raise RuntimeError("Hiç veri indirilemedi. İnternet veya yfinance sorunu.")

    # Veri tazeligi: en yaygin son bar tarihini referans al
    son_tarihler = [df.index[-1].date() for df in frames.values()]
    veri_tarihi = max(set(son_tarihler), key=son_tarihler.count)
    bayat = veri_tarihi != now.date()
    if bayat and not zorla:
        print(f"Son bar {veri_tarihi}, bugün {now.date()} — tatil olabilir. "
              "Yine de rapor gönderiliyor.")

    rows = []
    for sym, df in frames.items():
        try:
            res = compute(df, cfg)
        except Exception:
            continue
        r = last_row_summary(sym, res, lookback=LOOKBACK)
        if not (r["AI Buy"] or r["CCI Long"]):
            continue
        if r["Hacim"] < MIN_HACIM or r["AL"] < MIN_AL:
            continue
        r["Sinyal"] = _label(r)
        rows.append(r)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["Strong Buy", "AL", "YZ Guven %"], ascending=False)
        out = out.reset_index(drop=True)

    if gonder:
        notify.send(build_message(out, len(frames), veri_tarihi, bayat))
        if not out.empty:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            csv = LOG_DIR / f"bist_long_{now:%Y%m%d}.csv"
            out.to_csv(csv, index=False, encoding="utf-8-sig")
            notify.send_document(csv, caption=f"Tam liste — {len(out)} hisse")

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Günlük BIST Long taraması")
    ap.add_argument("--test", action="store_true",
                    help="Sadece Telegram bağlantısını doğrula")
    ap.add_argument("--zorla", action="store_true",
                    help="Hafta sonu veya bayat veride de çalış")
    ap.add_argument("--gonderme", action="store_true",
                    help="Taramayı yap ama Telegram'a gönderme")
    args = ap.parse_args()

    notify.load_env(Path(__file__).resolve().parent.parent / ".env")
    notify.load_env(".env")

    if args.test:
        print("Bot:", notify.test_connection())
        return

    try:
        df = run(gonder=not args.gonderme, zorla=args.zorla)
        print(f"Tamam — {len(df)} sinyal.")
        if not df.empty:
            print(df[["Hisse", "Sinyal", "Fiyat", "AL"]].to_string(index=False))
    except Exception:
        hata = traceback.format_exc(limit=3)
        print(hata, file=sys.stderr)
        try:
            notify.send("❌ <b>Tarama hatası</b>\n<pre>"
                        + html.escape(hata[-1200:]) + "</pre>")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
