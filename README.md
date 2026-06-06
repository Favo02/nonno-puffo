# Nonno Puffo - Guida TV per la Stampa

Generatore di guida TV cartacea ad alta leggibilità per parenti anziani, che include i principali canali nazionali italiani e il pacchetto Sky Sport.

Il layout è ottimizzato per la stampa fronte-retro (A4): tutti i canali sono uniti in un flusso continuo a tre colonne che si distribuisce su più pagine, inserendo un'interruzione di pagina solo tra un giorno e l'altro.

## Prerequisiti

1. [**Python**](https://www.python.org/) (versione 3.9 o superiore)
2. [**uv**](https://astral-sh/uv) (gestore di pacchetti Python rapido ed efficiente)
3. [**Typst**](https://typst.app/home) (compilatore PDF moderno, rapido ed elegante)

## Esecuzione

Per avviare la generazione della guida con le opzioni predefinite:

```bash
uv run main.py
```

Questo comando scarica il palinsesto per i prossimi **7 giorni** (a partire da **domani**) nella fascia oraria **10:00 - 22:00** e genera il file `guida_tv.pdf`.

### Opzioni disponibili

Puoi passare i seguenti parametri alla riga di comando:

```bash
uv run main.py [opzioni]
```

- `--days N`: Numero di giorni da generare (default: `7`).
- `--start-date AAAA-MM-GG`: Data di inizio della guida (default: domani).
- `--start-hour ORA`: Ora locale di inizio della fascia oraria giornaliera (default: `10`).
- `--end-hour ORA`: Ora locale di fine della fascia oraria giornaliera (default: `22`).
- `--output FILE.pdf`: Nome del file PDF generato (default: `guida_tv.pdf`).
- `--no-desc`: Rimuove le brevi trame/descrizioni dei programmi per ottenere un PDF estremamente compatto.

---

## Funzionamento Interno

Il processo di generazione si divide nelle seguenti fasi:

1. **Scaricamento in parallelo (EPG)**: Lo script non fa web scraping di pagine HTML, ma interroga direttamente le API pubbliche e non protette di Sky Italia. Per velocizzare il processo, lo script esegue le richieste HTTP per ciascun canale in parallelo tramite un `ThreadPoolExecutor` (fino a 8 connessioni simultanee), completando il download di una settimana di palinsesto per 25 canali in circa 1-2 secondi.
2. **Conversione di Fuso Orario**: Le API di Sky restituiscono gli orari in formato UTC (es. `2026-06-06T20:30:00Z`). Lo script converte queste date nel fuso orario italiano (`Europe/Rome`), gestendo in automatico l'ora solare e l'ora legale (CEST/CET).
3. **Gestione della Giornata TV**: Per evitare che i programmi in tarda serata vengano spezzati a mezzanotte, lo script considera la giornata televisiva a partire dalle `05:00` del mattino fino alle `04:59` del giorno successivo. Qualsiasi programma che inizia tra la mezzanotte e le 04:59 viene accorpato alla serata del giorno televisivo precedente.
4. **Formattazione Typst**: I programmi raccolti vengono puliti (rimozione duplicati consecutivi, formattazione titoli ed escape dei caratteri speciali per Typst) e inseriti in un template Typst generato al volo in memoria.
5. **Compilazione PDF**: Il codice Typst viene salvato in un file temporaneo (`guida.typ`) e compilato istantaneamente in PDF invocando il comando `typst compile`. Al termine, il file temporaneo viene eliminato.

---

## Come Aggiungere Nuovi Canali

Tutti i canali inclusi nella guida sono definiti all'inizio di `main.py` nella lista `CANALI`. Ciascun canale è rappresentato da un dizionario Python con i seguenti campi:

```python
{"id": "899", "name": "Rai 1", "color": "rgb(\"#1a3a5f\")"}
```

- `id`: L'identificativo numerico del canale (stringa).
- `name`: Il nome visualizzato come intestazione sul PDF.
- `color`: Il colore associato all'intestazione della scheda (in formato Typst `rgb(...)` o colore predefinito).

### Come Reperire l'ID di un Canale

Tutti i canali disponibili sul database di Sky Italia (che comprende quasi tutti i canali nazionali in chiaro del digitale terrestre, oltre ai canali satellitari e Sky Sport) possono essere consultati richiamando l'endpoint della loro API ufficiale:

```
https://apid.sky.it/gtv/v1/channels?env=DTH
```

Questo endpoint restituisce un array JSON contenente l'elenco completo di canali. Per ciascun canale, troverai informazioni come:

```json
{
  "id": 12116,
  "name": "NOVE HD",
  "number": 149,
  "servicekey": "1009"
}
```

1. Apri il link sopra nel browser o usa uno strumento come `curl`.
2. Cerca il canale desiderato per nome (es. `"NOVE HD"`).
3. Copia il valore del campo `"id"` (nell'esempio sopra `12116`).
4. Aggiungi una nuova riga alla lista `CANALI` in `main.py` inserendo quell'ID, il nome desiderato per la stampa e un colore a tua scelta.
