import math
import random
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
# WICHTIG: Ersetze das durch ein sicheres Geheimnis deiner Wahl
app.secret_key = "super_geheimes_spiel_geheimnis_123"

# Spielfeld-Konfiguration (20x20 Gitter)
GRID_SIZE = 20
COLUMNS = [chr(i) for i in range(ord('A'), ord('A') + GRID_SIZE)]  # A bis T

# GPS-Grenzen exakt angepasst an deine Festland-Deutschlandkarte
KARTEN_DATEN = {
    "Deutschland 🇩🇪": {"bounds": (5.86, 47.27, 15.04, 54.91), "such_zusatz": ", Germany"}
}

# Eine Liste von interessanten Beispiel-Städten für das Spiel
STADT_POOL = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", 
    "Stuttgart", "Düsseldorf", "Leipzig", "Dortmund", "Essen",
    "Bremen", "Hannover", "Nürnberg", "Duisburg", "Flensburg",
    "Freiburg im Breisgau", "Kiel", "Erfurt", "Magdeburg", "Saarbrücken",
    "Rostock", "Kassel", "Trier", "Passau", "Garmisch-Partenkirchen",
    "Görlitz", "Aachen", "Emden", "Cottbus", "Ulm"
]

def get_grid_coordinates(lon, lat):
    """Rechnet GPS-Koordinaten in ein Gitterfeld (A-T, 1-20) für das Festland um."""
    min_lon, min_lat, max_lon, max_lat = KARTEN_DATEN["Deutschland 🇩🇪"]["bounds"]
    
    # Berechne, in welchem Prozentbereich der Punkt liegt
    pct_x = (lon - min_lon) / (max_lon - min_lon)
    # y-Achse umdrehen, da Zeile 1 im Norden (oben) und Zeile 20 im Süden (unten) ist
    pct_y = 1.0 - ((lat - min_lat) / (max_lat - min_lat))
    
    # In Gitter-Index umwandeln (0 bis 19)
    col_idx = int(math.floor(pct_x * GRID_SIZE))
    row_idx = int(math.floor(pct_y * GRID_SIZE))
    
    # Begrenzen, falls der Punkt leicht außerhalb liegt
    col_idx = max(0, min(GRID_SIZE - 1, col_idx))
    row_idx = max(0, min(GRID_SIZE - 1, row_idx))
    
    # Rückgabe als (Buchstabe, Zahl von 1-20)
    return COLUMNS[col_idx], row_idx + 1

def berechne_abstand(feld1, feld2):
    """Berechnet den Abstand zwischen zwei Feldern (Manhattan-Distanz)."""
    # feld ist ein String wie "K10"
    col1, row1 = COLUMNS.index(feld1[0]), int(feld1[1:])
    col2, row2 = COLUMNS.index(feld2[0]), int(feld2[1:])
    return abs(col1 - col2) + abs(row1 - row2)

# Dummy-Funktion für die GPS-Suche (Ersetze dies durch deine echte API-Abfrage, falls vorhanden)
def hole_stadt_gps(stadtname):
    # Für diese Demo geben wir feste Koordinaten für ein paar bekannte Städte zurück
    # Im echten Spiel fragt dein Code hier Nominatim/OpenStreetMap ab
    koordinaten = {
        "Berlin": (13.40, 52.52), "Hamburg": (10.00, 53.55), "München": (11.58, 48.13),
        "Köln": (6.96, 50.94), "Frankfurt am Main": (8.68, 50.11), "Stuttgart": (9.18, 48.77),
        "Aachen": (6.08, 50.77), "Görlitz": (14.99, 51.15), "Flensburg": (9.43, 54.78),
        "Garmisch-Partenkirchen": (11.09, 47.49)
    }
    return koordinaten.get(stadtname, (9.99, 51.16)) # Standardmitte als Fallback

@app.route('/')
def index():
    # Spielstand initialisieren, falls noch nicht vorhanden
    if 'scores' not in session:
        session['scores'] = {}
    if 'runde' not in session:
        session['runde'] = 0
    if 'aktuelle_stadt' not in session:
        session['aktuelle_stadt'] = random.choice(STADT_POOL)
        
    # Korrektes Feld für die aktuelle Stadt berechnen
    lon, lat = hole_stadt_gps(session['aktuelle_stadt'])
    session['korrektes_feld'] = "".join(map(str, get_grid_coordinates(lon, lat)))
    
    return render_template('index.html', 
                           stadt=session['aktuelle_stadt'], 
                           scores=session['scores'], 
                           runde=session['runde'])

@app.route('/tippen', models=['POST'])
def tippen():
    # Tipps der Spieler aus dem Formular einsammeln
    # Das Formular sendet z.B. spieler1="K10", spieler2="L11" etc.
    tipps = {}
    for key, val in request.form.items():
        if key.startswith('spieler_') and val:
            spieler_name = key.replace('spieler_', '')
            tipps[spieler_name] = val.upper().strip()
            
    korrektes_feld = session['korrektes_feld']
    scores = session['scores']
    
    # 1. Auswertung: Wer hat einen Volltreffer? (3 Punkte)
    # Gleichzeitig berechnen wir die Abstände für den Trostpunkt
    abstaende = {}
    for spieler, tipp in tipps.items():
        if spieler not in scores:
            scores[spieler] = 0
            
        if tipp == korrektes_feld:
            scores[spieler] += 3
            
        # Abstand zum korrekten Feld berechnen
        abstaende[spieler] = berechne_abstand(tipp, korrektes_feld)
    
    # 2. Auswertung: Wer ist am nächsten dran? (1 Punkt)
    if abstaende:
        min_abstand = min(abstaende.values())
        # Es können auch mehrere Spieler gleich nah dran sein!
        for spieler, abstand in abstaende.items():
            if abstand == min_abstand:
                scores[spieler] += 1
                
    # Spielstand in der Session speichern
    session['scores'] = scores
    session['runde'] += 1
    
    # Letzte Ergebnisse für die Auflösungs-Seite zwischenspeichern
    session['letzte_auswertung'] = {
        "stadt": session['aktuelle_stadt'],
        "korrekt": korrektes_feld,
        "tipps": tipps
    }
    
    # Nächste Stadt für die kommende Runde auswählen
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
