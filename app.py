import streamlit as st
from geopy.geocoders import Nominatim
import numpy as np
import pandas as pd
import random
import math

st.set_page_config(page_title="Geo-Master Quiz", page_icon="🎲", layout="centered")

# --- EXTERNEN FRAGENKATALOG AUS CSV LADEN ---
@st.cache_data
def lade_fragen():
    try:
        df = pd.read_csv("fragen.csv", sep=";")
        # Wichtig: Entfernt unsichtbare Leerzeichen aus den Spaltennamen
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der fragen.csv: {e}")
        return pd.DataFrame(columns=["karte", "frage", "ziel", "info"])

fragen_df = lade_fragen()

# GPS-Grenzen exakt angepasst an deine Festland-Deutschlandkarte
KARTEN_DATEN = {
    "Deutschland 🇩🇪": {"bounds": (5.86, 47.27, 15.04, 54.91), "such_zusatz": ", Germany"}
}

# Das volle 20x20 Spielfeld passend zu deinem 2200px Ausdruck
GRID_SIZE = 20
spalten = [chr(i) for i in range(ord('A'), ord('A') + GRID_SIZE)]  # A bis T
zeilen = [str(i) for i in range(1, GRID_SIZE + 1)]               # 1 bis 20
felder_liste = [s+z for s in spalten for z in zeilen]

def get_field_center_gps(feld, karte_name):
    minx, miny, maxx, maxy = KARTEN_DATEN[karte_name]["bounds"]
    s_idx = spalten.index(feld[0])
    z_idx = int(feld[1:]) - 1
    
    lon_step = (maxx - minx) / GRID_SIZE
    lat_step = (maxy - miny) / GRID_SIZE
    
    center_lon = minx + (s_idx + 0.5) * lon_step
    center_lat = maxy - (z_idx + 0.5) * lat_step  
    return center_lon, center_lat

def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371.0  # Erdradius in km
    rad_lon1, rad_lat1 = math.radians(lon1), math.radians(lat1)
    rad_lon2, rad_lat2 = math.radians(lon2), math.radians(lat2)
    dlon = rad_lon2 - rad_lon1
    dlat = rad_lat2 - rad_lat1
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Hilfsfunktion: Zieht eine frische Frage aus der CSV
def frische_frage_ziehen(karte_name):
    # Fix: Wir filtern sowohl nach dem Namen MIT als auch OHNE Emoji, falls deine CSV keine Emojis hat!
    reiner_name = karte_name.split(" ")[0].strip()
    verfuegbare = fragen_df[(fragen_df["karte"] == karte_name) | (fragen_df["karte"] == reiner_name)]
    
    if not verfuegbare.empty:
        zufaellige_zeile = verfuegbare.sample(n=1).iloc[0]
        return {
            "frage": zufaellige_zeile["frage"],
            "ziel": zufaellige_zeile["ziel"],
            "info": zufaellige_zeile["info"]
        }
    else:
        return {
            "frage": f"Keine Fragen für '{karte_name}' oder '{reiner_name}' in der fragen.csv gefunden!",
            "ziel": "",
            "info": "Bitte überprüfe die Spalte 'karte' in deiner CSV-Datei."
        }

# --- APP STATE INIT ---
if "scores" not in st.session_state:
    st.session_state.scores = {}
if "runde" not in st.session_state:
    st.session_state.runde = 0
if "aktuelle_frage" not in st.session_state:
    st.session_state.aktuelle_frage = None
if "vorherige_karte" not in st.session_state:
    st.session_state.vorherige_karte = ""
if "runden_ergebnis" not in st.session_state:
    st.session_state.runden_ergebnis = None

# --- INTERFACE ---
st.title("🏆 Geo-Master Quiz-Leiter")

# 1. Kartenauswahl
gewaehlte_karte = st.selectbox("Welche Karte liegt auf dem Tisch?", list(KARTEN_DATEN.keys()))

if gewaehlte_karte != st.session_state.vorherige_karte:
    st.session_state.aktuelle_frage = frische_frage_ziehen(gewaehlte_karte)
    st.session_state.vorherige_karte = gewaehlte_karte
    st.session_state.runden_ergebnis = None

st.divider()

# 2. Spieler-Setup
anzahl_spieler = st.number_input("Wie viele Spieler?", min_value=1, max_value=6, value=2)
spieler_namen = []
cols_spieler = st.columns(min(anzahl_spieler, 3))
for i in range(anzahl_spieler):
    with cols_spieler[i % 3]:
        default_name = f"Spieler {i+1}"
        name = st.text_input(f"Name Spieler {i+1}:", value=default_name, key=f"name_{i}")
        spieler_namen.append(name)
        if name not in st.session_state.scores:
            st.session_state.scores[name] = 0

# Punktestand anzeigen
st.subheader("📊 Globaler Punktestand:")
score_df = pd.DataFrame([{"Spieler": k, "Punkte": v} for k, v in st.session_state.scores.items() if k in spieler_namen])
if not score_df.empty:
    st.dataframe(score_df.set_index("Spieler"), use_container_width=True)

if st.button("Scoreboard zurücksetzen 🔄"):
    st.session_state.scores = {name: 0 for name in spieler_namen}
    st.session_state.runde = 0
    st.session_state.runden_ergebnis = None
    st.session_state.aktuelle_frage = frische_frage_ziehen(gewaehlte_karte)
    st.rerun()

st.divider()

# Erste Frage laden, falls der State leer ist
if st.session_state.aktuelle_frage is None:
    st.session_state.aktuelle_frage = frische_frage_ziehen(gewaehlte_karte)

# 3. Fragen-Steuerung
if st.button("🔄 Nächste Frage ziehen", type="secondary"):
    st.session_state.aktuelle_frage = frische_frage_ziehen(gewaehlte_karte)
    st.session_state.runden_ergebnis = None
    st.rerun()

st.info(f"❓ **DIE QUIZ-FRAGE (Runde {st.session_state.runde + 1}):**\n\n### {st.session_state.aktuelle_frage['frage']}")

st.divider()

# 4. Tipps abfragen
st.write("Wählt euer Rasterfeld auf dem gedruckten Brett:")
tipps = {}
cols_tipps = st.columns(min(anzahl_spieler, 3))
for i, name in enumerate(spieler_namen):
    with cols_tipps[i % 3]:
        tipp = st.selectbox(f"{name}:", felder_liste, key=f"tipp_{i}", index=0)
        tipps[name] = tipp

# 5. Auswertung
if st.button("Runde auflösen! 🎲", type="primary"):
    if not st.session_state.aktuelle_frage["ziel"]:
        st.error("Kein gültiges Ziel in dieser Frage vorhanden.")
    else:
        with st.spinner("Orakel wird befragt (Geolokalisierung)..."):
            geolocator = Nominatim(user_agent="geo_master_quiz_precise_v2")
            ziel_ort = st.session_state.aktuelle_frage["ziel"]
            such_string = ziel_ort + KARTEN_DATEN[gewaehlte_karte]["such_zusatz"]
            location = geolocator.geocode(such_string)
        
        if not location:
            st.error(f"Fehler bei der Ortung. '{ziel_ort}' wurde weltweit nicht gefunden. Evtl. Tippfehler in der CSV?")
        else:
            ziel_lon, ziel_lat = location.longitude, location.latitude
            
            # Berechne das exakt korrekte Feld
            minx, miny, maxx, maxy = KARTEN_DATEN[gewaehlte_karte]["bounds"]
            pct_x = (ziel_lon - minx) / (maxx - minx)
            pct_y = 1.0 - ((ziel_lat - miny) / (maxy - miny))
            corr_col = spalten[max(0, min(GRID_SIZE - 1, int(math.floor(pct_x * GRID_SIZE))))]
            corr_row = zeilen[max(0, min(GRID_SIZE - 1, int(math.floor(pct_y * GRID_SIZE))))]
            korrektes_feld = f"{corr_col}{corr_row}"
            
            ergebnisse = []
            abstaende_km = {}
            
            for name, tipp in tipps.items():
                tx, ty = get_field_center_gps(tipp, gewaehlte_karte)
                distanz = haversine_distance(tx, ty, ziel_lon, ziel_lat)
                
                punkte_dieser_runde = 0
                if tipp == korrektes_feld:
                    st.session_state.scores[name] += 3
                    punkte_dieser_runde += 3
                    
                abstaende_km[name] = distanz
                ergebnisse.append({
                    "Spieler": name, 
                    "Tipp": tipp, 
                    "Abstand (km)": round(distanz, 1), 
                    "Volltreffer": "🎉 Ja (+3 Pkt)" if tipp == korrektes_feld else "Nein",
                    "punkte_basis": punkte_dieser_runde
                })
            
            # Trostpunkt ermitteln
            if abstaende_km:
                min_distanz = min(abstaende_km.values())
                for idx, erg in enumerate(ergebnisse):
                    sp_name = erg["Spieler"]
                    if abstaende_km[sp_name] == min_distanz:
                        st.session_state.scores[sp_name] += 1
                        ergebnisse[idx]["Trostpunkt"] = "🎯 Ja (+1 Pkt)"
                    else:
                        ergebnisse[idx]["Trostpunkt"] = "Nein"
            
            st.session_state.runde += 1
            st.session_state.runden_ergebnis = {
                "ziel": ziel_ort.upper(),
                "info": st.session_state.aktuelle_frage['info'],
                "feld": korrektes_feld,
                "tabelle": pd.DataFrame(ergebnisse).drop(columns=["punkte_basis"])
            }
            
            # WICHTIG: Bereite direkt die nächste Frage im Hintergrund vor, 
            # damit beim nächsten Rendern eine neue Frage bereitsteht!
            st.session_state.aktuelle_frage = frische_frage_ziehen(gewaehlte_karte)
            st.rerun()

# Ergebnis anzeigen
if st.session_state.runden_ergebnis:
    res = st.session_state.runden_ergebnis
    st.success(f"🏁 **Letzte Auflösung: {res['ziel']}** (Liegt im Feld **{res['feld']}**)")
    st.write(f"*💡 Hintergrund-Info: {res['info']}*")
    st.subheader("📈 Runden-Auswertung:")
    st.table(res["tabelle"].set_index("Spieler"))
