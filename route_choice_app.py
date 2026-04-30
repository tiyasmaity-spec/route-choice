import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(layout="wide")

# ==============================
# OSRM ROUTE FUNCTION
# ==============================

def get_route(start, end):
    url = f"http://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
    r = requests.get(url).json()
    coords = r['routes'][0]['geometry']['coordinates']
    return [(lat, lon) for lon, lat in coords]

# ==============================
# ROUTE DATA
# ==============================

route1 = {
    "name": "Route 1 — Sardar Patel Marg",
    "tt": 49,
    "bti": 0.70,
    "signals": 0.60,
    "circularity": 1.10
}

route2 = {
    "name": "Route 2 — Rao Tula Ram Marg",
    "tt": 52,
    "bti": 0.45,
    "signals": 0.40,
    "circularity": 1.40
}

# ==============================
# WEIGHTS FUNCTION (FIXED)
# ==============================

def get_weights(user):

    w = {
        "TT": 0.30,
        "BTI": 0.40,
        "Signals": 0.15,
        "Geometry": 0.15
    }

    # Delay sensitivity
    if user['threshold'] == "1–2 min":
        w["BTI"] += 0.25
        w["TT"] -= 0.10
    elif user['threshold'] == "5–10 min":
        w["BTI"] += 0.10
    elif user['threshold'] == ">10 min":
        w["TT"] += 0.20
        w["BTI"] -= 0.10

    # Buffer
    if user['buffer'] >= 20:
        w["BTI"] += 0.20
    else:
        w["TT"] += 0.10

    # Peak time
    if user['time'] in ["Morning peak (6–9 AM)", "Evening peak (4–8 PM)"]:
        w["BTI"] += 0.15
        w["Signals"] += 0.10

    # Signals preference
    if user['signals'] == "Avoid signals":
        w["Signals"] += 0.20

    # Geometry preference
    if user['geometry'] == "Prefer straight route":
        w["Geometry"] += 0.15

    # Normalize
    total = sum(w.values())
    for k in w:
        w[k] /= total

    return w

# ==============================
# SCORING FUNCTION (FIXED)
# ==============================

def score(route, w):

    s_tt = (1 / route["tt"]) * 100
    s_bti = (1 / route["bti"]) * 100
    s_sig = (1 - route["signals"]) * 100
    s_geo = (1 / route["circularity"]) * 100

    score = (
        w["TT"] * s_tt +
        w["BTI"] * s_bti +
        w["Signals"] * s_sig +
        w["Geometry"] * s_geo
    )

    return round(score, 2)

# ==============================
# UI
# ==============================

st.title("🚗 Route Recommendation System")

col1, col2 = st.columns(2)

with col1:

    commuter = st.selectbox("Commuter type", ["Regular", "Non-regular"])

    purpose = st.selectbox("Trip purpose", ["Work", "Education", "Leisure"])

    timeband = st.selectbox("Time of travel",
        ["Morning peak (6–9 AM)", "Inter-peak (9 AM–4 PM)",
         "Evening peak (4–8 PM)", "Off-peak / night"]
    )

    threshold = st.selectbox("Delay threshold",
        ["1–2 min", "5–10 min", ">10 min"]
    )

    buffer = st.slider("Buffer time (min)", 0, 30, 10)

    signals = st.selectbox("Signals preference",
        ["Okay with signals", "Avoid signals"]
    )

    geometry = st.selectbox("Route shape",
        ["Doesn’t matter", "Prefer straight route"]
    )

    if st.button("Find best route"):

        user = {
            "threshold": threshold,
            "buffer": buffer,
            "time": timeband,
            "signals": signals,
            "geometry": geometry
        }

        w = get_weights(user)

        score1 = score(route1, w)
        score2 = score(route2, w)

        best = route1 if score1 > score2 else route2

        st.success(f"✅ Recommended: {best['name']}")
        st.write("Route 1 Score:", score1)
        st.write("Route 2 Score:", score2)

# ==============================
# MAP
# ==============================

with col2:

    start = (28.6139, 77.2090)   # Delhi
    end   = (28.4595, 77.0266)   # Gurgaon

    route1_coords = get_route(start, end)

    waypoint = (28.5672, 77.1170)
    route2_coords = get_route(start, waypoint) + get_route(waypoint, end)

    m = folium.Map(location=start, zoom_start=11)

    folium.PolyLine(route1_coords, color="blue", weight=5).add_to(m)
    folium.PolyLine(route2_coords, color="orange", weight=5).add_to(m)

    folium.Marker(start, tooltip="Start").add_to(m)
    folium.Marker(end, tooltip="End").add_to(m)

    st_folium(m, width=700)
