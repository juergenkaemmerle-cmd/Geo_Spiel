import io
import math
import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# 1. Daten laden und säubern
def lade_fragen():
    df = pd.read_csv("fragen.csv", sep=";")
    df.columns = df.columns.str.strip()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].str.strip()
    return df

try:
    df = lade_fragen()
except Exception as e:
    print(f"Fehler beim Laden der CSV: {e}")
    exit()

# 2. Druck-Layout-Einstellungen (DIN A4 Querformat bei 300 DPI)
# 1 DIN A4 = 297mm x 210mm. Bei 300 DPI sind das ca. 3508 x 2480 Pixel.
WIDTH, HEIGHT = 3508, 2480
ROWS, COLS = 3, 2
CARD_WIDTH = WIDTH // COLS
CARD_HEIGHT = HEIGHT // ROWS

# 3. Schriften laden (Fallbacks für Windows/Mac)
def get_font(font_name, size):
    try:
        # Windows Pfad
        return ImageFont.truetype(font_name, size)
    except IOError:
        try:
            # Mac Pfad / Alternativ
            return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
        except IOError:
            # Absoluter Fallback
            return ImageFont.load_default()

font_id = get_font("arialbd.ttf", 60)       # Große ID oben links
font_kat = get_font("arial.ttf", 45)        # Kategorie oben rechts
font_frage = get_font("arialbd.ttf", 50)    # Die Frage selbst
font_ziel = get_font("arial.ttf", 45)       # Das gesuchte Ziel (fett markiert im Text)
font_info = get_font("arial.ttf", 36)       # Hintergrund-Info

def wrap_text(text, font, max_width, draw):
    """Bricht Text automatisch in Zeilen um, damit er in die Karte passt."""
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        # Teste Breite der aktuellen Zeile
        bbox = draw.textbbox((0, 0), ' '.join(current_line), font=font)
        w = bbox[2] - bbox[0]
        if w > max_width:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(' '.join(current_line))
    return lines

# 4. Karten zeichnen
anzahl_karten = len(df)
seiten_anzahl = math.ceil(anzahl_karten / (ROWS * COLS))

os.makedirs("ausdruck_karten", exist_ok=True)

for seite in range(seiten_anzahl):
    # Neue weiße DIN-A4 Seite erstellen
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    
    for i in range(ROWS * COLS):
        index = seite * (ROWS * COLS) + i
        if index >= anzahl_karten:
            break
            
        row = i // COLS
        col = i % COLS
        
        # Startkoordinaten der aktuellen Karte
        x_start = col * CARD_WIDTH
        y_start = row * CARD_HEIGHT
        x_end = x_start + CARD_WIDTH
        y_end = y_start + CARD_HEIGHT
        
        # Schneidelinien zeichnen (Grauer Rahmen um jede Karte)
        draw.rectangle([x_start, y_start, x_end, y_end], outline="#CCCCCC", width=3)
        
        # Daten der aktuellen Frage holen
        row_data = df.iloc[index]
        f_id = f"ID: {index}"
        kat = row_data["karte"]
        frage = row_data["frage"]
        ziel = f"LÖSUNG: {row_data['ziel']}"
        info = f"Info: {row_data['info']}"
        
        # Innenabstand (Padding)
        pad_x = 60
        max_text_w = CARD_WIDTH - (2 * pad_x)
        
        # --- OBERE ZEILE: ID & Kategorie ---
        draw.text((x_start + pad_x, y_start + 50), f_id, fill="#1f77b4", font=font_id)
        
        bbox_kat = draw.textbbox((0, 0), kat, font=font_kat)
        kat_w = bbox_kat[2] - bbox_kat[0]
        draw.text((x_end - pad_x - kat_w, y_start + 65), kat, fill="#555555", font=font_kat)
        
        # Trennlinie unter dem Header
        draw.line([x_start + pad_x, y_start + 140, x_end - pad_x, y_start + 140], fill="#DDDDDD", width=2)
        
        # --- MITTE: Frage ---
        y_cursor = y_start + 180
        frage_lines = wrap_text(frage, font_frage, max_text_w, draw)
        for line in frage_lines:
            draw.text((x_start + pad_x, y_cursor), line, fill="black", font=font_frage)
            y_cursor += 65
            
        # --- UNTEN: Lösung & Info (Für den Quizmaster) ---
        # Fixiert am unteren Rand der Karte platziert
        y_unten = y_end - 280
        
        # Grüne Box für das Ziel/Lösung
        draw.rectangle([x_start + pad_x, y_unten, x_end - pad_x, y_unten + 70], fill="#E8F5E9", outline="#A5D6A7", width=2)
        draw.text((x_start + pad_x + 20, y_unten + 10), ziel, fill="#2E7D32", font=font_id) # Nutzen font_id für Fett-Effekt
        
        # Info-Text darunter
        y_cursor = y_unten + 90
        info_lines = wrap_text(info, font_info, max_text_w, draw)
        for line in info_lines[:2]: # Maximal 2 Zeilen Info, damit es nicht überlappt
            draw.text((x_start + pad_x, y_cursor), line, fill="#666666", font=font_info)
            y_cursor += 45

    # Seite abspeichern
    img.save(f"ausdruck_karten/geo_quiz_seite_{seite + 1}.png", "PNG")
    print(f"Seite {seite + 1} erfolgreich generiert.")

print("\nFertig! Alle Karten liegen im Ordner 'ausdruck_karten' als hochauflösende PNGs bereit zum Drucken.")
