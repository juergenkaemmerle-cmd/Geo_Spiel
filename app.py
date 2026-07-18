import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
from geopy.geocoders import Nominatim
import numpy as np
import pandas as pd
import random

st.set_page_config(page_title="Geo-Master Quiz", page_icon="🎲", layout="centered")

# --- EXTERNEN FRAGENKATALOG AUS CSV LADEN ---
@st.cache_data
def lade_fragen():
    try:
        # Lädt die CSV-Datei, die im selben Ordner liegt
        df = pd.read_csv("fragen.csv", sep=";")
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der fragen.csv: {e}")
        return pd.DataFrame(columns=["karte", "frage", "ziel", "info"])

fragen_df = lade_fragen()

KARTEN_DATEN = {
    "Deutschland 🇩🇪": {"bounds": (5.86, 47.27, 15.04, 54.91), "such_zusatz": ", Germany"},
    "Baden-Württemberg 🥨": {"bounds": (7.51, 47.53, 10.50, 49.79), "such_zusatz": ", Baden-Wuerttemberg, Germany"},
    "Weltkarte 🗺️": {"bounds": (-180.0, -60.0, 180.0, 85.0), "such_zusatz": ""}
}

spalten = ['A', 'B', 'C', 'D', 'E']
zeilen = ['1', '2', '3', '4', '5', '6', '7']
felder_liste = [s+z for s in spalten for z in zeilen]

def get_raster_coords(feld, karte_name):
    minx, miny, maxx, maxy = KARTEN_DATEN[karte_name]["bounds"]
    s_idx = spalten.index(feld[0])
    z_idx = zeilen.index(feld[1])
    x_edges = np.linspace(minx, maxx, len(spalten) + 1)
    y_edges = np.linspace(miny, maxy, len(zeilen) + 1)
    return (x_edges[s_idx] + x_edges[s_idx + 1]) / 2, (y_edges[z_idx] + y_edges[z_idx + 1]) / 2

# --- APP STATE ---
if "aktuelle_frage" not in st.session_state:
    st.session_state.aktuelle_frage = None
if "vorherige_karte" not in st.session_state:
    st.session_state.vorherige_karte = ""

# --- INTERFACE ---
st.title("🏆 Geo-Master Quiz-Leiter")

# 1. Kartenauswahl
gewaehlte_karte = st.selectbox("Welche Karte liegt auf dem Tisch?", list(KARTEN_DATEN.keys()))

if gewaehlte_karte != st.session_state.vorherige_karte:
    st.session_state.aktuelle_frage = None
    st.session_state.vorherige_karte = gewaehlte_karte

st.divider()

# 2. Spieler-Setup
anzahl_spieler = st.number_input("Wie viele Spieler?", min_value=1, max_value=6, value=2)
spieler_namen = []
cols_spieler = st.columns(min(anzahl_spieler, 3))
for i in range(anzahl_spieler):
    with cols_spieler[i % 3]:
        name = st.text_input(f"Name Spieler {i+1}:", value=f"Spieler {i+1}", key=f"name_{i}")
        spieler_namen.append(name)

st.divider()

# 3. Fragen-Steuerung aus der Tabelle
# Filtere alle Fragen, die zur gewählten Karte gehören
verfuegbare_fragen = fragen_df[fragen_df["karte"] == gewaehlte_karte]

if st.button("🔄 Neue Frage ziehen", type="secondary") or st.session_state.aktuelle_frage is None:
    if not verfuegbare_fragen.empty:
        # Wähle eine zufällige Zeile aus den gefilterten Fragen
        zufaellige_zeile = verfuegbare_fragen.sample(n=1).iloc[0]
        st.session_state.aktuelle_frage = {
            "frage": zufaellige_zeile["frage"],
            "ziel": zufaellige_zeile["ziel"],
            "info": zufaellige_zeile["info"]
        }
    else:
        st.session_state.aktuelle_frage = {
            "frage": "Keine Fragen für diese Karte in der CSV gefunden!",
            "ziel": "",
            "info": ""
        }

# Frage anzeigen
st.info(f"❓ **DIE QUIZ-FRAGE:**\n\n### {st.session_state.aktuelle_frage['frage']}")

st.divider()

# 4. Tipps abfragen
st.write("Layoutet eure Steine auf dem Brett und wählt euer Rasterfeld:")
tipps = {}
cols_tipps = st.columns(min(anzahl_spieler, 3))
for i, name in enumerate(spieler_namen):
    with cols_tipps[i % 3]:
        tipp = st.selectbox(f"{name}:", felder_liste, key=f"tipp_{i}", index=10)
        tipps[name] = tipp

# 5. Auswertung
if st.button("Runde auflösen! 🎲", type="primary"):
    if st.session_state.aktuelle_frage["ziel"] == "":
        st.error("Kein gültiges Ziel vorhanden.")
    else:
        geolocator = Nominatim(user_agent="geo_master_quiz_csv")
        ziel_ort = st.session_state.aktuelle_frage["ziel"]
        such_string = ziel_ort + KARTEN_DATEN[gewaehlte_karte]["such_zusatz"]
        location = geolocator.geocode(such_string)
        
        if not location:
            st.error("Fehler bei der Ortung des Ziels. Bitte noch einmal versuchen.")
        else:
            st.success(f"🏁 **Lösung: {ziel_ort.upper()}**")
            st.write(f"*💡 Hintergrund-Info: {st.session_state.aktuelle_frage['info']}*")
            
            ziel_lon, ziel_lat = location.longitude, location.latitude
            ergebnisse = []
            
            for name, tipp in tipps.items():
                tx, ty = get_raster_coords(tipp, gewaehlte_karte)
                pro_grad_km = 111.0 
                if gewaehlte_karte != "Weltkarte":
                    distanz = np.sqrt((ziel_lon - tx)**2 + (ziel_lat - ty)**2) * pro_grad_km
                else:
                    distanz = np.sqrt((ziel_lon - tx)**2 + (ziel_lat - ty)**2) * 80.0
                    
                ergebnisse.append((name, tipp, distanz))
            
            ergebnisse.sort(key=lambda x: x[2])
            
            st.subheader("📊 Das Ergebnis dieser Runde:")
            for rang, (name, tipp, dist) in enumerate(ergebnisse, 1):
                medaille = "🥇" if rang == 1 else "🥈" if rang == 2 else "🥉" if rang == 3 else "⚫"
                st.warning(f"{medaille} **Platz {rang}: {name}** (Feld {tipp}) — ca. **{dist:.1f} km** vom Ziel entfernt")
