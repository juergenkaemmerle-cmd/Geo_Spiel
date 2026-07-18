import math
import random
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "super_geheimes_spiel_geheimnis_123"

# Spielfeld-Konfiguration (20x20 Gitter)
GRID_SIZE = 20
COLUMNS = [chr(i) for i in range(ord('A'), ord('A') + GRID_SIZE)]  # A bis T

# GPS-Grenzen exakt angepasst an deine Festland-Deutschlandkarte
MIN_LON, MIN_LAT, MAX_LON, MAX_LAT = 5.86, 47.27, 15.04, 54.91

STADT_POOL = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", 
    "Stuttgart", "Düsseldorf", "Leipzig", "Dortmund", "Essen",
    "Bremen", "Hannover", "Nürnberg", "Duisburg", "Flensburg",
    "Freiburg im Breisgau", "Kiel", "Erfurt", "Magdeburg", "Saarbrücken",
    "Rostock", "Kassel", "Trier", "Passau", "Garmisch-Partenkirchen",
    "Görlitz", "Aachen", "Emden", "Cottbus", "Ulm"
]

def get_grid_coordinates(lon, lat):
    """Rechnet GPS-Koordinaten in das korrekte Gitterfeld (z.B. 'K10') um."""
    pct_x = (lon - MIN_LON) / (MAX_LON - MIN_LON)
    pct_y = 1.0 - ((lat - MIN_LAT) / (MAX_LAT - MIN_LAT))
    
    col_idx = max(0, min(GRID_SIZE - 1, int(math.floor(pct_x * GRID_SIZE))))
    row_idx = max(0, min(GRID_SIZE - 1, int(math.floor(pct_y * GRID_SIZE))))
    
    return f"{COLUMNS[col_idx]}{row_idx + 1}"

def get_field_center_gps(feld_string):
    """Berechnet die echten GPS-Koordinaten für den Mittelpunkt eines Kästchens (z.B. 'K10')."""
    try:
        col_char = feld_string[0].upper()
        row_num = int(feld_string[1:])
        
        col_idx = COLUMNS.index(col_char)
        row_idx = row_num - 1
        
        # Breite eines einzelnen Kästchens in GPS-Graden
        lon_step = (MAX_LON - MIN_LON) / GRID_SIZE
        lat_step = (MAX_LAT - MIN_LAT) / GRID_SIZE
        
        # Mittelpunkt berechnen (Index + 0.5 für die Mitte des Kästchens)
        center_lon = MIN_LON + (col_idx + 0.5) * lon_step
        center_lat = MAX_LAT - (row_idx + 0.5) * lat_step  # Von Norden nach Süden
        
        return center_lon, center_lat
    except (ValueError, IndexError):
        # Fallback falls die Eingabe fehlerhaft war (z.B. Mitte von Deutschland)
        return (MIN_LON + MAX_LON) / 2, (MIN_LAT + MAX_LAT) / 2

def haversine_distance(lon1, lat1, lon2, lat2):
    """Berechnet den exakten Abstand zwischen zwei GPS-Punkten in Kilometern."""
    R = 6371.0  # Erdradius in Kilometern
    
    # Umwandlung in Bogenmaß (Radians)
    rad_lon1, rad_lat1 = math.radians(lon1), math.radians(lat1)
    rad_lon2, rad_lat2 = math.radians(lon2), math.radians(lat2)
    
    dlon = rad_lon2 - rad_lon1
    dlat = rad_lat2 - rad_lat1
    
    # Haversine-Formel
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def hole_stadt_gps(stadtname):
    """Gibt die echten GPS-Koordinaten der gesuchten Städte zurück."""
    koordinaten = {
        "Berlin": (13.4050, 52.5200), "Hamburg": (9.9937, 53.5511), "München": (11.5820, 48.1351),
        "Köln": (6.9583, 50.9375), "Frankfurt am Main": (8.6821, 50.1109), "Stuttgart": (9.1813, 48.7758),
        "Aachen": (6.0839, 50.7753), "Görlitz": (14.9872, 51.1528), "Flensburg": (9.4354, 54.7836),
        "Garmisch-Partenkirchen": (11.0955, 47.4917), "Düsseldorf": (6.7762, 51.2277), "Leipzig": (12.3731, 51.3396)
    }
    # Fallback-Koordinaten (Mitte Deutschlands), falls eine Stadt im Pool fehlt
    return koordinaten.get(stadtname, (9.99, 51.16))

@app.route('/')
def index():
    if 'scores' not in session:
        session['scores'] = {}
    if 'runde' not in session:
        session['runde'] = 0
    if 'aktuelle_stadt' not in session:
        session['aktuelle_stadt'] = random.choice(STADT_POOL)
        
    lon, lat = hole_stadt_gps(session['aktuelle_stadt'])
    session['stadt_lon'] = lon
    session['stadt_lat'] = lat
    session['korrektes_feld'] = get_grid_coordinates(lon, lat)
    
    return render_template('index.html', 
                           stadt=session['aktuelle_stadt'], 
                           scores=session['scores'], 
                           runde=session['runde'])

@app.route('/tippen', methods=['POST'])
def tippen():
    tipps = {}
    for key, val in request.form.items():
        if key.startswith('spieler_') and val:
            spieler_name = key.replace('spieler_', '')
            tipps[spieler_name] = val.upper().strip()
            
    korrektes_feld = session['korrektes_feld']
    stadt_lon = session['stadt_lon']
    stadt_lat = session['stadt_lat']
    scores = session['scores']
    
    abstaende_km = {}
    letzte_details = {}
    
    # Punkte-Berechnung
    for spieler, tipp in tipps.items():
        if spieler not in scores:
            scores[spieler] = 0
            
        # Volltreffer prüfen (3 Punkte)
        if tipp == korrektes_feld:
            scores[spieler] += 3
            
        # 1. Mittelpunkt des getippten Kästchens bestimmen
        tipp_lon, tipp_lat = get_field_center_gps(tipp)
        
        # 2. Exakten geografischen Abstand zur Stadt in km berechnen
        abstand_km = haversine_distance(tipp_lon, tipp_lat, stadt_lon, stadt_lat)
        abstaende_km[spieler] = abstand_km
        
        letzte_details[spieler] = {
            "tipp": tipp,
            "abstand": round(abstand_km, 1)
        }
    
    # Trostpunkt vergeben: Wer ist am nächsten dran (kleinster km-Abstand)?
    if abstaende_km:
        min_abstand = min(abstaende_km.values())
        for spieler, abstand in abstaende_km.items():
            if abstand == min_abstand:
                scores[spieler] += 1
                letzte_details[spieler]["trostpunkt"] = True
            else:
                letzte_details[spieler]["trostpunkt"] = False
                
    session['scores'] = scores
    session['runde'] += 1
    
    session['letzte_auswertung'] = {
        "stadt": session['aktuelle_stadt'],
        "korrekt": korrektes_feld,
        "spieler_details": letzte_details
    }
    
    session['aktuelle_stadt'] = random.choice(STADT_POOL)
    return redirect(url_for('aufloesung'))

@app.route('/aufloesung')
def aufloesung():
    daten = session.get('letzte_auswertung', {})
    return render_template('aufloesung.html', daten=daten, scores=session['scores'])

@app.route('/reset')
def reset():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
