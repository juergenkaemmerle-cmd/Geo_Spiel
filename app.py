import streamlit as st
import streamlit.components.v1 as components
from geopy.geocoders import Nominatim
import numpy as np
import pandas as pd
import random
import math
import pydeck as pdk

st.set_page_config(page_title="Geo-Master Quiz", page_icon="🎲", layout="centered")

# --- FRAGENKATALOG LADE-FUNKTION ---
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
        idx = int(str(frage_id).strip())
        if 0 <= idx < len(fragen_df):
            return fragen_df.iloc[idx]
    except Exception:
        pass
    return None

def frische_frage_ziehen(karte_name):
    reiner_name = karte_name.split(" ")[0].strip()
    verfuegbare = fragen_df[(fragen_df["karte"] == karte_name) | (fragen_df["karte"] == reiner_name)]
    if not verfuegbare.empty:
        return verfuegbare.sample(n=1).iloc[0]
    else:
        return pd.Series({
            "frage": f"Keine Fragen für '{karte_name}' in der fragen.csv gefunden!",
            "ziel": "",
            "info": "Überprüfe die Spalte 'karte' in deiner CSV."
        })

# --- DAS ECHTE HTML-FORMULAR MIT INTEGRIERTEM QR-SCANNER ---
def st_qr_scanner(key):
    """
    Rendert ein eigenständiges HTML-Formular. Der Scanner füllt das Feld aus
    und schickt das Formular ab. Das lädt die Seite neu und übergibt die ID 
    zuverlässig per Standard-GET-Request an das Hauptfenster.
    """
    html_code = f"""
    <form action="" method="get" target="_parent" id="qr_form_{key}">
        <div id="reader_{key}" style="width: 100%; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px;"></div>
        <input type="hidden" name="scanned_id" id="scanned_id_{key}" value="">
    </form>
    
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(decodedText, decodedResult) {{
            let frageId = decodedText;
            if (decodedText.includes("frage_id=")) {{
                const urlParts = decodedText.split("frage_id=");
                if(urlParts.length > 1) {{
                    frageId = urlParts[1].split("&")[0];
                }}
            }}
            
            // Wert in das versteckte Formularfeld eintragen
            document.getElementById('scanned_id_{key}').value = frageId;
            // Das Formular sauber abschicken (schließt die Kamera und meldet an Eltern-Fenster)
            document.getElementById('qr_form_{key}').submit();
            
            html5QrcodeScanner.clear();
        }}

        const html5QrcodeScanner = new Html5QrcodeScanner(
            "reader_{key}", {{ fps: 15, qrbox: 250 }}, false
        );
        html5QrcodeScanner.render(onScanSuccess);
    </script>
    """
    components.html(html_code, height=380)

# --- APP STATE DEFAULT INIT ---
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
if "scan_modus_aktiv" not in st.session_state:
    st.session_state.scan_modus_aktiv = False

# --- EINGEHENDE FORMULAR-DATA HIER ABFANGEN ---
if "scanned_id" in st.query_params:
    scan_val = st.query_params["scanned_id"]
    # Direkt löschen, um Endlosschleifen beim manuellen Neuladen zu verhindern
    del st.query_params["scanned_id"]
    
    zeile = hole_spezifische_frage(scan_val)
    if zeile is not None:
        st.session_state.aktuelle_frage = zeile
        st.session_state.runden_ergebnis = None
        st.session_state.naechste_frage_bereit = None
        st.session_state.scan_modus_aktiv = False
        st.toast(f"🎯 Frage {scan_val} geladen!", icon="✅")

# --- HEADER / NAVIGATION ---
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
    st.markdown("### 📷 Vor dem Start: Optional ersten QR-Code scannen")
    
    st_qr_scanner("setup_scanner")
    
    if st.session_state.aktuelle_frage is not None:
        st.success(f"Aktuell geladene Frage: {st.session_state.aktuelle_frage['frage']}")
    
    if st.button("Spiel starten 🚀", type="primary", use_container_width=True):
        st.session_state.gewaehlte_karte = karte
        st.session_state.spieler_namen = namen
        for name in namen:
            if name not in st.session_state.scores:
                st.session_state.scores[name] = 0
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
                such_string = ziel_ort + KARTEN_DATEN[st.session_state.gewaehlte_karte].get("such_zusatz", ", Germany")
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
                        "Spieler": name, "Tipp": tipp, "Tipp_Lon": tx, "Tipp_Lat": ty,
                        "Abstand (km)": round(distanz, 1), "Volltreffer": "🎉 Ja (+3 Pkt)" if tipp == korrektes_feld else "Nein"
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
                    "ziel": ziel_ort.upper(), "ziel_lon": ziel_lon, "ziel_lat": ziel_lat,
                    "info": st.session_state.aktuelle_frage['info'], "feld": korrektes_feld,
                    "tabelle": pd.DataFrame(ergebnisse)
                }
                st.session_state.naechste_frage_bereit = frische_frage_ziehen(st.session_state.gewaehlte_karte)
                st.session_state.scan_modus_aktiv = False
                st.rerun()
    else:
        res = st.session_state.runden_ergebnis
        st.success(f"🏁 **Auflösung: {res['ziel']}** (Liegt im Feld **{res['feld']}**)")
        st.markdown(f"💡 *Hintergrund-Info: {res['info']}*")
        
        st.subheader("📈 Runden-Details & Punkteverteilung:")
        st.table(res["tabelle"].set_index("Spieler").drop(columns=["Tipp_Lon", "Tipp_Lat"]))
        
        st.divider()
        
        # --- KLAR GESTEUERTER SCAN-ABLAUF ---
        if not st.session_state.scan_modus_aktiv:
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("Kamera für nächste Runde öffnen 📷", type="primary", use_container_width=True):
                    st.session_state.scan_modus_aktiv = True
                    st.rerun()
            with c_btn2:
                if st.button("Zufällige nächste Frage ➡️", type="secondary", use_container_width=True):
                    st.session_state.aktuelle_frage = st.session_state.naechste_frage_bereit
                    st.session_state.runden_ergebnis = None
                    st.session_state.naechste_frage_bereit = None
                    st.session_state.scan_modus_aktiv = False
                    st.rerun()
        else:
            st.subheader("📷 Nächsten QR-Code live einscannen")
            if st.button("❌ Abbrechen / Zurück", type="secondary"):
                st.session_state.scan_modus_aktiv = False
                st.rerun()
                
            st_qr_scanner(f"runde_{st.session_state.runde}")
        
        st.divider()
        
        # --- MAP LAYER ---
        st.subheader("🗺️ Visueller Abgleich auf der Deutschlandkarte:")
        df_tipps = res["tabelle"].copy()
        df_tipps["Ziel_Lon"] = res["ziel_lon"]
        df_tipps["Ziel_Lat"] = res["ziel_lat"]
        
        df_ziel = pd.DataFrame([{"lon": res["ziel_lon"], "lat": res["ziel_lat"], "name": res["ziel"]}])
        
        line_layer = pdk.Layer(
            "ArcLayer", data=df_tipps,
            get_source_position="[Tipp_Lon, Tipp_Lat]", get_target_position="[Ziel_Lon, Ziel_Lat]",
            get_source_color="[255, 75, 75, 160]", get_target_color="[46, 196, 182, 255]", get_width=5
        )
        tipp_layer = pdk.Layer(
            "ScatterplotLayer", data=df_tipps, get_position="[Tipp_Lon, Tipp_Lat]",
            get_color="[255, 75, 75]", get_radius=12000
        )
        ziel_layer = pdk.Layer(
            "ScatterplotLayer", data=df_ziel, get_position="[lon, lat]",
            get_color="[46, 196, 182]", get_radius=18000
        )
        label_layer = pdk.Layer(
            "TextLayer", data=df_tipps, get_position="[Tipp_Lon, Tipp_Lat]",
            get_text="Spieler", get_size=15, get_color="[255, 255, 255]",
            background_color="[0, 0, 0, 180]"
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=[line_layer, tipp_layer, ziel_layer, label_layer],
            initial_view_state=pdk.ViewState(longitude=10.45, latitude=51.16, zoom=5.0, pitch=35, controller=True),
            map_style=None
        ))

# --- ANSICHT 2: PUNKTESTAND ---
elif st.session_state.ansicht == "score":
    st.subheader("📊 Globaler Punktestand")
    score_data = [{"Spieler": k, "Gesamtpunkte": v} for k, v in st.session_state.scores.items() if k in st.session_state.spieler_namen]
    df_score = pd.DataFrame(score_data)
    
    if not df_score.empty:
        df_score = df_score.sort_values(by="Gesamtpunkte", ascending=False).reset_index(drop=True)
        st.dataframe(df_score.set_index("Spieler"), use_container_width=True)
        st.bar_chart(df_score.set_index("Spieler"), y="Gesamtpunkte", color="#4bd6ff")
        
    if st.button("Scoreboard zurücksetzen 🔄", type="secondary"):
        st.session_state.scores = {name: 0 for name in st.session_state.spieler_namen}
        st.session_state.runde = 0
        st.session_state.runden_ergebnis = None
        st.session_state.aktuelle_frage = frische_frage_ziehen(st.session_state.gewaehlte_karte)
        st.session_state.ansicht = "spiel"
        st.session_state.scan_modus_aktiv = False
        st.rerun()
