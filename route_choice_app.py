import streamlit as st
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(layout="wide")

# ==============================
# ROUTE FETCH (OSRM)
# ==============================

def get_route(points):
    coords = ";".join([f"{lon},{lat}" for lat, lon in points])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords}?overview=full&geometries=geojson"
    r = requests.get(url).json()
    route = r['routes'][0]['geometry']['coordinates']
    return [(lat, lon) for lon, lat in route]

# ==============================
# ROUTE DEFINITIONS
# ==============================

start = (28.6139, 77.2090)   # Delhi
end   = (28.4595, 77.0266)   # Gurgaon

# Route 1 — SPM (more direct)
route1_points = [
    start,
    (28.6000, 77.1800),
    (28.5700, 77.1400),
    (28.5200, 77.1000),
    end
]

# Route 2 — RTR (more reliable)
route2_points = [
    start,
    (28.6200, 77.2500),
    (28.5800, 77.2000),
    (28.5500, 77.1500),
    (28.5000, 77.1200),
    end
]

route1_coords = get_route(route1_points)
route2_coords = get_route(route2_points)

# ==============================
# ROUTE DATA
# ==============================

route1 = {"tt": 49, "bti": 0.70, "signals": 0.60, "circularity": 1.10}
route2 = {"tt": 52, "bti": 0.45, "signals": 0.40, "circularity": 1.40}

# ==============================
# WEIGHTS
# ==============================

def get_weights(user):

    w = {"TT":0.30, "BTI":0.40, "Signals":0.15, "Geometry":0.15}

    if user['threshold']=="1–2 min":
        w["BTI"]+=0.25; w["TT"]-=0.10
    elif user['threshold']=="5–10 min":
        w["BTI"]+=0.10
    elif user['threshold']==">10 min":
        w["TT"]+=0.20; w["BTI"]-=0.10

    if user['buffer']>=20:
        w["BTI"]+=0.20
    else:
        w["TT"]+=0.10

    if user['time'] in ["Morning peak (6–9 AM)", "Evening peak (4–8 PM)"]:
        w["BTI"]+=0.15; w["Signals"]+=0.10

    if user['signals']=="Avoid signals":
        w["Signals"]+=0.20

    if user['geometry']=="Prefer straight route":
        w["Geometry"]+=0.15

    total=sum(w.values())
    for k in w: w[k]/=total

    return w

# ==============================
# SCORING
# ==============================

def score(route, w):

    s_tt = (1/route["tt"])*100
    s_bti = (1/route["bti"])*100
    s_sig = (1-route["signals"])*100
    s_geo = (1/route["circularity"])*100

    return round(
        w["TT"]*s_tt +
        w["BTI"]*s_bti +
        w["Signals"]*s_sig +
        w["Geometry"]*s_geo, 2
    )

# ==============================
# WHY EXPLANATION
# ==============================

def explain(best, w):

    reasons = []

    if w["BTI"] > w["TT"]:
        reasons.append("You prefer reliable routes (low delay risk)")

    if w["TT"] > w["BTI"]:
        reasons.append("You prefer faster routes")

    if w["Signals"] > 0.2:
        reasons.append("You prefer routes with fewer signals")

    if w["Geometry"] > 0.2:
        reasons.append("You prefer straighter routes")

    return reasons

# ==============================
# UI
# ==============================

st.title("🚗 Smart Route Recommendation System")

col1, col2 = st.columns([1,2])

with col1:

    timeband = st.selectbox("Time of travel",
        ["Morning peak (6–9 AM)",
         "Inter-peak (9 AM–4 PM)",
         "Evening peak (4–8 PM)",
         "Off-peak / night"]
    )

    threshold = st.selectbox("Delay tolerance",
        ["1–2 min", "5–10 min", ">10 min"]
    )

    buffer = st.slider("Buffer time (min)", 0, 30, 10)

    signals = st.selectbox("Signals preference",
        ["Okay with signals", "Avoid signals"]
    )

    geometry = st.selectbox("Route preference",
        ["Doesn’t matter", "Prefer straight route"]
    )

    if st.button("Find best route"):

        user = {
            "time": timeband,
            "threshold": threshold,
            "buffer": buffer,
            "signals": signals,
            "geometry": geometry
        }

        w = get_weights(user)

        s1 = score(route1, w)
        s2 = score(route2, w)

        best = "R1" if s1 > s2 else "R2"

        st.success(f"Recommended: {'Route 1 (SPM)' if best=='R1' else 'Route 2 (RTR)'}")

        st.write("Route 1 Score:", s1)
        st.write("Route 2 Score:", s2)

        # WHY explanation
        st.subheader("Why this route?")
        for r in explain(best, w):
            st.write("•", r)

with col2:

    m = folium.Map(location=start, zoom_start=11)

    if 'best' in locals():

        if best=="R1":

            folium.PolyLine(route1_coords, color="blue", weight=7).add_to(m)
            folium.PolyLine(route2_coords, color="orange", weight=3, opacity=0.4).add_to(m)

        else:

            folium.PolyLine(route2_coords, color="orange", weight=7).add_to(m)
            folium.PolyLine(route1_coords, color="blue", weight=3, opacity=0.4).add_to(m)

    else:

        folium.PolyLine(route1_coords, color="blue").add_to(m)
        folium.PolyLine(route2_coords, color="orange").add_to(m)

    folium.Marker(start, tooltip="Start").add_to(m)
    folium.Marker(end, tooltip="End").add_to(m)

    st_folium(m, width=900)
