#!/usr/bin/env python3
import argparse
import urllib.request
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# CONFIGURAZIONE CANALI
# ==========================================

CANALI_CHIARO = [
    {"id": "899", "name": "Rai 1"},
    {"id": "898", "name": "Rai 2"},
    {"id": "897", "name": "Rai 3"},
    {"id": "10464", "name": "Rete 4"},
    {"id": "10354", "name": "Canale 5"},
    {"id": "10454", "name": "Italia 1"},
    {"id": "319", "name": "La7"},
    {"id": "8195", "name": "TV8"},
    {"id": "12116", "name": "Nove"},
]

CANALI_SPORT = [
    {"id": "9094", "name": "Sky Sport 24"},
    {"id": "11346", "name": "Sky Sport Uno"},
    {"id": "9113", "name": "Sky Sport Calcio"},
    {"id": "11237", "name": "Sky Sport Tennis"},
    {"id": "7507", "name": "Sky Sport Arena"},
    {"id": "9103", "name": "Sky Sport Max"},
    {"id": "9096", "name": "Sky Sport F1"},
    {"id": "9102", "name": "Sky Sport MotoGP"},
    {"id": "10254", "name": "Sky Sport Golf"},
]

# Nomi dei giorni e dei mesi in italiano per evitare dipendenze da locale di sistema
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
]

def formatta_data_it(dt):
    """Formatta la data in stile italiano: es. 'Lunedì 8 Giugno'"""
    giorno_sett = GIORNI[dt.weekday()]
    giorno_mese = dt.day
    mese = MESI[dt.month - 1]
    return f"{giorno_sett} {giorno_mese} {mese}"

def escape_typst(s):
    """Rende sicura una stringa per l'inserimento in Typst come stringa racchiusa da doppie virgolette"""
    if not s:
        return ""
    # Rimuove ritorni a capo per evitare problemi di formattazione
    s = s.replace("\r", "").replace("\n", " ")
    # Effettua l'escape dei backslash e delle virgolette doppie
    return s.replace("\\", "\\\\").replace("\"", "\\\"")

# ==========================================
# RETRIEVAL DATI EPG
# ==========================================

def fetch_events_for_channel(ch_id, start_utc, end_utc):
    """Scarica il palinsesto dal server Sky per un singolo canale nel range temporale specificato"""
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://apid.sky.it/gtv/v1/events?from={start_str}&to={end_str}&pageSize=999&pageNum=0&env=DTH&channels={ch_id}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read())
            return ch_id, data.get("events", [])
    except Exception as e:
        print(f"Errore nello scaricamento dei dati per il canale {ch_id}: {e}", file=sys.stderr)
        return ch_id, []

def scarica_palinsesto(start_local, days):
    """Scarica i palinsesti di tutti i canali in parallelo per ottimizzare i tempi"""
    local_tz = ZoneInfo("Europe/Rome")
    utc_tz = ZoneInfo("UTC")
    
    # Range di date in UTC
    end_local = start_local + timedelta(days=days)
    start_utc = start_local.astimezone(utc_tz)
    end_utc = end_local.astimezone(utc_tz)
    
    tutti_i_canali = CANALI_CHIARO + CANALI_SPORT
    canali_ids = [c["id"] for c in tutti_i_canali]
    
    risultati = {}
    print(f"Scaricamento della guida TV per {days} giorni a partire da {start_local.strftime('%d/%m/%Y')}...")
    
    # Scaricamento parallelo (massimo 8 connessioni contemporanee)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_events_for_channel, ch_id, start_utc, end_utc): ch_id 
            for ch_id in canali_ids
        }
        for future in as_completed(futures):
            ch_id, events = future.result()
            risultati[ch_id] = events
            
    print("Scaricamento completato con successo.")
    return risultati

# ==========================================
# ELABORAZIONE E FILTRAGGIO DATI
# ==========================================

def elabora_programmi(raw_data, start_hour, end_hour):
    """
    Raggruppa ed elabora i programmi per data TV locale e canale.
    Gestisce la fascia oraria TV (considerando i programmi dopo la mezzanotte fino alle 02:00
    come parte della serata precedente).
    """
    local_tz = ZoneInfo("Europe/Rome")
    palinsesto = {} # Struttura: {data_str: {channel_id: [programmi]}}
    
    for ch_id, events in raw_data.items():
        for ev in events:
            # parsing data inizio
            try:
                dt_utc = datetime.strptime(ev["starttime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
                dt_local = dt_utc.astimezone(local_tz)
            except Exception:
                continue
                
            # Determina la data TV locale (se prima delle 05:00 del mattino, appartiene alla giornata TV precedente)
            if dt_local.hour < 5:
                data_tv = (dt_local - timedelta(days=1)).date()
                tv_hour = dt_local.hour + 24
            else:
                data_tv = dt_local.date()
                tv_hour = dt_local.hour
                
            # Filtro per la fascia oraria configurata
            eff_end_hour = end_hour
            if end_hour < 5:
                eff_end_hour += 24
                
            if not (start_hour <= tv_hour <= eff_end_hour):
                continue
                
            data_str = data_tv.strftime("%Y-%m-%d")
            if data_str not in palinsesto:
                palinsesto[data_str] = {}
                
            if ch_id not in palinsesto[data_str]:
                palinsesto[data_str][ch_id] = []
                
            titolo = ev.get("eventTitle") or ev.get("epgEventTitle") or "Senza Titolo"
            desc = ev.get("eventSynopsis") or ""
            if desc.startswith("..."):
                desc = desc[3:].strip()
                
            palinsesto[data_str][ch_id].append({
                "ora": dt_local.strftime("%H:%M"),
                "titolo": titolo,
                "descrizione": desc,
                "time_obj": dt_local
            })
            
    # Ordina cronologicamente i programmi all'interno di ogni canale
    for data_str in palinsesto:
        for ch_id in palinsesto[data_str]:
            palinsesto[data_str][ch_id].sort(key=lambda x: x["time_obj"])
            
            # Filtra duplicati consecutivi (es. repliche o spezzoni dello stesso programma)
            unici = []
            for prog in palinsesto[data_str][ch_id]:
                if not unici or unici[-1]["ora"] != prog["ora"] or unici[-1]["titolo"] != prog["titolo"]:
                    unici.append(prog)
            
            # Rimosso il limite fisso per permettere una visualizzazione completa di tutta la fascia oraria
            palinsesto[data_str][ch_id] = unici
            
    return palinsesto

# ==========================================
# GENERAZIONE FILE TYPST
# ==========================================

def genera_file_typst(palinsesto, date_iniziale, days, start_hour, end_hour, include_desc):
    """Crea la stringa di codice Typst con tutti i programmi formattati in griglie ad alta leggibilità"""
    
    local_tz = ZoneInfo("Europe/Rome")
    ora_generazione = datetime.now(local_tz).strftime("%d/%m/%Y alle %H:%M")
    
    # Intestazione e stili del documento Typst (stile sobrio, inchiostro ridotto, ad alta leggibilità)
    content = []
    content.append(f"""#set page(
  paper: "a4",
  margin: (x: 1cm, top: 1cm, bottom: 1.2cm),
  header: align(right)[#text(8pt, fill: rgb("#7f8c8d"))[Guida TV Settimanale]],
  footer: align(center)[#text(8pt, fill: rgb("#7f8c8d"))[
    Generato con github.com/Favo02/nonno-puffo in data {ora_generazione} | Pagina #context counter(page).display()
  ]]
)
#set text(font: "Arial", size: 9pt, lang: "it")

// Componente Card semplificato (senza sfondi colorati pesanti, economico per la stampa)
#let channel-card(name, programs) = {{
  block(
    width: 100%,
    stroke: 0.8pt + black,
    radius: 3pt,
    inset: 8pt,
    breakable: false,
    [
      #align(center)[#text(weight: "bold", size: 11pt)[#upper(name)]]
      #v(2pt)
      #line(length: 100%, stroke: 0.5pt + black)
      #v(4pt)
      #if programs.len() == 0 [
        #v(1em)
        #align(center)[#text(style: "italic", fill: rgb("#7f8c8d"), size: 9pt)[Nessun programma]]
        #v(1em)
      ] else [
        #grid(
          columns: (auto, 1fr),
          column-gutter: 6pt,
          row-gutter: 6pt,
          ..programs.map(p => (
            text(weight: "bold", size: 9pt)[#p.at(0)],
            [
              #text(weight: "bold", size: 9pt)[#p.at(1)]
              #if p.at(2) != "" [
                \\\\ #text(size: 7.5pt, fill: rgb("#444444"))[#p.at(2)]
              ]
            ]
          )).flatten()
        )
      ]
    ]
  )
}}
""")

    for i in range(days):
        giorno_corrente = date_iniziale + timedelta(days=i)
        data_key = giorno_corrente.strftime("%Y-%m-%d")
        data_formattata = formatta_data_it(giorno_corrente).upper()
        
        dati_giorno = palinsesto.get(data_key, {})
        
        # ----------------------------------------------------
        # PAGINA 1: CANALI IN CHIARO
        # ----------------------------------------------------
        content.append(f"""
#align(center)[
  #text(16pt, weight: "bold")[{data_formattata}] \\
  #text(10pt, weight: "bold", fill: rgb("#555555"))[CANALI IN CHIARO (Fascia {start_hour:02d}:00 - {end_hour:02d}:59)]
]
#v(0.5em)

#columns(3, gutter: 10pt)[
""")
        
        for ch in CANALI_CHIARO:
            ch_id = ch["id"]
            progs = dati_giorno.get(ch_id, [])
            
            progs_code = []
            for p in progs:
                desc = p["descrizione"] if include_desc else ""
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                progs_code.append(f'("{p["ora"]}", "{escape_typst(p["titolo"])}", "{escape_typst(desc)}")')
                
            array_str = "(" + ", ".join(progs_code) + ")"
            content.append(f'  #channel-card("{ch["name"]}", {array_str})\n')
            
        content.append("]\n")
        content.append("#pagebreak(weak: true)\n")
        
        # ----------------------------------------------------
        # PAGINA 2: SKY SPORT
        # ----------------------------------------------------
        content.append(f"""
#align(center)[
  #text(16pt, weight: "bold")[{data_formattata}] \\
  #text(10pt, weight: "bold", fill: rgb("#555555"))[SKY SPORT (Fascia {start_hour:02d}:00 - {end_hour:02d}:59)]
]
#v(0.5em)

#columns(3, gutter: 10pt)[
""")
        
        for ch in CANALI_SPORT:
            ch_id = ch["id"]
            progs = dati_giorno.get(ch_id, [])
            
            progs_code = []
            for p in progs:
                desc = p["descrizione"] if include_desc else ""
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                progs_code.append(f'("{p["ora"]}", "{escape_typst(p["titolo"])}", "{escape_typst(desc)}")')
                
            array_str = "(" + ", ".join(progs_code) + ")"
            content.append(f'  #channel-card("{ch["name"]}", {array_str})\n')
            
        content.append("]\n")
        
        if i < days - 1:
            content.append("#pagebreak(weak: true)\n")
            
    return "".join(content)

# ==========================================
# METODO PRINCIPALE
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Genera una guida TV settimanale in PDF ottimizzata per la stampa e ad alta leggibilità.")
    parser.add_argument("--days", type=int, default=7, help="Numero di giorni da includere nella guida (default: 7)")
    parser.add_argument("--start-date", type=str, default=None, help="Data iniziale nel formato AAAA-MM-GG (default: oggi)")
    parser.add_argument("--start-hour", type=int, default=18, help="Ora iniziale della fascia oraria locale (default: 18)")
    parser.add_argument("--end-hour", type=int, default=23, help="Ora finale della fascia oraria locale (default: 23)")
    parser.add_argument("--output", type=str, default="guida_tv.pdf", help="Nome del file PDF generato (default: guida_tv.pdf)")
    parser.add_argument("--no-desc", action="store_true", help="Se specificato, non include le trame/descrizioni dei programmi")
    
    args = parser.parse_args()
    
    local_tz = ZoneInfo("Europe/Rome")
    
    if args.start_date:
        try:
            start_date_only = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            start_local = datetime(start_date_only.year, start_date_only.month, start_date_only.day, 0, 0, 0, tzinfo=local_tz)
        except ValueError:
            print(f"Errore: la data '{args.start_date}' non è valida. Usa il formato AAAA-MM-GG.", file=sys.stderr)
            sys.exit(1)
    else:
        ora_oggi = datetime.now(local_tz)
        start_local = datetime(ora_oggi.year, ora_oggi.month, ora_oggi.day, 0, 0, 0, tzinfo=local_tz)
        
    raw_data = scarica_palinsesto(start_local, args.days)
    palinsesto = elabora_programmi(raw_data, args.start_hour, args.end_hour)
    
    codice_typst = genera_file_typst(
        palinsesto, 
        start_local, 
        args.days, 
        args.start_hour, 
        args.end_hour, 
        not args.no_desc
    )
    
    temp_typ_file = "guida.typ"
    try:
        with open(temp_typ_file, "w", encoding="utf-8") as f:
            f.write(codice_typst)
        
        print(f"Compilazione del PDF '{args.output}' tramite Typst...")
        result = subprocess.run(
            ["typst", "compile", temp_typ_file, args.output], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            print(f"Successo! La guida TV è stata salvata in: {os.path.abspath(args.output)}")
        else:
            print(f"Errore durante la compilazione Typst:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
            
    finally:
        if os.path.exists(temp_typ_file):
            try:
                os.remove(temp_typ_file)
            except OSError:
                pass

if __name__ == "__main__":
    main()
