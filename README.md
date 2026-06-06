# Nonno Puffo - Guida TV per la Stampa

Generatore di guida TV cartacea ad alta leggibilità, includendo i principali canali nazionali e Sky Sport.

## Prerequisiti

1. [**Python**](https://www.python.org/)
2. [**uv**](https://astral-sh/uv) (package manager per Python, _meglio di pip_)
3. [**Typst**](https://typst.app/home) (compilatore PDF, meglio di _LaTeX_)

## Esecuzione

```bash
uv run main.py [opzioni]
```

Default (opzioni non specificate): guida per i prossimi 7 giorni (a partire da domani), dalle 10:00 alle 22:00.

- `--days N`: Numero di giorni da generare (default: `7`).
- `--start-date AAAA-MM-GG`: Data di inizio (default: domani).
- `--start-hour ORA` / `--end-hour ORA`: Fascia oraria (default: `10` - `22`).
- `--output FILE.pdf`: Nome del PDF generato (default: `guida_tv.pdf`).
- `--no-desc`: Rimuove le brevi descrizioni dei programmi per maggiore compattezza (default: non presente, descrizioni attive).

## Personalizzazione

I canali inclusi sono definiti all'inizio del file `main.py` all'interno delle liste `CANALI_CHIARO` e `CANALI_SPORT`. Ogni canale ha tre proprietà:
- `id`: l'ID numerico del canale sul database di Sky.
- `name`: il nome che verrà stampato sul PDF.
- `color`: il colore in formato Typst (es. `rgb("#1a3a5f")`) per l'intestazione della scheda del canale.

Per aggiungere, rimuovere o modificare i canali e i loro colori, basta modificare queste liste direttamente in `main.py`.

## Funzionamento interno

- **Fonte dei dati**: Lo script non effettua web scraping dell'HTML, bensì interroga direttamente le API JSON pubbliche di Sky Italia (`apid.sky.it/gtv/v1/events`).
- **Recupero ID canali**: Puoi trovare tutti i canali Sky (con i rispettivi ID numerici) interrogando l'endpoint: `https://apid.sky.it/gtv/v1/channels?env=DTH`.
- **Fuso orario**: I dati temporali restituiti in UTC vengono convertiti nel fuso orario di Roma (`Europe/Rome`), gestendo autonomamente l'ora solare/legale.
- **Giornata televisiva**: Lo script accorpa i programmi notturni (dalle 00:00 alle 04:59) alla giornata televisiva del giorno precedente per evitare interruzioni nei programmi di seconda serata.
- **Generazione PDF**: Lo script scrive temporaneamente un file `guida.typ` in sintassi Typst e lo compila al volo in PDF invocando il comando `typst compile`, eliminando il file temporaneo al termine dell'operazione.
