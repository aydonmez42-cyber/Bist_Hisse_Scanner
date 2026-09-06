"""
BIST Long Tarayici — dashboard.

Calistirmak icin:
    streamlit run bist_screener/app.py
"""

from __future__ import annotations

import datetime as dt
import hmac
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from bist_screener import data as bist_data
from bist_screener.engine import SBS_NAMES, Settings, compute, last_row_summary
from bist_screener.scan import _label

st.set_page_config(page_title="BIST Long Tarayici", page_icon="◆", layout="wide")

# Palet: gece mavisi zemin, sinyal icin tek bir turkuaz vurgu.
INK = "#0E1620"
PANEL = "#16202C"
LINE = "#243444"
TEXT = "#D7E0EA"
MUTED = "#7B8B9C"
UP = "#2FBF71"
DOWN = "#E0533D"
ACCENT = "#00CED1"

st.markdown(
    f"""
    <style>
      .stApp {{ background:{INK}; color:{TEXT}; }}
      section[data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {LINE}; }}
      h1,h2,h3 {{ color:{TEXT}; font-weight:600; letter-spacing:-.01em; }}
      .rule {{ border-top:1px solid {LINE}; margin:1.1rem 0 .9rem; }}
      .stat {{ font-size:2rem; font-weight:650; line-height:1.1; color:{TEXT}; }}
      .statlabel {{ font-size:.78rem; color:{MUTED}; }}
      .tag {{ display:inline-block; padding:2px 9px; border-radius:3px;
              font-size:.72rem; font-weight:600; margin-right:5px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def gate() -> None:
    """
    DASHBOARD_PASSWORD ortam degiskeni tanimliysa parola sorar.
    Railway'de dashboard herkese acik bir URL alir; bu degiskeni mutlaka tanimlayin.
    Degisken bos birakilirsa kapi devre disi kalir (yerel kullanim icin).
    """
    sifre = os.environ.get("DASHBOARD_PASSWORD", "").strip()
    if not sifre or st.session_state.get("acik"):
        return
    st.markdown("# BIST Long Tarayici")
    girilen = st.text_input("Parola", type="password")
    if girilen and hmac.compare_digest(girilen, sifre):
        st.session_state.acik = True
        st.rerun()
    elif girilen:
        st.error("Parola hatali.")
    st.stop()


gate()


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_prices(symbols: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    return bist_data.download(list(symbols))

@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_symbols(full: bool) -> list[str]:
    return bist_data.get_symbols(full_market=full)


def signal_chip(text: str) -> str:
    colors = {"STRONG BUY": ACCENT, "AI Buy": UP, "CCI Long": "#8AB4F8",
              "Long Giris": "#B49CF0"}
    parts = [p.strip() for p in text.split("+") if p.strip()]
    return "".join(
        f'<span class="tag" style="background:{colors.get(p, MUTED)}22;'
        f'color:{colors.get(p, MUTED)};border:1px solid {colors.get(p, MUTED)}55">{p}</span>'
        for p in parts
    )


# ------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### Tarama ayarlari")
    evren = st.radio("Hisse evreni", ["Tum BIST", "Hazir liste (~105)"],
                     index=0, horizontal=False)
    lookback = st.slider("Sinyal tazeligi (bar)", 1, 5, 1,
                         help="1 = sadece son kapanmis gun")
    min_hacim = st.number_input("Minimum hacim (lot)", 0, 100_000_000, 500_000,
                                step=100_000)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("### Sinyal filtresi")
    f_ai = st.checkbox("AI Buy", True)
    f_cci = st.checkbox("CCI Long", True)
    sadece_kesisim = st.checkbox("Sadece ikisi ayni anda", False)
    sadece_golden = st.checkbox("Sadece Golden Zone", False)
    min_al = st.slider("Minimum SBS AL skoru", 0, 26, 13)
    min_adx = st.slider("Minimum ADX", 0, 50, 0)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("### Indikator parametreleri")
    ai_sens = st.slider("Classifier Sensitivity", 5, 50, 25)
    cci_len = st.slider("CCI Length", 10, 60, 30)
    long_th = st.slider("Long Threshold", 0, 150, 50)
    gc_filter = st.checkbox("Altin/Olum kesisim filtresi", True)

    calistir = st.button("Taramayi calistir", type="primary", use_container_width=True)

cfg = Settings(ai_sens=ai_sens, cci_len=cci_len, long_threshold=long_th,
               use_gc_filter=gc_filter)

st.markdown("# BIST Long Tarayici")
st.caption("Global-100 Trade Intelligence indikatorunun BIST gunluk barlar uzerinde "
           "otomatik taramasi. Yatirim tavsiyesi degildir.")

if "sonuc" not in st.session_state:
    st.session_state.sonuc = None
    st.session_state.frames = {}

if calistir:
    syms = load_symbols(evren == "Tum BIST")
    with st.spinner(f"{len(syms)} hisse icin veri indiriliyor..."):
        frames = load_prices(tuple(syms))
    rows = []
    bar = st.progress(0.0, text="Indikator hesaplaniyor")
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
            bar.progress(i / max(len(frames), 1), text="Indikator hesaplaniyor")
    bar.empty()
    st.session_state.frames = frames
    st.session_state.sonuc = pd.DataFrame(rows)
    st.session_state.tarama_zamani = dt.datetime.now()
    st.session_state.evren_boyut = len(frames)

sonuc = st.session_state.sonuc

if sonuc is None:
    st.info("Soldaki panelden ayarlari secip **Taramayi calistir**'a basin. "
            "Ilk tarama tum piyasa icin birkac dakika surer, sonrakiler onbellekten gelir.")
    st.stop()

if sonuc.empty:
    st.warning("Secilen kriterlerde sinyal ureten hisse bulunamadi. "
               "Sinyal tazeligini artirmayi veya hacim esigini dusurmeyi deneyin.")
    st.stop()

# -------------------------------------------------------------------- filtre
d = sonuc.copy()
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
d = d[(d["AL"] >= min_al) & (d["Hacim"] >= min_hacim) & (d["ADX"].fillna(0) >= min_adx)]
d = d.sort_values(["Strong Buy", "AL", "YZ Guven %"], ascending=False)

# --------------------------------------------------------------------- ozet
c1, c2, c3, c4 = st.columns(4)
for col, val, lab in [
    (c1, st.session_state.evren_boyut, "taranan hisse"),
    (c2, len(d), "sinyal veren"),
    (c3, int(d["Strong Buy"].sum()), "Strong Buy"),
    (c4, int((d["AI Buy"] & d["CCI Long"]).sum()), "AI Buy + CCI Long"),
]:
    col.markdown(f'<div class="stat">{val}</div><div class="statlabel">{lab}</div>',
                 unsafe_allow_html=True)
st.caption(f"Son tarama: {st.session_state.tarama_zamani:%d.%m.%Y %H:%M}")
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

# -------------------------------------------------------------------- tablo
gosterim = d[["Hisse", "Sinyal", "Fiyat", "Degisim %", "AL", "SAT", "YZ Guven %",
              "CCI", "ADX", "Supertrend", "Bolge", "Volatilite %", "Hacim"]].copy()
gosterim["Hacim"] = (gosterim["Hacim"] / 1_000_000).round(2)
gosterim = gosterim.rename(columns={"Hacim": "Hacim (M lot)"})

st.dataframe(
    gosterim,
    use_container_width=True,
    hide_index=True,
    height=min(560, 42 * (len(gosterim) + 1)),
    column_config={
        "Degisim %": st.column_config.NumberColumn(format="%.2f%%"),
        "AL": st.column_config.ProgressColumn(min_value=0, max_value=26, format="%d"),
        "YZ Guven %": st.column_config.NumberColumn(format="%.1f"),
    },
)

st.download_button(
    "Listeyi CSV indir",
    d.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"bist_long_{dt.date.today():%Y%m%d}.csv",
    mime="text/csv",
)

# ------------------------------------------------------------------- detay
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown("## Hisse detayi")
secim = st.selectbox("Hisse", d["Hisse"].tolist(), label_visibility="collapsed")

df = st.session_state.frames.get(secim)
if df is not None:
    res = compute(df, cfg)
    tail = res.tail(180)
    px = df.tail(180)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.72, 0.28], vertical_spacing=0.04)
    fig.add_trace(go.Candlestick(
        x=px.index, open=px["open"], high=px["high"], low=px["low"], close=px["close"],
        increasing_line_color=UP, decreasing_line_color=DOWN, name=secim), row=1, col=1)
    for col, color, name in [("ema_50", "#2566F1", "EMA 50"),
                             ("ema_200", "#B06EF5", "EMA 200"),
                             ("base_ai", ACCENT, "YZ Serit")]:
        fig.add_trace(go.Scatter(x=tail.index, y=tail[col], line=dict(color=color, width=1.4),
                                 name=name), row=1, col=1)

    buys = tail[tail["AI_BUY"] | tail["STRONG_BUY"]]
    if len(buys):
        fig.add_trace(go.Scatter(
            x=buys.index, y=buys["close"] * 0.97, mode="markers",
            marker=dict(symbol="triangle-up", size=11, color=ACCENT), name="AI Buy"),
            row=1, col=1)
    cl = tail[tail["CCI_LONG"]]
    if len(cl):
        fig.add_trace(go.Scatter(
            x=cl.index, y=cl["close"] * 0.94, mode="markers",
            marker=dict(symbol="triangle-up", size=9, color="#8AB4F8"), name="CCI Long"),
            row=1, col=1)

    fig.add_trace(go.Scatter(x=tail.index, y=tail["cci"], line=dict(color=MUTED, width=1.3),
                             name="CCI"), row=2, col=1)
    for y, dash in [(long_th, "dot"), (0, "solid"), (-long_th, "dot")]:
        fig.add_hline(y=y, line=dict(color=LINE, width=1, dash=dash), row=2, col=1)

    fig.update_layout(
        height=560, paper_bgcolor=INK, plot_bgcolor=INK, font=dict(color=TEXT, size=11),
        margin=dict(l=8, r=8, t=8, b=8), xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.06, x=0, bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### SBS detayi — 26 gosterge")
    last = res.iloc[-1]
    detay = pd.DataFrame({
        "Gosterge": SBS_NAMES,
        "Sinyal": ["AL" if last["sbs_" + n] else "SAT" for n in SBS_NAMES],
    })
    a, b = st.columns(2)
    a.dataframe(detay.iloc[:13], hide_index=True, use_container_width=True)
    b.dataframe(detay.iloc[13:], hide_index=True, use_container_width=True)
