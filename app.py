import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
import numpy as np

# Seiten-Setup für Smartphones (Mobile First)
st.set_page_config(page_title="Geo-Brettspiel", page_icon="🎲", layout="centered")

# CSS für schöne, große Buttons auf dem Handy
st.markdown("""
    <style>
    div.stButton > button:first-child {
        width: 100%;
        height: 60px;
        font-size: 20px;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    world = gpd.read_file(url)
    germany = world[world.ISO_A3 == "DEU"].to_crs(epsg=25832)
    return germany

# Daten laden
germany = load_data()
minx, miny, maxx, maxy = germany.total_bounds

spalten = ['A', 'B', 'C', 'D', 'E']
zeilen = ['1', '2', '3', '4', '5', '6', '7']
x_edges = np.linspace(minx, maxx, len(spalten) + 1)
y_edges = np.linspace(miny, maxy, len(zeilen) + 1)

def raster_zu_koordinate(feld):
    s_idx = spalten.index(feld[0])
    z_idx = zeilen.index(feld[1])
    return Point((x_edges[s_idx] + x_edges[s_idx + 1]) / 2, (y_edges[z_idx] + y_edges[z_idx + 1]) / 2)

# --- OBERFLÄCHE ---
st.title("🗺️ Erdkunde Brettspiel")
st.write("Nutzt euer ausgedrucktes A3-Raster auf dem Tisch!")

# Eingabe der Stadt
stadt = st.text_input("Welche Stadt wird gesucht?", value="München")

# Touch-freundliche Dropdowns für die Spieler
felder_liste = [s+z for s in spalten for z in zeilen]
col1, col2 = st.columns(2)

with col1:
    p1 = st.selectbox("Tipp Spieler 1 (Blau):", felder_liste, index=10)
with col2:
    p2 = st.selectbox("Tipp Spieler 2 (Rot):", felder_liste, index=15)

# Großer Auswertungs-Button
if st.button("Runde auswerten! 🎲"):
    geolocator = Nominatim(user_agent="handy_brettspiel")
    location = geolocator.geocode(f"{stadt}, Germany")
    
    if not location:
        st.error("❌ Stadt nicht gefunden! Bitte Schreibweise prüfen.")
    else:
        stadt_utm = gpd.GeoDataFrame(geometry=[Point(location.longitude, location.latitude)], crs="EPSG:4326").to_crs(epsg=25832)
        echter_punkt = stadt_utm.geometry.iloc[0]
        
        d1 = echter_punkt.distance(raster_zu_koordinate(p1)) / 1000
        d2 = echter_punkt.distance(raster_zu_koordinate(p2)) / 1000
        
        st.subheader(f"📍 Ziel: {stadt.upper()}")
        
        # Schicke Info-Boxen für die Ergebnisse
        st.info(f"🔵 Spieler 1 ({p1}): **{d1:.1f} km** entfernt")
        st.warning(f"🔴 Spieler 2 ({p2}): **{d2:.1f} km** entfernt")
        
        # Sieger-Verkündung
        if d1 < d2:
            st.success(f"🏆 **SPIELER 1 GEWINNT DIE RUNDE!**")
        elif d2 < d1:
            st.success(f"🏆 **SPIELER 2 GEWINNT DIE RUNDE!**")
        else:
            st.success("🤝 **Unentschieden!** Beide liegen gleich nah dran.")
