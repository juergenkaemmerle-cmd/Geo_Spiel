import streamlit as st
from geopy.geocoders import Nominatim
import numpy as np
import pandas as pd
import random
import math
import pydeck as pdk
import urllib.parse

st.set_page_config(page_title="Geo-Master Quiz", page_icon="🎲", layout="centered")

# --- FRAGENKATALOG DIREKT UND FRISCH LADEN ---
def lade_fragen():
    try:
        df = pd.read_csv("fragen.csv", sep=";")
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].str.strip()
        return df
    except Exception as e:
        st.error(f"Fehler beim Laden der fragen.csv: {e}")
        return pd.DataFrame(columns=["karte", "frage", "ziel", "info"])

fragen_df = lade_fragen()

# FEIN-KALIBRIERTE GRENZEN FÜR VERTICALES A-T GITTER
KARTEN_DATEN = {
    "Deutschland 🇩🇪": {"bounds": (5.20, 47.27, 15.70, 54.91), "such_zusatz": ", Germany"}
}

GRID_SIZE = 20
x_achsen_werte = [str(i) for i in range(1, GRID_SIZE + 1)]
y_achsen_werte = [chr(i) for i in range(ord('A'), ord('A') + GRID_SIZE)]
felder_liste = [b+z for b in y_achsen_werte for z in x_achsen_werte]

def get_field_center_gps(feld, karte_name):
    minx, miny, maxx, maxy = KARTEN_DATEN[karte_name]["bounds"]
    b_char = feld[0].upper()
    z_str = feld[1:]
    y_idx = y_achsen_werte.index(b_char)  
    x_idx = x_achsen_werte.index(z_str)   
    lon_step = (maxx - minx) / GRID_SIZE
    lat_step = (maxy - miny) / GRID_SIZE
    center_lon = minx + (x_idx + 0.5) * lon_step
    center_lat = maxy - (y_idx + 0.5) * lat_step  
    return center_lon, center_lat

def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371.0
    rad_lon1, rad_lat1 = math.radians(lon1), math.radians(lat1)
    rad_lon2, rad_lat2 = math.radians(lon2), math.radians(lat2)
    dlon = rad_lon2 - rad_lon1
    dlat = rad_lat2 - rad_lat1
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def hole_spezifische_frage(frage_id):
    try:
        idx = int(frage_id)
        if 0 <= idx < len(fragen_df):
            zeile = fragen_df.iloc[idx]
            return {
                "frage": zeile["frage"],
                "ziel": zeile["ziel"],
                "info": zeile["info"]
            }
    except ValueError:
        pass
    return None

def frische_frage_ziehen(karte_name):
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
            "frage": f"Keine Fragen für '{karte_name}' in der fragen.csv gefunden!",
            "ziel": "",
            "info": "Überprüfe die Spalte 'karte' in deiner CSV."
        }

# --- APP STATE INIT ---
if "setup_erledigt" not in st.session_state:
    st.session_state.setup_erledigt = False
if "ansicht" not in st.session_state:
    st.session_state.ansicht = "spiel"
if "gewaehlte_karte" not in st.session_state:
    st.session_state.gewaehlte_karte = "Deutschland 🇩🇪"
if "spieler_namen" not in st.session_state:
    st.session_state.spieler_namen = []
if "scores" not in st.session_state:
    st.session_state.scores = {}
if "runde" not in st.session_state:
    st.session_state.runde = 0
if "aktuelle_frage" not in st.session_state:
    st.session_state.aktuelle_frage = None
if "runden_ergebnis" not in st.session_state:
    st.session_state.runden_ergebnis = None
if "naechste_frage_bereit" not in st.session_state:
    st.session_state.naechste_frage_bereit = None
if "letzte_verarbeitete_id" not in st.session_state:
    st.session_state.letzte_verarbeitete_id = None

# --- WICHTIG: LIVE EXTRACT AUS DER URL ---
query_params = st.query_params
url_frage_id = query_params.get("frage_id", None)

# Wenn eine NEUE Frage-ID über die URL reinkommt, laden wir sie sofort
if url_frage_id and url_frage_id != st.session_state.letzte_verarbeitete_id:
    spezifische = hole_spezifische_frage(url_frage_id)
    if spezifische:
        st.session_state.aktuelle_frage = spezifische
        st.session_state.letzte_verarbeitete_id = url_frage_id
        st.session_state.runden_ergebnis = None  # Altes Ergebnis löschen für die neue Runde

# --- HEADER / NAVIGATION VIA BUTTONS ---
st.title("🏆 Geo-Master Quiz-Leiter")

if st.session_state.setup_erledigt:
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("🎮 Zum Spiel", use_container_width=True, disabled=(st.session_state.ansicht == "spiel")):
            st.session_state.ansicht = "spiel"
            st.rerun()
    with c2:
        if st.button("📊 Punktestand", use_container_width=True, disabled=(st.session_state.ansicht == "score")):
            st.session_state.ansicht = "score"
            st.rerun()
    with c3:
        if st.button("⚙️ Spiel-Setup ändern", use_container_width=False):
            st.session_state.setup_erledigt = False
            st.rerun()
    st.divider()

# --- ANSICHT 0: SETUP (START) ---
if not st.session_state.setup_erledigt:
    st.subheader("🛠️ Spiel-Setup")
    karte = st.selectbox("Welche Karte liegt auf dem Tisch?", list(KARTEN_DATEN.keys()))
    anzahl_spieler = st.number_input("Wie viele Spieler?", min_value=1, max_value=6, value=2)
    
    namen = []
    cols_spieler = st.columns(min(anzahl_spieler, 3))
    for i in range(anzahl_spieler):
        with cols_spieler[i % 3]:
            default_name = f"Spieler {i+1}"
            name = st.text_input(f"Name Spieler {i+1}:", value=default_name, key=f"setup_name_{i}")
            namen.append(name)
            
    st.divider()
    st.markdown("### 📷 Manuelle ID Eingabe")
    scanned_input = st.text_input("Falls kein URL-Scan genutzt wird, ID hier eingeben:", placeholder="Z.B. 12")
    
    if st.button("Speichern & Spiel starten 🚀", type="primary"):
        st.session_state.gewaehlte_karte = karte
        st.session_state.spieler_namen = namen
        for name in namen:
            if name not in st.session_state.scores:
                st.session_state.scores[name] = 0
        
        if scanned_input:
            spezifische = hole_spezifische_frage(scanned_input)
            if spezifische:
                st.session_state.aktuelle_frage = spezifische
        
        if st.session_state.aktuelle_frage is None:
            st.session_state.aktuelle_frage = frische_frage_ziehen(karte)
            
        st.session_state.setup_erledigt = True
        st.session_state.ansicht = "spiel"
        st.rerun()

# --- ANSICHT 1: DAS SPIEL ---
elif st.session_state.ansicht == "spiel":
    if st.session_state.aktuelle_frage is None:
        st.session_state.aktuelle_frage = frische_frage_ziehen(st.session_state.gewaehlte_karte)

    ist_aufgeloest = st.session_state.runden_ergebnis is not None

    st.info(f"❓ **DIE QUIZ-FRAGE (Runde {st.session_state.runde + 1}):**\n\n### {st.session_state.aktuelle_frage['frage']}")
    st.divider()

    st.write("Wählt euer Rasterfeld auf dem gedruckten Brett:")
    tipps = {}
    cols_tipps = st.columns(min(len(st.session_state.spieler_namen), 3))
    for i, name in enumerate(st.session_state.spieler_namen):
        with cols_tipps[i % 3]:
            tipp_key = f"tipp_{st.session_state.runde}_{i}"
            tipps[name] = st.selectbox(f"{name}:", felder_liste, key=tipp_key, disabled=ist_aufgeloest)

    if not ist_aufgeloest:
        if st.button("Runde auflösen! 🎲", type="primary", use_container_width=True):
            with st.spinner("Orakel ermittelt Koordinaten..."):
                geolocator = Nominatim(user_agent="geo_master_quiz_v2026")
                ziel_ort = st.session_state.aktuelle_frage["ziel"]
                
                if "such_zusatz" in KARTEN_DATEN[st.session_state.gewaehlte_karte]:
                    such_string = ziel_ort + KARTEN_DATEN[st.session_state.gewaehlte_karte]["such_zusatz"]
                else:
                    such_string = ziel_ort + ", Germany"
                    
                location = geolocator.geocode(such_string)
            
            if not location:
                st.error(f"Fehler bei der Ortung für '{ziel_ort}'.")
            else:
                ziel_lon, ziel_lat = location.longitude, location.latitude
                minx, miny, maxx, maxy = KARTEN_DATEN[st.session_state.gewaehlte_karte]["bounds"]
                
                pct_x = (ziel_lon - minx) / (maxx - minx)
                corr_x_idx = max(0, min(GRID_SIZE - 1, int(math.floor(pct_x * GRID_SIZE))))
                korrekte_zahl = x_achsen_werte[corr_x_idx]
                
                pct_y = 1.0 - ((ziel_lat - miny) / (maxy - miny))
                corr_y_idx = max(0, min(GRID_SIZE - 1, int(math.floor(pct_y * GRID_SIZE))))
                korrekter_buchstabe = y_achsen_werte[corr_y_idx]
                
                korrektes_feld = f"{korrekter_buchstabe}{korrekte_zahl}"
                
                ergebnisse = []
                abstaende_km = {}
                
                for name, tipp in tipps.items():
                    tx, ty = get_field_center_gps(tipp, st.session_state.gewaehlte_karte)
                    distanz = haversine_distance(tx, ty, ziel_lon, ziel_lat)
                    
                    punkte_dieser_runde = 0
                    if tipp == korrektes_feld:
                        st.session_state.scores[name] += 3
                        punkte_dieser_runde += 3
                        
                    abstaende_km[name] = distanz
                    ergebnisse.append({
                        "Spieler": name, 
                        "Tipp": tipp,
                        "Tipp_Lon": tx,
                        "Tipp_Lat": ty,
                        "Abstand (km)": round(distanz, 1), 
                        "Volltreffer": "🎉 Ja (+3 Pkt)" if tipp == korrektes_feld else "Nein",
                        "Punkte": punkte_dieser_runde
                    })
                
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
                    "ziel_lon": ziel_lon,
                    "ziel_lat": ziel_lat,
                    "info": st.session_state.aktuelle_frage['info'],
                    "feld": korrektes_feld,
                    "tabelle": pd.DataFrame(ergebnisse)
                }
                st.session_state.naechste_frage_bereit = frische_frage_ziehen(st.session_state.gewaehlte_karte)
                st.rerun()
    else:
        res = st.session_state.runden_ergebnis
        st.success(f"🏁 **Auflösung: {res['ziel']}** (Liegt im Feld **{res['feld']}**)")
        st.markdown(f"💡 *Hintergrund-Info: {res['info']}*")
        
        st.subheader("📈 Runden-Details & Punkteverteilung:")
        st.table(res["tabelle"].set_index("Spieler").drop(columns=["Punkte", "Tipp_Lon", "Tipp_Lat"]))
        
        st.divider()
        
        st.subheader("🗺️ Visueller Abgleich auf der Deutschlandkarte:")
        
        df_tipps = res["tabelle"].copy()
        df_tipps["Ziel_Lon"] = res["ziel_lon"]
        df_tipps["Ziel_Lat"] = res["ziel_lat"]
        
        df_ziel = pd.DataFrame([{
            "lon": res["ziel_lon"],
            "lat": res["ziel_lat"],
            "name": res["ziel"]
        }])
        
        line_layer = pdk.Layer(
            "ArcLayer",
            data=df_tipps,
            get_source_position="[Tipp_Lon, Tipp_Lat]",
            get_target_position="[Ziel_Lon, Ziel_Lat]",
            get_source_color="[255, 75, 75, 160]",
            get_target_color="[46, 196, 182, 255]",
            get_width=5,
            pickable=True
        )
        
        tipp_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_tipps,
            get_position="[Tipp_Lon, Tipp_Lat]",
            get_color="[255, 75, 75]",
            get_radius=12000,
            pickable=True,
            auto_highlight=True
        )
        
        ziel_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_ziel,
            get_position="[lon, lat]",
            get_color="[46, 196, 182]",
            get_radius=18000,
            pickable=True
        )

        label_layer = pdk.Layer(
            "TextLayer",
            data=df_tipps,
            get_position="[Tipp_Lon, Tipp_Lat]",
            get_text="Spieler",
            get_size=15,
            get_color="[255, 255, 255]",
            get_alignment_baseline="'bottom'",
            background_color="[0, 0, 0, 180]"
        )
        
        view_state = pdk.ViewState(
            longitude=10.45,
            latitude=51.16,
            zoom=5.0,
            pitch=35,
            bearing=0,
            controller=True
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[line_layer, tipp_layer, ziel_layer, label_layer],
            initial_view_state=view_state,
            map_style=None, 
            tooltip={"text": "{Spieler}: {Tipp}\nAbstand: {Abstand (km)} km"}
        ))
        
        st.divider()
        
        if st.button("Nächste Runde starten ➡️", type="primary", use_container_width=True):
            st.session_state.aktuelle_frage = st.session_state.naechste_frage_bereit
            st.session_state.runden_ergebnis = None
            st.session_state.naechste_frage_bereit = None
            st.rerun()

# --- ANSICHT 2: GLOBALER PUNKTESTAND ---
elif st.session_state.ansicht == "score":
    st.subheader("📊 Globaler Punktestand (Aktuelles Spiel)")
    score_data = [{"Spieler": k, "Gesamtpunkte": v} for k, v in st.session_state.scores.items() if k in st.session_state.spieler_namen]
    df_score = pd.DataFrame(score_data)
    
    if not df_score.empty:
        df_score = df_score.sort_values(by="Gesamtpunkte", ascending=False).reset_index(drop=True)
        st.dataframe(df_score.set_index("Spieler"), use_container_width=True)
        st.bar_chart(df_score.set_index("Spieler"), y="Gesamtpunkte", color="#4bd6ff")
    else:
        st.info("Noch keine Punkte vergeben.")
        
    if st.button("Scoreboard & Runden komplett zurücksetzen 🔄", type="secondary"):
        st.session_state.scores = {name: 0 for name in st.session_state.spieler_namen}
        st.session_state.runde = 0
        st.session_state.runden_ergebnis = None
        st.session_state.aktuelle_frage = frische_frage_ziehen(st.session_state.gewaehlte_karte)
        st.session_state.ansicht = "spiel"
        st.rerun()
