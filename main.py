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
# CONFIGURAZIONE UNICA CANALI
# ==========================================

CANALI = [
    # Nazionali in chiaro principali
    {"id": "899", "name": "Rai 1", "color": 'rgb("#1a3a5f")'},
    {"id": "898", "name": "Rai 2", "color": 'rgb("#9c27b0")'},
    {"id": "897", "name": "Rai 3", "color": 'rgb("#2e7d32")'},
    {"id": "10464", "name": "Rete 4", "color": 'rgb("#e65100")'},
    {"id": "10354", "name": "Canale 5", "color": 'rgb("#1565c0")'},
    {"id": "10454", "name": "Italia 1", "color": 'rgb("#00838f")'},
    {"id": "319", "name": "La7", "color": 'rgb("#d84315")'},
    {"id": "8195", "name": "TV8", "color": 'rgb("#c2185b")'},
    {"id": "12116", "name": "Nove", "color": 'rgb("#37474f")'},
    # Altri canali DTT gratuiti popolari
    {"id": "10458", "name": "20 Mediaset", "color": 'rgb("#ff6f00")'},
    {"id": "8133", "name": "Cielo", "color": 'rgb("#0091ea")'},
    {"id": "12120", "name": "DMAX", "color": 'rgb("#558b2f")'},
    {"id": "12123", "name": "Food Network", "color": 'rgb("#d81b60")'},
    {"id": "895", "name": "Rai News 24", "color": 'rgb("#b71c1c")'},
    # Canali sportivi gratuiti
    {"id": "807", "name": "Rai Sport", "color": 'rgb("#0d47a1")'},
    {"id": "6000", "name": "SuperTennis", "color": 'rgb("#43a047")'},
    # Pacchetto Sky Sport
    {"id": "9094", "name": "Sky Sport 24", "color": 'rgb("#0288d1")'},
    {"id": "11346", "name": "Sky Sport Uno", "color": 'rgb("#d32f2f")'},
    {"id": "9113", "name": "Sky Sport Calcio", "color": 'rgb("#388e3c")'},
    {"id": "11237", "name": "Sky Sport Tennis", "color": 'rgb("#7b1fa2")'},
    {"id": "9103", "name": "Sky Sport Max", "color": 'rgb("#c2185b")'},
    {"id": "9096", "name": "Sky Sport F1", "color": 'rgb("#e53935")'},
    {"id": "9102", "name": "Sky Sport MotoGP", "color": 'rgb("#1976d2")'},
]

# Nomi dei giorni e dei mesi in italiano
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = [
    "Gennaio",
    "Febbraio",
    "Marzo",
    "Aprile",
    "Maggio",
    "Giugno",
    "Luglio",
    "Agosto",
    "Settembre",
    "Ottobre",
    "Novembre",
    "Dicembre",
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
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ==========================================
# RETRIEVAL DATI EPG
# ==========================================


def fetch_events_for_channel(ch_id, start_utc, end_utc):
    """Scarica il palinsesto dal server Sky per un singolo canale nel range temporale specificato"""
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://apid.sky.it/gtv/v1/events?from={start_str}&to={end_str}&pageSize=999&pageNum=0&env=DTH&channels={ch_id}"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read())
            return ch_id, data.get("events", [])
    except Exception as e:
        print(
            f"Errore nello scaricamento dei dati per il canale {ch_id}: {e}",
            file=sys.stderr,
        )
        return ch_id, []


def scarica_palinsesto(start_local, days):
    """Scarica i palinsesti di tutti i canali in parallelo"""
    local_tz = ZoneInfo("Europe/Rome")
    utc_tz = ZoneInfo("UTC")

    # Range di date in UTC
    end_local = start_local + timedelta(days=days)
    start_utc = start_local.astimezone(utc_tz)
    end_utc = end_local.astimezone(utc_tz)

    canali_ids = [c["id"] for c in CANALI]

    risultati = {}
    print(
        f"Scaricamento della guida TV per {days} giorni a partire da {start_local.strftime('%d/%m/%Y')}..."
    )

    # Scaricamento parallelo
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
    Gestisce la fascia oraria TV (considerando i programmi dopo la mezzanotte fino alle 04:59
    come parte della serata precedente).
    """
    local_tz = ZoneInfo("Europe/Rome")
    palinsesto = {}  # Struttura: {data_str: {channel_id: [programmi]}}

    for ch_id, events in raw_data.items():
        for ev in events:
            try:
                dt_utc = datetime.strptime(
                    ev["starttime"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=ZoneInfo("UTC"))
                dt_local = dt_utc.astimezone(local_tz)
            except Exception:
                continue

            if dt_local.hour < 5:
                data_tv = (dt_local - timedelta(days=1)).date()
                tv_hour = dt_local.hour + 24
            else:
                data_tv = dt_local.date()
                tv_hour = dt_local.hour

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

            palinsesto[data_str][ch_id].append(
                {
                    "ora": dt_local.strftime("%H:%M"),
                    "titolo": titolo,
                    "descrizione": desc,
                    "time_obj": dt_local,
                }
            )

    # Ordinamento cronologico e rimozione duplicati consecutivi
    for data_str in palinsesto:
        for ch_id in palinsesto[data_str]:
            palinsesto[data_str][ch_id].sort(key=lambda x: x["time_obj"])

            unici = []
            for prog in palinsesto[data_str][ch_id]:
                if (
                    not unici
                    or unici[-1]["ora"] != prog["ora"]
                    or unici[-1]["titolo"] != prog["titolo"]
                ):
                    unici.append(prog)
            palinsesto[data_str][ch_id] = unici

    return palinsesto


# ==========================================
# GENERAZIONE FILE TYPST
# ==========================================


def genera_file_typst(
    palinsesto, date_iniziale, days, start_hour, end_hour, include_desc
):
    """Crea la stringa di codice Typst con tutti i canali e programmi in un unico flusso a tre colonne"""

    local_tz = ZoneInfo("Europe/Rome")
    ora_generazione = datetime.now(local_tz).strftime("%d/%m/%Y alle %H:%M")

    content = []
    content.append(f"""#set page(
  paper: "a4",
  margin: (x: 0.6cm, top: 0.8cm, bottom: 0.8cm),
  header: none,
  footer: none
)
#set text(font: "Arial", size: 8.5pt, lang: "it")

// Componente Card del canale (colorato, breakable per scorrere tra le colonne)
#let channel-card(name, color, programs) = {{
  block(
    width: 100%,
    stroke: 0.5pt + color.lighten(40%),
    radius: 4pt,
    clip: true,
    fill: white,
    [
      #block(
        fill: color,
        width: 100%,
        inset: (x: 6pt, y: 5pt),
        [#align(center)[#text(fill: white, weight: "bold", size: 10.5pt)[#upper(name)]]]
      )
      #pad(top: 3pt, bottom: 4pt, left: 5pt, right: 5pt)[
        #if programs.len() == 0 [
          #v(0.5em)
          #align(center)[#text(style: "italic", fill: rgb("#7f8c8d"), size: 8pt)[Nessun programma]]
          #v(0.5em)
        ] else [
          #grid(
            columns: (auto, 1fr),
            column-gutter: 5pt,
            row-gutter: 4pt,
            ..programs.map(p => (
              text(weight: "bold", size: 8.5pt, fill: color.darken(25%))[#p.at(0)],
              [
                #text(weight: "bold", size: 8.5pt, fill: rgb("#2c3e50"))[#p.at(1)]
                #if p.at(2) != "" [
                  \\\\ #text(size: 7.2pt, fill: rgb("#555555"))[#p.at(2)]
                ]
              ]
            )).flatten()
          )
        ]
      ]
    ]
  )
}}
""")

    for i in range(days):
        giorno_corrente = date_iniziale + timedelta(days=i)
        data_key = giorno_corrente.strftime("%Y-%m-%d")
        data_formattata = formatta_data_it(giorno_corrente).upper()
        giorno_anno = giorno_corrente.timetuple().tm_yday

        dati_giorno = palinsesto.get(data_key, {})

        footer_giorno = f"""
        #place(left)[#text(6pt, fill: rgb("#7f8c8d"))[Generato con github.com/Favo02/nonno-puffo in data {ora_generazione}]]
        #align(right)[#text(7.5pt, fill: rgb("#7f8c8d"))[Giorno dell'anno: {giorno_anno} | Pagina #context counter(page).display()]]
        """

        # Scrittura del layout per il giorno corrente (Tutti i canali insieme)
        content.append(f"""
#set page(
  header: align(center)[#text(13pt, weight: "bold")[{data_formattata} (Fascia {start_hour:02d}:00 - {end_hour:02d}:59)]],
  footer: [ {footer_giorno} ]
)

#columns(3, gutter: 8pt)[
""")

        for ch in CANALI:
            ch_id = ch["id"]
            progs = dati_giorno.get(ch_id, [])

            progs_code = []
            for p in progs:
                desc = p["descrizione"] if include_desc else ""
                if len(desc) > 90:
                    desc = desc[:87] + "..."
                progs_code.append(
                    f'("{p["ora"]}", "{escape_typst(p["titolo"])}", "{escape_typst(desc)}")'
                )

            array_str = "(" + ", ".join(progs_code) + ")"
            content.append(
                f'  #channel-card("{ch["name"]}", {ch["color"]}, {array_str})\n'
            )

        content.append("]\n")

        # Pagebreak solo se non è l'ultimo giorno della guida
        if i < days - 1:
            content.append("#pagebreak(weak: true)\n")

    return "".join(content)


# ==========================================
# METODO PRINCIPALE
# ==========================================


def main():
    parser = argparse.ArgumentParser(
        description="Genera una guida TV settimanale in PDF ottimizzata per la stampa e ad alta leggibilità."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Numero di giorni da includere nella guida (default: 7)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Data iniziale nel formato AAAA-MM-GG (default: domani)",
    )
    parser.add_argument(
        "--start-hour",
        type=int,
        default=10,
        help="Ora iniziale della fascia oraria locale (default: 10)",
    )
    parser.add_argument(
        "--end-hour",
        type=int,
        default=22,
        help="Ora finale della fascia oraria locale (default: 22)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="guida_tv.pdf",
        help="Nome del file PDF generato (default: guida_tv.pdf)",
    )
    parser.add_argument(
        "--no-desc",
        action="store_true",
        help="Se specificato, non include le trame/descrizioni dei programmi",
    )

    args = parser.parse_args()

    local_tz = ZoneInfo("Europe/Rome")

    if args.start_date:
        try:
            start_date_only = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            start_local = datetime(
                start_date_only.year,
                start_date_only.month,
                start_date_only.day,
                0,
                0,
                0,
                tzinfo=local_tz,
            )
        except ValueError:
            print(
                f"Errore: la data '{args.start_date}' non è valida. Usa il formato AAAA-MM-GG.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        # Default: domani a mezzanotte
        ora_oggi = datetime.now(local_tz)
        ora_domani = ora_oggi + timedelta(days=1)
        start_local = datetime(
            ora_domani.year, ora_domani.month, ora_domani.day, 0, 0, 0, tzinfo=local_tz
        )

    raw_data = scarica_palinsesto(start_local, args.days)
    palinsesto = elabora_programmi(raw_data, args.start_hour, args.end_hour)

    codice_typst = genera_file_typst(
        palinsesto,
        start_local,
        args.days,
        args.start_hour,
        args.end_hour,
        not args.no_desc,
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
            text=True,
        )

        if result.returncode == 0:
            print(
                f"Successo! La guida TV è stata salvata in: {os.path.abspath(args.output)}"
            )
        else:
            print(
                f"Errore durante la compilazione Typst:\n{result.stderr}",
                file=sys.stderr,
            )
            sys.exit(1)

    finally:
        if os.path.exists(temp_typ_file):
            try:
                os.remove(temp_typ_file)
            except OSError:
                pass


if __name__ == "__main__":
    main()
