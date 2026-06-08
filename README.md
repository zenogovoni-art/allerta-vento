# Allerta vento 🌬️

Controlla ogni 15 minuti i dati di due stazioni meteo e ti manda un messaggio
**Telegram** quando il vento medio supera gli **8 nodi**:

- **Porto Corsini** (a sud) — Adriatico Wind Club: solo venti da E/SE/S/SW/O.
- **Lido di Volano** (a nord, `dkwa.it/meteo`): solo venti da O/NW/N/NE/E.

- Gira gratis su **GitHub Actions** (nessun PC acceso necessario).
- Avviso **solo al superamento** della soglia (niente messaggi a raffica):
  riparte solo quando il vento riscende sotto i 7 nodi e poi risale.
- Avvisi **solo di giorno** (09:00–19:00, ora italiana).
- Messaggio con **intensità**, **direzione** e **raffica**.
- Tre livelli vento (8 / 20 / 30 nodi) e **ALERT RAFFICA** (15 / 20 / 25 / 30
  nodi sul picco di giornata).

---

## 1. Crea il bot Telegram (dal Mac)

1. Apri Telegram, cerca **@BotFather**.
2. Manda `/newbot` e segui le istruzioni → ricevi un **token**
   tipo `123456789:ABCdef...`.
3. Apri una chat col tuo nuovo bot e mandagli un messaggio qualsiasi
   (es. "ciao").
4. Nel browser apri:
   `https://api.telegram.org/bot<IL_TUO_TOKEN>/getUpdates`
   e cerca `"chat":{"id": ...}`: quel numero è il tuo **chat_id**.

## 2. Metti il progetto su GitHub

1. Crea un repository **pubblico** (Actions è gratis sui repo pubblici).
2. Carica tutti questi file.

## 3. Aggiungi i Secrets

Nel repo: **Settings → Secrets and variables → Actions → New repository secret**.
Crea due secret:

| Nome               | Valore                    |
|--------------------|---------------------------|
| `TELEGRAM_TOKEN`   | il token di BotFather     |
| `TELEGRAM_CHAT_ID` | il tuo chat_id            |

## 4. Provalo subito

Vai nella scheda **Actions → Allerta vento → Run workflow** per un avvio
manuale. Controlla il log: vedrai i valori letti. Se in quel momento il vento
è sopra i 10 nodi (e sei in orario) ti arriva il messaggio.

---

## Personalizzazioni

Tutto in cima a [`meteo_check.py`](meteo_check.py):

- `SOGLIA_NODI` — la soglia di avviso (default 10).
- `ORA_INIZIO` / `ORA_FINE` — fascia oraria degli avvisi.
- `STAZIONI` — elenco delle stazioni. Per **aggiungere una stazione a nord**
  (per i venti da nord) basta aggiungere un blocco:

  ```python
  {
      "nome": "Nome stazione nord",
      "url": "https://...",
      "direzioni": ["N", "NNE", "NE", "NNW"],  # avvisa solo da nord
  },
  ```

  Il campo `direzioni` è opzionale: `None` = avvisa per qualsiasi direzione.

## Note / limiti

- Il cron di GitHub **non è preciso**: può ritardare di qualche minuto.
- I workflow schedulati vengono **disattivati dopo 60 giorni** di inattività
  del repo: questo workflow committa `state.json` quando il vento cambia
  stato, il che aiuta a tenerlo attivo; in mancanza di vento per molto tempo,
  fai un commit ogni tanto o riattivalo dalla scheda Actions.
- I dati vengono letti dall'HTML del sito: se cambiano la grafica, va
  aggiornata la parte di parsing in `leggi_stazione()`.
