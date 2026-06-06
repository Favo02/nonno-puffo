# Nonno Puffo - Guida TV per la Stampa

Questo progetto genera una guida TV settimanale cartacea ad alta leggibilità per parenti anziani, includendo i principali canali nazionali e Sky Sport.

Il layout è ottimizzato per la stampa fronte-retro (A4): ogni giorno occupa esattamente un foglio (fronte Canali in Chiaro, retro Sky Sport).

## Prerequisiti

1. **Python 3.9+**
2. **uv** (consigliato per eseguire Python):
   - macOS/Linux: `curl -LsSf https://astral-sh/uv/install.sh | sh`
   - Windows: `powershell -c "irm https://astral-sh/uv/install.ps1 | iex"`
3. **Typst** (per compilare il PDF):
   - macOS/Linux: `brew install typst`
   - Windows: `winget install Typst.Typst`

## Esecuzione

Genera la guida TV di 7 giorni a partire da oggi (fascia serale 18:00 - 23:59):

```bash
uv run main.py
```

### Opzioni principali

```bash
uv run main.py [opzioni]
```

- `--days N`: Numero di giorni da generare (default: `7`).
- `--start-date AAAA-MM-GG`: Data di inizio (default: oggi).
- `--start-hour ORA` / `--end-hour ORA`: Fascia oraria (default: `18` - `23`).
- `--output FILE.pdf`: Nome del PDF generato (default: `guida_tv.pdf`).
- `--no-desc`: Rimuove le brevi descrizioni dei programmi per maggiore compattezza.
