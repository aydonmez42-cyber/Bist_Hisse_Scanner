"""
BIST Long Tarayici — dashboard.

Calistirmak icin:
    streamlit run bist_screener/app.py
"""

from __future__ import annotations

import datetime as dt
import hmac
import os
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bist_screener import data as bist_data
from bist_screener import pwa
from bist_screener.engine import SBS_NAMES, Settings, compute, last_row_summary
from bist_screener.scan import _label

TZ = ZoneInfo("Europe/Istanbul")

st.set_page_config(page_title="BIST Long Tarayıcı", page_icon="◆",
                   layout="wide", initial_sidebar_state="auto")

# Vurgu renkleri hem koyu hem acik temada okunacak sekilde secildi.
# Zemin ve yazi renkleri Streamlit temasindan gelir (var(--...)), boylece
# sag ustteki menuden temayi degistirdiginizde arayuz de birlikte degisir.
UP, DOWN, ACCENT = "#1FB47C", "#E35240", "#12AEB4"
BLUE, VIOLET, GRID = "#4A8FE7", "#8B6FE0", "#8A9AAB"

st.markdown("""
<style>
  .block-container { padding-top: 2.1rem; max-width: 1500px; }

  /* Kenar cubugu etiketleri tam kontrastta */
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] .stMarkdown p {
      color: var(--text-color, #EDF3F9) !important;
      font-size: .87rem; opacity: 1;
  }
  section[data-testid="stSidebar"] h3 {
      font-size: .73rem; letter-spacing: .08em; text-transform: uppercase;
      opacity: .72; margin: 1.5rem 0 .5rem; font-weight: 600;
  }
  .hint { font-size: .74rem; opacity: .62; margin: -.35rem 0 .7rem; }

  .hdr { display:flex; align-items:baseline; gap:.7rem; margin-bottom:.15rem; }
  .hdr h1 { font-size:1.6rem; font-weight:650; letter-spacing:-.02em; margin:0; }
  .hdr .badge { font-size:.68rem; letter-spacing:.08em; text-transform:uppercase;
                color:#12AEB4; border:1px solid #12AEB477; border-radius:3px;
                padding:2px 7px; }
  .sub { opacity:.66; font-size:.85rem; margin-bottom:1.3rem; }

  .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem;
           margin:.2rem 0 .4rem; }
  .card { background:var(--secondary-background-color, #1B2836);
          border:1px solid rgba(128,150,175,.28); border-radius:7px;
          padding:.85rem 1rem; }
  .card .n { font-size:1.8rem; font-weight:600; line-height:1.05;
             font-variant-numeric:tabular-nums; }
  .card .l { font-size:.74rem; opacity:.66; margin-top:.25rem; }

  .meta { opacity:.66; font-size:.78rem; margin:.6rem 0 1.1rem; }
  .meta b { opacity:1; font-weight:600; }

  .sect { font-size:.73rem; letter-spacing:.08em; text-transform:uppercase;
          opacity:.66; font-weight:600;
          border-top:1px solid rgba(128,150,175,.28);
          padding-top:1.1rem; margin:1.8rem 0 .8rem; }

  [data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }

  /* ---------- Telefon duzeni ---------- */
  .mobil-liste { display:none; }

  @media (max-width: 820px) {
      .block-container { padding-top:1.2rem; padding-left:.8rem;
                         padding-right:.8rem; }
      .cards { grid-template-columns:repeat(2,1fr); gap:.5rem; }
      .card { padding:.65rem .75rem; }
      .card .n { font-size:1.45rem; }
      .hdr h1 { font-size:1.28rem; }
      .sub { font-size:.8rem; margin-bottom:1rem; }

      /* Genis tablo telefonda okunmuyor; yerine kart listesi */
      .st-key-tablo_genis { display:none !important; }
      .mobil-liste { display:block; }
  }

  @media (min-width: 821px) { .mobil-liste { display:none !important; } }

  /* Hisse kartlari */
  .hk { background:var(--secondary-background-color, #1B2836);
        border:1px solid rgba(128,150,175,.28); border-radius:8px;
        padding:.7rem .8rem; margin-bottom:.5rem; }
  .hk-ust { display:flex; justify-content:space-between; align-items:baseline;
            gap:.5rem; }
  .hk-ad { font-size:1.02rem; font-weight:650; letter-spacing:.01em; }
  .hk-fiyat { font-size:1.0rem; font-weight:600;
              font-variant-numeric:tabular-nums; }
  .hk-rozet { display:inline-block; font-size:.66rem; font-weight:650;
              padding:2px 7px; border-radius:3px; margin:.4rem .3rem 0 0;
              letter-spacing:.02em; }
  .hk-bar { height:5px; border-radius:3px; margin:.55rem 0 .4rem;
            background:rgba(128,150,175,.22); overflow:hidden; }
  .hk-bar span { display:block; height:100%; border-radius:3px; }
  .hk-alt { display:flex; flex-wrap:wrap; gap:.15rem .9rem; font-size:.73rem;
            opacity:.72; font-variant-numeric:tabular-nums; }
  .hk-alt b { font-weight:600; opacity:1; }
</style>
""", unsafe_allow_html=True)


def gate() -> None:
    """DASHBOARD_PASSWORD tanimliysa parola sorar; bos ise kapi kapalidir."""
    sifre = os.environ.get("DASHBOARD_PASSWORD", "").strip()
    if not sifre or st.session_state.get("acik"):
        return
    st.markdown('<div class="hdr"><h1>BIST Long Tarayıcı</h1></div>',
                unsafe_allow_html=True)
    girilen = st.text_input("Parola", type="password")
    if girilen and hmac.compare_digest(girilen, sifre):
        st.session_state.acik = True
        st.rerun()
    elif girilen:
        st.error("Parola hatalı.")
    st.stop()


gate()
pwa.enable("#111A24")


@st.cache_data(ttl=1800, show_spinner=False)
def load_prices(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    return bist_data.download(list(symbols))


@st.cache_data(ttl=1800, show_spinner=False)
def load_symbols(full: bool) -> tuple[list[str], str]:
    syms = bist_data.get_symbols(full_market=full)
    return syms, bist_data.LAST_SOURCE


@st.cache_data(ttl=1800, show_spinner=False, max_entries=40)
def hesapla(df: pd.DataFrame, ai_sens: int, cci_len: int,
            long_th: int, gc: bool) -> pd.DataFrame:
    """
    Detay grafigi icin indikator hesabi. Onbelleklenmesi sart: aksi halde her
    onay kutusu dokunusunda 26 gosterge bastan hesaplanir ve Streamlit betik
    calisirken tum arayuzu kilitler — panel "pasif" gorunur.
    """
    return compute(df, Settings(ai_sens=ai_sens, cci_len=cci_len,
                                long_threshold=long_th, use_gc_filter=gc))


# --------------------------------------------------------------- kenar cubugu
with st.sidebar:
    st.markdown("### Tarama ayarları")
    st.markdown('<div class="hint">Bunları değiştirdikten sonra taramayı '
                'yeniden çalıştırmanız gerekir.</div>', unsafe_allow_html=True)

    evren = st.radio("Hisse evreni", ["Tüm BIST", "Yedek liste"], index=0)
    lookback = st.slider(
        "Sinyal tazeliği (bar)", 1, 5, 1,
        help="Sinyal, eşiğin kesildiği barda bir kez tetiklenir. 1 sadece son "
             "kapanmış günü gösterir. 3 yaparsanız son üç gün içinde tetiklenmiş "
             "hisseler de listeye girer — dün kaçırdığınız sinyalleri yakalarsınız, "
             "karşılığında liste eskir ve uzar.")
    ai_sens = st.slider("Classifier Sensitivity", 5, 50, 25,
                        help="YZ AI motorunun RSI/CCI/ATR periyodu. Düşük değer "
                             "daha çok ve daha erken sinyal, daha çok gürültü.")
    cci_len = st.slider("CCI Length", 10, 60, 30)
    long_th = st.slider("Long Threshold", 0, 150, 50,
                        help="CCI Long sinyalinin tetiklendiği eşik.")
    gc_filter = st.checkbox(
        "Altın/Ölüm kesişim filtresi", True,
        help="Açıkken Long girişleri yalnız EMA50 > EMA200 olan hisselerde "
             "sayılır. Strong Buy ve Long Giriş etiketlerini etkiler; "
             "AI Buy ve CCI Long etiketleri bundan bağımsızdır.")

    calistir = st.button("Taramayı çalıştır", type="primary",
                         use_container_width=True)

    st.markdown("### Liste filtresi")
    st.markdown('<div class="hint">Bunlar anında uygulanır, yeniden tarama '
                'gerektirmez.</div>', unsafe_allow_html=True)

    sadece_kesisim = st.checkbox("Sadece ikisi aynı anda", False)
    f_ai = st.checkbox("AI Buy", True, disabled=sadece_kesisim)
    f_cci = st.checkbox("CCI Long", True, disabled=sadece_kesisim)
    sadece_golden = st.checkbox("Sadece Golden Zone", False,
                                help="Listeyi EMA50 > EMA200 olan hisselerle "
                                     "sınırlar.")
    min_al = st.slider("Minimum SBS AL skoru", 0, 26, 13,
                       help="26 göstergeden en az kaçı AL demeli.")
    min_adx = st.slider(
        "Minimum ADX", 0, 50, 0,
        help="ADX trendin gücünü ölçer, yönünü değil. 20'nin altı genelde "
             "yatay/kararsız piyasa demektir ve bu tür seyirde sinyaller sık "
             "yanlış çıkar. 20–25 vermek yatay seyredenleri eler; 0 hepsini geçirir.")
    min_hacim = st.number_input("Minimum hacim (lot)", 0, 100_000_000, 500_000,
                                step=100_000)

tarama_imzasi = (evren, lookback, ai_sens, cci_len, long_th, gc_filter)

st.markdown(
    '<div class="hdr"><h1>BIST Long Tarayıcı</h1>'
    '<span class="badge">Günlük</span></div>'
    '<div class="sub">Global-100 Trade Intelligence indikatörünün otomatik '
    'taraması. Ön eleme aracıdır, yatırım tavsiyesi değildir.</div>',
    unsafe_allow_html=True,
)

if "sonuc" not in st.session_state:
    st.session_state.sonuc = None
    st.session_state.frames = {}
    st.session_state.imza = None

if calistir:
    syms, kaynak = load_symbols(evren == "Tüm BIST")
    with st.spinner(f"{len(syms)} hisse için veri indiriliyor…"):
        frames = load_prices(tuple(syms))
    cfg = Settings(ai_sens=ai_sens, cci_len=cci_len, long_threshold=long_th,
                   use_gc_filter=gc_filter)
    rows = []
    bar = st.progress(0.0, text="İndikatör hesaplanıyor")
    for i, (sym, df) in enumerate(frames.items()):
        try:
            res = compute(df, cfg)
        except Exception:
            continue
        r = last_row_summary(sym, res, lookback=lookback)
        if r["AI Buy"] or r["CCI Long"]:
            r["Sinyal"] = _label(r)
            rows.append(r)
        if i % 25 == 0:
            bar.progress(i / max(len(frames), 1), text="İndikatör hesaplanıyor")
    bar.empty()
    st.session_state.frames = frames
    st.session_state.sonuc = pd.DataFrame(rows)
    st.session_state.zaman = dt.datetime.now(TZ)
    st.session_state.evren_boyut = len(frames)
    st.session_state.kaynak = kaynak
    st.session_state.imza = tarama_imzasi
    st.session_state.veri_tarihi = max(
        (x.index[-1].date() for x in frames.values()), default=None)

sonuc = st.session_state.sonuc

if sonuc is None:
    st.info("Soldaki panelden ayarları seçip **Taramayı çalıştır**'a basın. "
            "İlk tarama birkaç dakika sürer, sonrakiler önbellekten gelir.")
    st.stop()

if st.session_state.imza != tarama_imzasi:
    st.warning("Tarama ayarlarını değiştirdiniz. Aşağıdaki liste hâlâ eski "
               "ayarlarla üretildi — **Taramayı çalıştır**'a basın.")

# ---------------------------------------------------------------------- filtre
d = sonuc.copy()
if not d.empty:
    if sadece_kesisim:
        d = d[d["AI Buy"] & d["CCI Long"]]
    else:
        mask = pd.Series(False, index=d.index)
        if f_ai:
            mask |= d["AI Buy"]
        if f_cci:
            mask |= d["CCI Long"]
        d = d[mask]
    if sadece_golden:
        d = d[d["Bolge"] == "GOLDEN"]
    d = d[(d["AL"] >= min_al) & (d["Hacim"] >= min_hacim)
          & (d["ADX"].fillna(0) >= min_adx)]
    d = d.sort_values(["Strong Buy", "AL", "YZ Guven %"], ascending=False)

# --------------------------------------------------------------- ozet kartlari
kartlar = [
    (st.session_state.evren_boyut, "taranan hisse", "inherit"),
    (len(d), "sinyal veren", ACCENT),
    (int(d["Strong Buy"].sum()) if not d.empty else 0, "Strong Buy", ACCENT),
    (int((d["AI Buy"] & d["CCI Long"]).sum()) if not d.empty else 0,
     "AI Buy + CCI Long", UP),
]
st.markdown(
    '<div class="cards">'
    + "".join(f'<div class="card"><div class="n" style="color:{c}">{n}</div>'
              f'<div class="l">{lbl}</div></div>' for n, lbl, c in kartlar)
    + "</div>",
    unsafe_allow_html=True,
)

vt = st.session_state.veri_tarihi
bayat = bool(vt) and vt != dt.datetime.now(TZ).date()
st.markdown(
    f'<div class="meta">Son tarama <b>{st.session_state.zaman:%d.%m.%Y %H:%M}</b>'
    f' · sembol kaynağı <b>{st.session_state.kaynak}</b>'
    + (f' · veri <b>{vt:%d.%m.%Y}</b>' if vt else "")
    + (f' <span style="color:{DOWN}">⚠ bugüne ait değil</span>' if bayat else "")
    + "</div>",
    unsafe_allow_html=True,
)

if d.empty:
    st.warning("Seçilen kriterlerde sinyal yok. Minimum SBS skorunu düşürmeyi "
               "veya sinyal tazeliğini artırıp yeniden taramayı deneyin.")
    st.stop()

# ----------------------------------------------------------------------- tablo
st.markdown('<div class="sect">Sinyal veren hisseler</div>', unsafe_allow_html=True)

tab = d[["Hisse", "Sinyal", "Fiyat", "Degisim %", "AL", "YZ Guven %", "CCI",
         "ADX", "Supertrend", "Bolge", "Volatilite %", "Hacim"]].copy()
tab["Hacim"] = (tab["Hacim"] / 1_000_000).round(2)
tab = tab.rename(columns={"Degisim %": "Değişim %", "Hacim": "Hacim (M)",
                          "YZ Guven %": "YZ Güven", "Bolge": "Bölge",
                          "Volatilite %": "Volatilite"})

# Genis ekran: tam tablo. Telefon: kart listesi. Ikisi de her zaman uretilir,
# hangisinin gorunecegine CSS medya sorgusu karar verir (Python ekran
# genisligini bilemez).
try:
    kap = st.container(key="tablo_genis")
except TypeError:            # eski Streamlit surumlerinde key destegi yok
    kap = st.container()

with kap:
    st.dataframe(
        tab, use_container_width=True, hide_index=True,
        height=min(600, 36 * (len(tab) + 1) + 8),
        column_config={
            "Hisse": st.column_config.TextColumn(width="small"),
            "Sinyal": st.column_config.TextColumn(width="medium"),
            "Fiyat": st.column_config.NumberColumn(format="%.2f"),
            "Değişim %": st.column_config.NumberColumn(format="%+.2f%%"),
            "AL": st.column_config.ProgressColumn(
                "AL / 26", min_value=0, max_value=26, format="%d",
                width="small"),
            "YZ Güven": st.column_config.NumberColumn(format="%.0f"),
            "CCI": st.column_config.NumberColumn(format="%.0f"),
            "ADX": st.column_config.NumberColumn(
                format="%.0f", help="Trend gücü. 20 altı yatay seyir."),
            "Volatilite": st.column_config.NumberColumn(format="%.1f%%"),
            "Hacim (M)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

ROZET = {"STRONG BUY": ACCENT, "AI Buy": UP, "CCI Long": BLUE,
         "Long Giris": VIOLET}


def _n(x, basamak: int = 0) -> str:
    """Kisa gecmisli hisselerde CCI/ADX bos gelebilir; karta 'nan' yazmasin."""
    return "—" if pd.isna(x) else f"{x:.{basamak}f}"


def _kart(r: pd.Series) -> str:
    deg = 0.0 if pd.isna(r["Degisim %"]) else float(r["Degisim %"])
    dr = UP if deg >= 0 else DOWN
    ok = "▲" if deg >= 0 else "▼"
    rozetler = "".join(
        f'<span class="hk-rozet" style="background:{ROZET.get(t, GRID)}26;'
        f'color:{ROZET.get(t, GRID)}">{t}</span>'
        for t in (x.strip() for x in str(r["Sinyal"]).split("+")) if t
    )
    oran = min(max(int(r["AL"]) / 26, 0), 1) * 100
    barrenk = ACCENT if r["Strong Buy"] else UP
    hacim = r["Hacim"] / 1_000_000
    return (
        f'<div class="hk">'
        f'<div class="hk-ust"><span class="hk-ad">{r["Hisse"]}</span>'
        f'<span class="hk-fiyat">{r["Fiyat"]:.2f}'
        f'<span style="color:{dr};font-size:.8rem;margin-left:.4rem">'
        f'{ok}{abs(deg):.2f}%</span></span></div>'
        f'<div>{rozetler}</div>'
        f'<div class="hk-bar"><span style="width:{oran:.0f}%;'
        f'background:{barrenk}"></span></div>'
        f'<div class="hk-alt">'
        f'<span>AL <b>{int(r["AL"])}/26</b></span>'
        f'<span>YZ <b>{_n(r["YZ Guven %"])}</b></span>'
        f'<span>CCI <b>{_n(r["CCI"])}</b></span>'
        f'<span>ADX <b>{_n(r["ADX"])}</b></span>'
        f'<span>ST <b>{r["Supertrend"]}</b></span>'
        f'<span>Bölge <b>{r["Bolge"]}</b></span>'
        f'<span>Hacim <b>{_n(hacim, 1)}M</b></span>'
        f'</div></div>'
    )


st.markdown(
    '<div class="mobil-liste">'
    + "".join(_kart(r) for _, r in d.iterrows())
    + "</div>",
    unsafe_allow_html=True,
)

st.download_button("CSV indir", d.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"bist_long_{dt.datetime.now(TZ):%Y%m%d}.csv",
                   mime="text/csv")

# ----------------------------------------------------------------------- detay
st.markdown('<div class="sect">Hisse detayı</div>', unsafe_allow_html=True)
secim = st.selectbox("Hisse", d["Hisse"].tolist(), label_visibility="collapsed")

df = st.session_state.frames.get(secim)
if df is not None:
    res = hesapla(df, ai_sens, cci_len, long_th, gc_filter)
    tail, px = res.tail(180), df.tail(180)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.035)
    fig.add_trace(go.Candlestick(
        x=px.index, open=px["open"], high=px["high"], low=px["low"],
        close=px["close"], name=secim,
        increasing=dict(line=dict(color=UP, width=1), fillcolor=UP),
        decreasing=dict(line=dict(color=DOWN, width=1), fillcolor=DOWN),
    ), row=1, col=1)

    for col, color, name, w in [("ema_50", BLUE, "EMA 50", 1.2),
                                ("ema_200", VIOLET, "EMA 200", 1.2),
                                ("base_ai", ACCENT, "YZ Şerit", 1.6)]:
        fig.add_trace(go.Scatter(x=tail.index, y=tail[col], name=name,
                                 line=dict(color=color, width=w)), row=1, col=1)

    for kolon, renk, ad, boy in [("STRONG_BUY", ACCENT, "Strong Buy", 13),
                                 ("AI_BUY", UP, "AI Buy", 10),
                                 ("CCI_LONG", BLUE, "CCI Long", 9)]:
        s = tail[tail[kolon]]
        if len(s):
            fig.add_trace(go.Scatter(
                x=s.index, y=s["close"] * 0.965, mode="markers", name=ad,
                marker=dict(symbol="triangle-up", size=boy, color=renk,
                            line=dict(width=0))), row=1, col=1)

    fig.add_trace(go.Scatter(x=tail.index, y=tail["cci"], name="CCI",
                             line=dict(color=GRID, width=1.2)), row=2, col=1)
    for y, dash in [(long_th, "dot"), (0, "solid"), (-long_th, "dot")]:
        fig.add_hline(y=y, line=dict(color=GRID, width=1, dash=dash),
                      opacity=.45, row=2, col=1)

    # Saydam zemin: grafik sayfanin temasini alir, tema degisince uyumlu kalir.
    fig.update_layout(
        height=460, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=GRID, size=11), margin=dict(l=4, r=4, t=4, b=4),
        xaxis_rangeslider_visible=False, hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor="rgba(138,154,171,.18)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(138,154,171,.18)", zeroline=False)
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})

    st.markdown('<div class="sect">SBS detayı — 26 gösterge</div>',
                unsafe_allow_html=True)
    last = res.iloc[-1]
    detay = pd.DataFrame({
        "Gösterge": SBS_NAMES,
        "Durum": ["AL" if last["sbs_" + n] else "SAT" for n in SBS_NAMES],
    })
    stil = {"AL": f"background-color:{UP}30;color:{UP};font-weight:600",
            "SAT": f"background-color:{DOWN}30;color:{DOWN};font-weight:600"}
    a, b = st.columns(2, gap="medium")
    for kol, parca in [(a, detay.iloc[:13]), (b, detay.iloc[13:])]:
        kol.dataframe(
            parca.style.map(lambda v: stil.get(v, ""), subset=["Durum"]),
            hide_index=True, use_container_width=True, height=36 * 14,
            column_config={"Durum": st.column_config.TextColumn(width="small")},
        )
