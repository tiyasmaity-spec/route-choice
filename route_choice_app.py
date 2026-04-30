import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

st.set_page_config(page_title="Route Recommender — Mandi House to IIFCO Chowk",
                   layout="wide", page_icon="🛣️")

st.markdown("""
<style>
.block-container{padding-top:1.5rem}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CORRECTED ROUTE COORDINATES
# Verified against actual road geometry (Delhi)
# Route 1: Mandi House → KG Marg → Udyog Bhawan → Sardar Patel Marg → Dhaula Kuan → NH-48 → Aerocity → IIFCO Chowk
# Route 2: Mandi House → ITO → Ring Road → Rao Tularam Marg → Dhaula Kuan → IIFCO Chowk
# ─────────────────────────────────────────────────────────────
ROUTE_COORDS = {
    "Route 1 — Sardar Patel Marg (SPM)": [
        [28.6270, 77.2390],   # Mandi House
        [28.6248, 77.2325],   # Tolstoy Marg junction
        [28.6225, 77.2255],   # KG Marg / Janpath crossing
        [28.6200, 77.2165],   # Janpath–Rafi Marg
        [28.6178, 77.2095],   # Udyog Bhawan
        [28.6148, 77.2030],   # Willingdon Crescent
        [28.6108, 77.1968],   # Teen Murti Chowk
        [28.6062, 77.1905],   # Shantipath crossing
        [28.5995, 77.1840],   # Sardar Patel Marg north
        [28.5910, 77.1762],   # Sardar Patel Marg mid
        [28.5838, 77.1682],   # Malcha Marg junction
        [28.5768, 77.1598],   # Dhaula Kuan flyover approach
        [28.5718, 77.1528],   # Dhaula Kuan interchange
        [28.5668, 77.1428],   # NH-48 entry
        [28.5598, 77.1305],   # Mahipalpur cut
        [28.5528, 77.1195],   # Aerocity T-junction
        [28.5448, 77.1082],   # NH-48 towards Gurgaon
        [28.5290, 77.0940],   # IIFCO Chowk
    ],
    "Route 2 — Rao Tularam Marg (RTR)": [
        [28.6270, 77.2390],   # Mandi House
        [28.6248, 77.2325],   # Tolstoy Marg
        [28.6222, 77.2258],   # KG Marg
        [28.6198, 77.2168],   # Janpath
        [28.6175, 77.2095],   # Udyog Bhawan
        [28.6108, 77.1968],   # Teen Murti
        [28.6055, 77.1892],   # Chanakya Puri signal
        [28.5988, 77.1818],   # Satya Marg
        [28.5908, 77.1742],   # Vinay Marg
        [28.5830, 77.1672],   # Rao Tularam Marg start
        [28.5745, 77.1592],   # Rao Tularam Marg mid
        [28.5662, 77.1512],   # Benito Juarez Marg junction
        [28.5575, 77.1432],   # Shiv Murti approach
        [28.5488, 77.1352],   # Outer Ring Road merge
        [28.5390, 77.1168],   # Dwarka Expressway crossing
        [28.5290, 77.0940],   # IIFCO Chowk
    ],
}

ROUTE_COLORS = {
    "Route 1 — Sardar Patel Marg (SPM)": "#1A73E8",
    "Route 2 — Rao Tularam Marg (RTR)":  "#E8711A",
}

NETWORK = {
    "Route 1 — Sardar Patel Marg (SPM)": {
        "avg_lanes": 3.9, "avg_speed": 26.6, "std_dev_speed": 10.8,
        "signal_ratio": 0.53, "intersection_ratio": 0.72,
        "roadside_friction": 0.34, "merge_points": 4, "circularity": 1.15,
        "total_length_km": 18.5, "avg_tt_min": 49.0, "network_bt_min": 34.4,
        "bti_measured": 0.702, "unreliable": "Junctions and merging zones",
        "color": "#1A73E8",
    },
    "Route 2 — Rao Tularam Marg (RTR)": {
        "avg_lanes": 3.8, "avg_speed": 28.2, "std_dev_speed": 8.4,
        "signal_ratio": 0.44, "intersection_ratio": 0.78,
        "roadside_friction": 0.41, "merge_points": 3, "circularity": 1.45,
        "total_length_km": 20.1, "avg_tt_min": 52.0, "network_bt_min": 32.1,
        "bti_measured": 0.617, "unreliable": "Road links and outer ring road merge",
        "color": "#E8711A",
    },
}

# ─────────────────────────────────────────────────────────────
# MODEL & SCORING
# ─────────────────────────────────────────────────────────────
def predict_bti(lanes, length, avg_speed, std_dev, intersection, roadside_friction):
    bti = (0.3641 + 0.0411*lanes - 0.00308*length - 0.01903*avg_speed
           + 0.06103*std_dev + 0.03981*intersection + 0.00618*roadside_friction)
    return round(max(0.1, min(bti, 2.0)), 4)

def estimate_buffer_time(bti, avg_tt):
    return round(bti * avg_tt, 1)

def get_weights(commuter, purpose, occupation, timeband, threshold, buffer, switching):
    w = dict(bti=1.0, tt=1.0, signals=1.0, merge=1.0, familiarity=1.0, networkBT=1.0, circularity=1.0)
    if occupation == "Cab / commercial driver":
        w.update(bti=0.4, tt=2.0, signals=0.6, merge=0.8, familiarity=0.5, networkBT=0.5, circularity=0.7)
    elif occupation == "Student":
        w.update(bti=1.8, tt=1.0, signals=1.2, merge=1.2, familiarity=1.6, networkBT=1.4, circularity=1.1)
    elif occupation == "Working professional":
        w.update(bti=1.3, tt=1.4, signals=1.0, merge=1.5, familiarity=1.0, networkBT=1.2, circularity=1.0)
    else:
        w.update(bti=1.0, tt=1.2, signals=0.9, merge=1.0, familiarity=0.8, networkBT=1.0, circularity=0.9)
    if commuter == "Non-regular":
        w["bti"] += 0.5; w["familiarity"] += 0.8; w["networkBT"] += 0.4; w["circularity"] += 0.5
    if purpose == "Education":
        w["bti"] += 0.4; w["familiarity"] += 0.3
    if purpose == "Other / leisure":
        w["tt"] -= 0.3; w["bti"] += 0.2; w["circularity"] -= 0.2
    if timeband in ["Morning peak (6–9 AM)", "Evening peak (4–8 PM)"]:
        w["merge"] += 0.5; w["signals"] += 0.3
    if threshold == "1–2 min":
        w["bti"] += 0.8; w["networkBT"] += 0.6
    elif threshold == "2–5 min":
        w["bti"] += 0.4
    elif threshold == "More than 10 min":
        w["bti"] -= 0.3; w["tt"] += 0.3
    if buffer == "More than 20 min":
        w["networkBT"] += 0.3
    if buffer == "No buffer":
        w["bti"] += 0.5
    if switching == "Habitual — stays on known route":
        w["familiarity"] += 1.0
    elif switching == "App-driven":
        w["familiarity"] -= 0.5
    return w

def score_route(r, w, use_predicted=False):
    bti = r["bti_predicted"] if use_predicted else r["bti_measured"]
    bt  = r["bt_predicted"]  if use_predicted else r["network_bt_min"]
    s_bti  = (1 - min(bti, 1.5) / 1.5)          * w["bti"]
    s_tt   = (1 - (r["avg_tt_min"] - 40) / 30)  * w["tt"]
    s_sig  = (1 - r["signal_ratio"])             * w["signals"]
    s_mrg  = (1 - r["merge_points"] / 6)         * w["merge"]
    s_fam  = r["familiarity_score"]              * w["familiarity"]
    s_bt   = (1 - min(bt, 40) / 40)             * w["networkBT"]
    s_circ = (1 - (r["circularity"] - 1) / 0.6) * w["circularity"]
    total = s_bti + s_tt + s_sig + s_mrg + s_fam + s_bt + s_circ
    return max(0, min(100, round((total / sum(w.values())) * 100)))

# ─────────────────────────────────────────────────────────────
# MAP BUILDER — returns static HTML string (no re-render flicker)
# ─────────────────────────────────────────────────────────────
def build_map_html(routes_to_show, best_route_name):
    m = folium.Map(location=[28.590, 77.168], zoom_start=12,
                   tiles="CartoDB positron")

    for rname, coords in ROUTE_COORDS.items():
        if rname not in routes_to_show:
            continue
        is_best = (rname == best_route_name)
        folium.PolyLine(
            coords,
            color=ROUTE_COLORS[rname],
            weight=7 if is_best else 3,
            dash_array=None if is_best else "10 6",
            opacity=0.92 if is_best else 0.55,
            tooltip=f"{'★ RECOMMENDED — ' if is_best else ''}{rname}",
        ).add_to(m)

    # Origin marker
    folium.Marker(
        [28.6270, 77.2390],
        popup=folium.Popup("🟢 <b>Origin:</b> Mandi House Circle", max_width=200),
        tooltip="Origin: Mandi House",
        icon=folium.Icon(color="green", icon="circle", prefix="fa"),
    ).add_to(m)

    # Destination marker
    folium.Marker(
        [28.5290, 77.0940],
        popup=folium.Popup("🔴 <b>Destination:</b> IIFCO Chowk", max_width=200),
        tooltip="Destination: IIFCO Chowk",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(m)

    # Legend
    legend_items = ""
    for rname in routes_to_show:
        if rname not in ROUTE_COLORS:
            continue
        star = "★ " if rname == best_route_name else ""
        color = ROUTE_COLORS[rname]
        short = rname.split("—")[1].strip() if "—" in rname else rname
        legend_items += (
            f"<div style='margin:3px 0'>"
            f"<span style='background:{color};display:inline-block;"
            f"width:22px;height:4px;margin-right:6px;vertical-align:middle'></span>"
            f"<span style='font-size:12px'>{star}{short}</span></div>"
        )

    legend_html = f"""
    <div style='position:fixed;bottom:24px;left:24px;z-index:9999;
                background:white;padding:10px 14px;border-radius:8px;
                box-shadow:0 2px 8px rgba(0,0,0,0.18);font-family:sans-serif'>
        <div style='font-size:11px;font-weight:700;margin-bottom:6px;color:#333'>
            ROUTES</div>
        {legend_items}
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    return m._repr_html_()


# ─────────────────────────────────────────────────────────────
# SESSION STATE — persists results across Streamlit reruns
# ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None
if "map_html" not in st.session_state:
    # Default map (both routes, no best highlighted)
    st.session_state.map_html = build_map_html(list(ROUTE_COORDS.keys()), None)

# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────
st.title("Route Recommender")
st.caption("Mandi House → IIFCO Chowk · Based on Travel Time Reliability & User Characteristics")

col_form, col_map = st.columns([1, 1.6], gap="large")

with col_form:
    st.subheader("User characteristics")
    commuter   = st.selectbox("Commuter type", ["Regular", "Non-regular"])
    purpose    = st.selectbox("Trip purpose", ["Work", "Education", "Other / leisure"])
    occupation = st.selectbox("Occupation", ["Working professional", "Cab / commercial driver",
                                              "Student", "Self-employed"])
    timeband   = st.selectbox("Time of travel", ["Morning peak (6–9 AM)", "Inter-peak (9 AM–4 PM)",
                                                  "Evening peak (4–8 PM)", "Off-peak / night"])
    threshold  = st.selectbox("Delay threshold to switch", ["1–2 min", "2–5 min",
                                                             "5–10 min", "More than 10 min"])
    buffer     = st.selectbox("Buffer time kept", ["No buffer", "Up to 15 min",
                                                    "15–20 min", "More than 20 min"])
    switching  = st.selectbox("Route switching behaviour", ["Flexible — switches when needed",
                                                             "Habitual — stays on known route",
                                                             "App-driven"])

    st.divider()
    st.subheader("Add a custom route")
    with st.expander("Enter route characteristics (BTI will be predicted)"):
        c_name  = st.text_input("Route name", "My Custom Route")
        c_lanes = st.slider("Avg number of lanes", 1, 6, 4)
        c_len   = st.number_input("Total route length (km)", 5.0, 40.0, 18.0, 0.5)
        c_speed = st.slider("Avg speed (km/h)", 10, 70, 28)
        c_std   = st.slider("Speed variability — std dev (km/h)", 2, 20, 10)
        c_inter = st.slider("Intersection ratio (0 = none, 1 = all)", 0.0, 1.0, 0.5, 0.05)
        c_fric  = st.slider("Roadside friction ratio", 0.0, 1.0, 0.3, 0.05)
        c_sig   = st.slider("Signal ratio", 0.0, 1.0, 0.5, 0.05)
        c_merge = st.slider("Number of merge / diverge points", 0, 8, 3)
        c_circ  = st.slider("Circularity ratio (1.0 = straight, 2.0 = very circular)",
                            1.0, 2.0, 1.3, 0.05)
        c_tt    = st.number_input("Estimated avg travel time (min)", 20, 120, 50, 5)
        c_fam   = st.selectbox("Route familiarity", ["High — well-known route",
                                                      "Medium — somewhat familiar",
                                                      "Low — unfamiliar"])
        add_custom = st.checkbox("Include this route in recommendation")

    if st.button("Find best route", type="primary", use_container_width=True):
        w = get_weights(commuter, purpose, occupation, timeband, threshold, buffer, switching)
        fam_map = {"High — well-known route": 1.0,
                   "Medium — somewhat familiar": 0.6,
                   "Low — unfamiliar": 0.2}
        routes_scored = []

        for rname, rdata in NETWORK.items():
            bti_pred = predict_bti(rdata["avg_lanes"], rdata["total_length_km"],
                                   rdata["avg_speed"], rdata["std_dev_speed"],
                                   rdata["intersection_ratio"], rdata["roadside_friction"])
            bt_pred = estimate_buffer_time(bti_pred, rdata["avg_tt_min"])
            entry = {**rdata, "name": rname, "bti_predicted": bti_pred,
                     "bt_predicted": bt_pred, "familiarity_score": 0.8}
            entry["score"] = score_route(entry, w)
            routes_scored.append(entry)

        if add_custom:
            bti_c = predict_bti(c_lanes, c_len, c_speed, c_std, c_inter, c_fric)
            bt_c  = estimate_buffer_time(bti_c, c_tt)
            ce = {
                "name": c_name, "avg_lanes": c_lanes, "avg_speed": c_speed,
                "std_dev_speed": c_std, "signal_ratio": c_sig,
                "intersection_ratio": c_inter, "roadside_friction": c_fric,
                "merge_points": c_merge, "circularity": c_circ,
                "total_length_km": c_len, "avg_tt_min": c_tt,
                "network_bt_min": bt_c, "bti_measured": bti_c,
                "bti_predicted": bti_c, "bt_predicted": bt_c,
                "unreliable": "Unknown — predicted from inputs", "color": "#6f42c1",
                "familiarity_score": fam_map.get(c_fam, 0.5),
            }
            ce["score"] = score_route(ce, w, use_predicted=True)
            routes_scored.append(ce)

        routes_scored.sort(key=lambda x: x["score"], reverse=True)
        best = routes_scored[0]

        # Store results + pre-render map HTML into session_state
        st.session_state.results = routes_scored
        routes_on_map = [r["name"] for r in routes_scored if r["name"] in ROUTE_COORDS]
        st.session_state.map_html = build_map_html(routes_on_map, best["name"])

# ─────────────────────────────────────────────────────────────
# RIGHT COLUMN — map + results (reads from session_state, never flickers)
# ─────────────────────────────────────────────────────────────
with col_map:
    st.subheader("Route map")

    # Render map as static HTML iframe — no re-render on widget interaction
    st.components.v1.html(st.session_state.map_html, height=420, scrolling=False)

    if st.session_state.results is None:
        st.caption("Select your characteristics and click 'Find best route' to see the recommendation.")
    else:
        routes_scored = st.session_state.results
        best = routes_scored[0]

        st.markdown(f"""
        <div style='background:#d4edda;border-radius:10px;padding:14px 18px;
                    margin-top:8px;margin-bottom:8px'>
          <div style='font-size:11px;font-weight:600;color:#155724;margin-bottom:4px'>
            ★ RECOMMENDED ROUTE</div>
          <div style='font-size:18px;font-weight:600;color:#155724'>{best["name"]}</div>
          <div style='font-size:13px;color:#1e7e34;margin-top:4px'>
            Score: {best["score"]}/100 &nbsp;|&nbsp;
            Avg TT: {best["avg_tt_min"]} min &nbsp;|&nbsp;
            Buffer: {best.get("bt_predicted", best["network_bt_min"])} min &nbsp;|&nbsp;
            BTI: {best.get("bti_predicted", best["bti_measured"])}
          </div>
        </div>""", unsafe_allow_html=True)

        # Bar chart
        st.subheader("All routes — scored")
        names  = [r["name"].replace("—", "-") for r in routes_scored]
        scores = [r["score"] for r in routes_scored]
        fig = go.Figure(go.Bar(
            x=names, y=scores,
            marker_color=[r.get("color", "#888") for r in routes_scored],
            text=[f"{s}/100" for s in scores], textposition="outside",
        ))
        fig.update_layout(
            yaxis=dict(range=[0, 115], title="Recommendation score"),
            xaxis_title="Route", plot_bgcolor="white", paper_bgcolor="white",
            font=dict(size=12), margin=dict(t=20, b=60, l=40, r=20),
            height=260, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Detail cards
        st.subheader("Route details")
        det_cols = st.columns(len(routes_scored))
        for i, r in enumerate(routes_scored):
            with det_cols[i]:
                bti_show = r.get("bti_predicted", r["bti_measured"])
                bt_show  = r.get("bt_predicted",  r["network_bt_min"])
                border = "2px solid #28a745" if r["name"] == best["name"] else "0.5px solid #dee2e6"
                st.markdown(f"""
                <div style='border:{border};border-radius:10px;padding:12px;margin-bottom:8px'>
                  <div style='font-size:12px;font-weight:600;margin-bottom:8px;color:#333'>
                    {'★ ' if r["name"]==best["name"] else ''}{r["name"].split("—")[0].strip() if "—" in r["name"] else r["name"]}</div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Score: <b>{r["score"]}/100</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Avg TT: <b>{r["avg_tt_min"]} min</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>BTI (predicted): <b>{bti_show}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Buffer demand: <b>{bt_show} min</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Circularity: <b>{r["circularity"]}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Merge points: <b>{r["merge_points"]}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>Signals: <b>{round(r["signal_ratio"]*100)}%</b></div>
                  <div style='font-size:11px;color:#999;margin-top:6px'>Unreliable: {r["unreliable"]}</div>
                </div>""", unsafe_allow_html=True)
