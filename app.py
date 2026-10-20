import json
import math
import random
import time
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from folium.plugins import AntPath, Fullscreen, MiniMap
from streamlit_folium import st_folium

BASE = Path(__file__).parent
st.set_page_config(page_title="IITR Waterlogging Dashboard", page_icon="💧", layout="wide")

WAVE = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 60' "
        "preserveAspectRatio='none'><path d='M0 30 Q150 0 300 30 T600 30 T900 30 T1200 30 V60 H0Z' "
        "fill='%2300c6ff'/></svg>")

# ================= GLOBAL CSS (dashboard + animations) =================
GLOBAL_CSS = """
<style>
@keyframes fadeUp {from {opacity:0; transform:translateY(20px);} to {opacity:1; transform:translateY(0);}}
@keyframes waveMove {0%,100% {background-position:0% 50%;} 50% {background-position:100% 50%;}}
@keyframes bob {0%,100% {transform:translateY(0);} 50% {transform:translateY(-7px);}}
@keyframes waveShift {0% {transform:translateX(0);} 100% {transform:translateX(-50%);}}
@keyframes wavePan {from {background-position:0 0;} to {background-position:-1200px 0;}}
@keyframes fillUp {from {height:0;}}
@keyframes riseWater {0% {height:0;} 100% {height:106vh;}}
@keyframes drainWater {0% {height:106vh;} 100% {height:0;}}
@keyframes slowRise {from {height:0;} to {height:14vh;}}
@keyframes bubbleUp {0% {transform:translateY(0) scale(.6); opacity:0;} 20% {opacity:.85;}
                     100% {transform:translateY(-95vh) scale(1.3); opacity:0;}}
@keyframes textIn {0% {opacity:0;} 40%,100% {opacity:1;}}
@property --ac {syntax:'<integer>'; initial-value:0; inherits:false;}
@property --bc {syntax:'<integer>'; initial-value:0; inherits:false;}
@keyframes cntA {from {--ac:0;} to {--ac:var(--a);}}
@keyframes cntB {from {--bc:0;} to {--bc:var(--b);}}

.hero {padding:26px 32px; border-radius:18px; color:white; margin-bottom:8px;
  background:linear-gradient(120deg,#0f4c81,#1e90ff,#00c6ff,#0f4c81); background-size:300% 300%;
  animation:waveMove 8s ease infinite, fadeUp .8s ease;}
.hero .title {font-size:2rem; font-weight:700; margin:0;}
.hero .sub {margin-top:6px; opacity:.92; font-size:1.02rem;}
.drop {display:inline-block; animation:bob 2.5s ease-in-out infinite;}
.badge {display:inline-block; margin-top:10px; padding:3px 12px; border-radius:20px;
  background:rgba(255,255,255,.22); font-size:.8rem; letter-spacing:.5px;}
.wave {height:24px; margin:0 0 14px; background:url("WAVE") repeat-x; background-size:600px 100%;
  opacity:.8; animation:wavePan 6s linear infinite;}
button[data-baseweb="tab"] {font-size:1.05rem;}

.ccard {background:rgba(30,144,255,.10); border:1px solid rgba(30,144,255,.35); padding:14px 16px;
  border-radius:14px; animation:fadeUp .7s ease; transition:transform .2s, box-shadow .2s;}
.ccard:hover {transform:translateY(-4px); box-shadow:0 8px 20px rgba(30,144,255,.28);}
.clabel {font-size:.85rem; opacity:.75;}
.cnum {font-size:1.9rem; font-weight:700; animation:cntA 1.5s ease-out forwards, cntB 1.5s ease-out forwards;
  counter-reset:ca var(--ac) cb var(--bc);}
.cnum::before {content:counter(ca);}
.cnum.dec::after {content:"." counter(cb, decimal-leading-zero);}

.gwrap {text-align:center;}
.glass {position:relative; width:110px; height:140px; margin:0 auto 6px; overflow:hidden;
  border:3px solid #1e90ff; border-radius:0 0 24px 24px; background:rgba(30,144,255,.08);}
.fill {position:absolute; bottom:0; left:0; width:100%;
  background:linear-gradient(#00c6ff,#0f4c81); animation:fillUp 2.2s ease-out;}
.fill::before {content:""; position:absolute; left:0; top:-12px; width:200%; height:14px;
  background:url("WAVE") repeat-x; background-size:50% 100%; animation:waveShift 2s linear infinite;}
.gv {position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-size:1.5rem; font-weight:700; color:white; text-shadow:0 1px 6px rgba(0,0,0,.6);}

.water {position:fixed; left:0; bottom:0; width:100vw; z-index:999990;
  background:linear-gradient(180deg,#00c6ff 0%,#1e90ff 35%,#0f4c81 75%,#082a4a 100%);}
.water::before {content:""; position:absolute; left:0; top:-58px; width:200%; height:60px;
  background:url("WAVE") repeat-x; background-size:50% 100%; animation:waveShift 2s linear infinite;}
.water.rise {animation:riseWater 3s ease-in forwards;}
.water.drain {animation:drainWater 2.4s ease-out forwards; pointer-events:none;}
.water.slow {animation:slowRise 50s linear 10s forwards; opacity:.55; z-index:6; pointer-events:none;}
.bubble {position:fixed; bottom:-20px; border-radius:50%; z-index:999991;
  border:2px solid rgba(255,255,255,.7); background:rgba(255,255,255,.2); animation:bubbleUp 3s ease-in infinite;}
.flood-text {position:fixed; top:42%; left:0; width:100vw; text-align:center; z-index:999992; color:white;
  font-size:2rem; font-weight:700; text-shadow:0 2px 10px rgba(0,0,0,.45); opacity:0;
  animation:textIn 3s ease forwards; animation-delay:.9s;}
</style>
""".replace("WAVE", WAVE)

# ================= INTRO-ONLY CSS: clouds -> lightning -> drizzle =================
INTRO_CSS = """
<style>
@keyframes cloudIn {from {opacity:0; transform:translateX(var(--from));} to {opacity:1; transform:translateX(0);}}
@keyframes cloudSway {from {transform:translateX(-2vw);} to {transform:translateX(2vw);}}
@keyframes boltFlash {0% {opacity:0;} 1% {opacity:1;} 2% {opacity:0;} 3% {opacity:1;} 5% {opacity:0;} 100% {opacity:0;}}
@keyframes skyFlash {0% {opacity:0;} 1% {opacity:.40;} 2% {opacity:0;} 3% {opacity:.30;} 5% {opacity:0;}
                     13% {opacity:0;} 14% {opacity:.40;} 15% {opacity:0;} 16% {opacity:.30;} 18% {opacity:0;}
                     30% {opacity:0;} 31% {opacity:.40;} 32% {opacity:0;} 33% {opacity:.30;} 35% {opacity:0;} 100% {opacity:0;}}
@keyframes drizzleIn {from {opacity:0;} to {opacity:1;}}
@keyframes drizzleFall {from {transform:translateY(-30px);} to {transform:translateY(105vh);}}
@keyframes typing {to {width:44ch;}}
@keyframes caret {50% {border-color:transparent;}}
@keyframes ripple {0% {box-shadow:0 0 0 0 rgba(0,198,255,.85);} 100% {box-shadow:0 0 0 24px rgba(0,198,255,0);}}

.stApp {background:linear-gradient(180deg,#060f1c 0%,#0d2540 55%,#16406b 100%) !important;}

/* 1) storm clouds slide in from both sides, then sway slowly */
.cloud-w {position:fixed; z-index:3; pointer-events:none; opacity:0; animation:cloudIn 3.5s ease-out forwards;}
.cloud {position:relative; width:10em; height:3em; border-radius:3em; background:rgba(58,72,98,.92);
  box-shadow:0 10px 22px rgba(0,0,0,.45); animation:cloudSway 9s ease-in-out infinite alternate;}
.cloud::before, .cloud::after {content:""; position:absolute; background:inherit; border-radius:50%;}
.cloud::before {width:4.6em; height:4.6em; left:1.4em; top:-2.2em;}
.cloud::after {width:3.6em; height:3.6em; right:1.6em; top:-1.5em;}

/* 2) lightning bolts (repeat every 10 s) + sky flash */
.sky-flash {position:fixed; inset:0; background:#cfe8ff; z-index:2; pointer-events:none; opacity:0;
  animation:skyFlash 10s infinite; animation-delay:4s;}
.bolt-w {position:fixed; top:60px; width:110px; height:52vh; z-index:4; pointer-events:none;
  filter:drop-shadow(0 0 10px #cfe8ff) drop-shadow(0 0 24px #7fc4ff);}
.bolt {width:100%; height:100%; opacity:0; background:linear-gradient(#ffffff,#d6ecff);
  clip-path:polygon(50% 0, 78% 0, 58% 36%, 82% 36%, 30% 100%, 42% 52%, 20% 52%);
  animation:boltFlash 10s infinite;}

/* 3) drizzle fades in after the lightning */
.drizzle {position:fixed; inset:0; z-index:5; pointer-events:none; opacity:0; animation:drizzleIn 4s ease 8s forwards;}
.dz {position:absolute; top:0; width:1px; height:14px; animation:drizzleFall linear infinite;
  background:linear-gradient(to bottom, rgba(255,255,255,0), rgba(190,225,255,.75));}

.typing {display:inline-block; overflow:hidden; white-space:nowrap; vertical-align:bottom; width:0;
  border-right:3px solid #fff; animation:typing 3s steps(42) forwards, caret .7s step-end infinite;}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {animation:ripple 1.6s infinite; border-radius:8px;}
.intro-card {max-width:760px; margin:10px auto; padding:22px 30px; border-radius:16px; color:white;
  background:rgba(30,144,255,.14); border:1px solid rgba(120,190,255,.45); backdrop-filter:blur(3px);
  text-align:center; animation:fadeUp 1s ease;}
.intro-card .label {font-size:.85rem; letter-spacing:1px; text-transform:uppercase; opacity:.75;}
.intro-card .name {font-size:1.35rem; font-weight:600; margin-top:4px;}
.intro-card .member {font-size:1.15rem; margin:3px 0;}
</style>
"""

# (top px, left %, size px, slide-in from, start delay s, sway duration s)
CLOUDS = "".join(
    f'<div class="cloud-w" style="top:{t}px; left:{x}%; font-size:{s}px; --from:{fr}; animation-delay:{d}s;">'
    f'<div class="cloud" style="animation-duration:{sw}s;"></div></div>'
    for t, x, s, fr, d, sw in [
        (-6, -4, 28, "-45vw", 0.0, 9), (14, 8, 30, "45vw", 0.4, 11), (-2, 20, 26, "-45vw", 0.8, 10),
        (16, 33, 32, "45vw", 1.2, 12), (-8, 45, 28, "-45vw", 1.6, 9), (12, 57, 30, "45vw", 2.0, 11),
        (-2, 69, 26, "-45vw", 2.4, 10), (14, 80, 31, "45vw", 2.8, 12), (-6, 90, 25, "45vw", 3.0, 9),
    ])

# (left %, first strike delay s) - strikes repeat every 10 s
BOLTS = "".join(
    f'<div class="bolt-w" style="left:{x}%;"><div class="bolt" style="animation-delay:{d}s;"></div></div>'
    for x, d in [(20, 4.0), (66, 5.3), (42, 7.0)])

_rng = random.Random(7)
DRIZZLE = '<div class="drizzle">' + "".join(
    f'<div class="dz" style="left:{_rng.uniform(0, 100):.1f}%; animation-duration:{_rng.uniform(1.4, 2.4):.2f}s; '
    f'animation-delay:-{_rng.uniform(0, 2.4):.2f}s; opacity:{_rng.uniform(0.3, 0.7):.2f};"></div>'
    for _ in range(60)) + "</div>"

BUBBLES = "".join(
    f'<div class="bubble" style="left:{l}%; width:{s}px; height:{s}px; animation-delay:{d}s;"></div>'
    for l, s, d in [(8, 14, .2), (20, 22, .8), (33, 12, .4), (47, 26, 1.1), (60, 16, .6), (72, 24, .1), (85, 14, .9), (93, 20, .5)])

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

for _k, _v in {"entered": False, "flooding": False, "just_entered": False}.items():
    st.session_state.setdefault(_k, _v)

# ================= INTRO PAGE =================
if not st.session_state.entered:
    slow = "" if st.session_state.flooding else '<div class="water slow"></div>'
    st.markdown(
        INTRO_CSS + '<div class="sky-flash"></div>' + CLOUDS + BOLTS + DRIZZLE + slow,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="hero" style="text-align:center; padding:48px 30px;">
  <div class="title"><span class="drop">💧</span> <span class="typing">Waterlogging Hotspot Detection using LiDAR</span></div>
  <div class="sub">IIT Roorkee Campus</div>
  <div class="badge">Made by Team 11 for CEC-201 Geospatial Engineering-II Project</div>
</div>
<div class="intro-card"><div class="label">Made by</div><div class="name">Sneha Verma</div></div>
<div class="intro-card"><div class="label">Team Leader</div><div class="name">Zubia Hasan</div></div>
<div class="intro-card"><div class="label">Other Team Members</div>
  <div class="member">Shoryajeet</div><div class="member">Suryavardhan</div>
  <div class="member">Vaibhav</div><div class="member">Yash</div></div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    _, mid, _ = st.columns([2, 1, 2])
    if mid.button("Enter Dashboard →", type="primary", use_container_width=True):
        st.session_state.flooding = True
        st.rerun()
    if st.session_state.flooding:
        st.markdown('<div class="water rise"></div>' + BUBBLES
                    + '<div class="flood-text">💧 Waterlogging in progress...</div>', unsafe_allow_html=True)
        time.sleep(3.3)
        st.session_state.update(flooding=False, entered=True, just_entered=True)
        st.rerun()
    st.stop()

if st.sidebar.button("⬅ Back to introduction"):
    st.session_state.entered = False
    st.rerun()
if st.session_state.just_entered:
    st.markdown('<div class="water drain"></div>', unsafe_allow_html=True)
    st.session_state.just_entered = False

# ================= DATA =================
gdf = gpd.read_file(BASE / "data" / "hotspots.geojson")
with open(BASE / "data" / "metrics.json") as f:
    metrics = json.load(f)
is_sample = bool(gdf["is_sample"].any()) if "is_sample" in gdf.columns else False
COLORS = {"Low": "#f1c40f", "Medium": "#e67e22", "High": "#c0392b"}


def severity(d):
    return "Low" if d < 0.3 else "Medium" if d < 0.6 else "High"


def card(label, value, dec=False):
    a = int(value)
    b = int(round((value - a) * 100)) if dec else 0
    return (f'<div class="ccard"><div class="clabel">{label}</div>'
            f'<div class="cnum {"dec" if dec else ""}" style="--a:{a}; --b:{b};"></div></div>')


def gauge(label, v):
    return (f'<div class="gwrap"><div class="glass"><div class="fill" style="height:{v * 100:.0f}%"></div>'
            f'<div class="gv">{v:.2f}</div></div><div class="clabel">{label}</div></div>')


# ================= HEADER =================
badge = '<div class="badge">SAMPLE DATA - not real results</div>' if is_sample else ""
st.markdown(
    f"""<div class="hero"><div class="title"><span class="drop">💧</span> Waterlogging Hotspots - IIT Roorkee</div>
<div class="sub">LiDAR-based depression detection: where water collects on campus, how deep, and how much.</div>{badge}</div>
<div class="wave"></div>""",
    unsafe_allow_html=True,
)

# ================= SIDEBAR =================
st.sidebar.header("Rainfall replay")
rain = st.sidebar.slider("Rainfall (mm)", 0, 200, 100, 10,
                         help="Illustrative: depths and volumes are scaled linearly from the 100 mm result.")
scale = rain / 100
gdf["depth_m"] = (gdf["depth_m"] * scale).round(2)
gdf["volume_m3"] = (gdf["volume_m3"] * scale).round(1)
gdf["severity"] = gdf["depth_m"].apply(severity)

st.sidebar.header("Filters")
min_depth = st.sidebar.slider("Minimum depth (m)", 0.0, 1.0, 0.0, 0.05)
min_area = st.sidebar.slider("Minimum area (m2)", 0, 1000, 0, 10)
levels = st.sidebar.multiselect("Severity", ["Low", "Medium", "High"], default=["Low", "Medium", "High"])
st.sidebar.header("Map options")
style = st.sidebar.radio("Map style", ["Street", "Satellite", "Dark"])
show_pulse = st.sidebar.checkbox("Ripple markers", value=True)
show_flow = st.sidebar.checkbox("Flowing water lines (illustrative)", value=True)

filtered = gdf[(gdf["depth_m"] > 0) & (gdf["depth_m"] >= min_depth) & (gdf["area_m2"] >= min_area)
               & (gdf["severity"].isin(levels))]
if filtered.empty:
    st.info("No hotspots match these filters. Raise the rainfall, lower the sliders or add severity levels.")
    st.stop()
focus = st.sidebar.selectbox("Focus on hotspot", ["All hotspots"] + filtered["id"].tolist())

# ================= TABS =================
tab_map, tab_chart, tab_table, tab_metrics = st.tabs(["🗺️ Map", "📊 Charts", "📋 Ranked table", "🎯 Accuracy"])

with tab_map:
    c = st.columns(4)
    c[0].markdown(card("Hotspots shown", len(filtered)), unsafe_allow_html=True)
    c[1].markdown(card("Total volume (m3)", round(filtered["volume_m3"].sum())), unsafe_allow_html=True)
    c[2].markdown(card("Deepest (m)", float(filtered["depth_m"].max()), dec=True), unsafe_allow_html=True)
    c[3].markdown(card("High severity", int((filtered["severity"] == "High").sum())), unsafe_allow_html=True)
    st.write("")

    tiles = {
        "Street": ("OpenStreetMap", "OpenStreetMap"),
        "Satellite": ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                      "Esri World Imagery"),
        "Dark": ("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", "CartoDB"),
    }
    tile_url, tile_attr = tiles[style]
    b = filtered.total_bounds
    centre, zoom = [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], 16
    if focus != "All hotspots":
        p = filtered[filtered["id"] == focus].iloc[0].geometry.representative_point()
        centre, zoom = [p.y, p.x], 18

    m = folium.Map(location=centre, zoom_start=zoom, tiles=tile_url, attr=tile_attr)
    if focus == "All hotspots" and len(filtered) > 1:
        m.fit_bounds([[b[1], b[0]], [b[3], b[2]]], max_zoom=17)

    m.get_root().header.add_child(folium.Element("""
<style>
.pulse {position:relative; width:14px; height:14px; border-radius:50%; background:var(--c);
        border:2px solid white; box-sizing:border-box;}
.pulse::before, .pulse::after {content:""; position:absolute; left:-2px; top:-2px; width:14px; height:14px;
        border-radius:50%; border:2px solid var(--c); box-sizing:border-box; animation:ring 2s ease-out infinite;}
.pulse::after {animation-delay:1s;}
@keyframes ring {0% {transform:scale(1); opacity:.9;} 100% {transform:scale(3.8); opacity:0;}}
path.leaflet-interactive {transform-box:fill-box; transform-origin:center; animation:grow 1.4s ease-out;}
@keyframes grow {from {transform:scale(0); fill-opacity:0;}}
</style>"""))
    m.get_root().html.add_child(folium.Element("""
<div style="position:fixed; bottom:25px; left:25px; z-index:9999; background:rgba(255,255,255,.93);
     padding:10px 14px; border-radius:10px; font-size:13px; color:#222; box-shadow:0 2px 8px rgba(0,0,0,.3);">
<b>Water depth</b><br><span style="color:#f1c40f">&#9679;</span> Low (&lt; 0.3 m)<br>
<span style="color:#e67e22">&#9679;</span> Medium (0.3 - 0.6 m)<br>
<span style="color:#c0392b">&#9679;</span> High (&gt; 0.6 m)</div>"""))

    folium.GeoJson(
        filtered[["id", "rank", "depth_m", "area_m2", "volume_m3", "severity", "geometry"]],
        style_function=lambda ft: {"fillColor": COLORS[ft["properties"]["severity"]], "color": "white",
                                   "weight": 1.5, "fillOpacity": 0.65},
        highlight_function=lambda ft: {"weight": 3, "fillOpacity": 0.9},
        tooltip=folium.GeoJsonTooltip(fields=["id", "rank", "depth_m", "area_m2", "volume_m3"],
                                      aliases=["ID", "Rank", "Depth (m)", "Area (m2)", "Volume (m3)"]),
    ).add_to(m)

    for _, r in filtered.iterrows():
        pt = r.geometry.representative_point()
        if show_flow:  # illustrative: replace with real flow-accumulation lines from the pipeline
            rg = random.Random(r["id"])
            for _i in range(3):
                ang, dist = rg.uniform(0, 6.28), rg.uniform(0.0004, 0.0008)
                s = [pt.y + dist * math.sin(ang), pt.x + dist * math.cos(ang)]
                mid = [(s[0] + pt.y) / 2 + rg.uniform(-1, 1) * 8e-5, (s[1] + pt.x) / 2 + rg.uniform(-1, 1) * 8e-5]
                AntPath([s, mid, [pt.y, pt.x]], color="#00c6ff", weight=3, delay=900,
                        dash_array=[8, 18], pulse_color="#ffffff").add_to(m)
        if show_pulse:
            folium.Marker(
                [pt.y, pt.x],
                icon=folium.DivIcon(html=f'<div class="pulse" style="--c:{COLORS[r["severity"]]};"></div>',
                                    icon_size=(14, 14), icon_anchor=(7, 7)),
                tooltip=f"<b>{r['id']}</b> - Rank {r['rank']}<br>Depth: {r['depth_m']} m<br>Volume: {r['volume_m3']} m3",
            ).add_to(m)

    Fullscreen().add_to(m)
    MiniMap(toggle_display=True).add_to(m)
    st_folium(m, height=560, use_container_width=True, returned_objects=[])
    if show_flow:
        st.caption("Flowing lines are illustrative until real flow-accumulation results replace them.")

with tab_chart:
    st.markdown('<div class="wave"></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Volume by hotspot (m3)")
        st.bar_chart(pd.DataFrame(filtered[["id", "volume_m3"]]).set_index("id"))
    with right:
        st.subheader("Depth by hotspot (m)")
        st.bar_chart(pd.DataFrame(filtered[["id", "depth_m"]]).set_index("id"))
    st.subheader("Hotspots per severity level")
    st.bar_chart(filtered["severity"].value_counts().reindex(["Low", "Medium", "High"]).fillna(0))

with tab_table:
    table = pd.DataFrame(filtered.drop(columns=["geometry", "is_sample"], errors="ignore"))
    table = table.sort_values("volume_m3", ascending=False)
    st.dataframe(
        table, hide_index=True,
        column_config={
            "volume_m3": st.column_config.ProgressColumn(
                "Volume (m3)", min_value=0.0, max_value=max(float(gdf["volume_m3"].max()), 1.0), format="%.1f"),
            "depth_m": st.column_config.NumberColumn("Depth (m)", format="%.2f"),
        },
    )
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download table (CSV)", table.to_csv(index=False), "hotspots.csv", "text/csv")
    d2.download_button("⬇️ Download hotspots (GeoJSON)", filtered.to_json(), "hotspots_filtered.geojson",
                       "application/geo+json")

with tab_metrics:
    if metrics.get("is_sample"):
        st.warning("SAMPLE metrics - replace with real results before submission.")
    g = st.columns(5)
    for col, (lab, key) in zip(g[:4], [("Precision", "precision"), ("Recall", "recall"), ("F1", "f1"), ("IoU", "iou")]):
        col.markdown(gauge(lab, float(metrics[key])), unsafe_allow_html=True)
    g[4].markdown(card("DTM RMSE (m)", float(metrics["dtm_rmse_m"]), dec=True), unsafe_allow_html=True)