#!/usr/bin/env python3
"""
Allerta vento via Telegram.

Controlla i dati di una o piu' stazioni meteo (web scraping) e invia un
messaggio Telegram quando il vento medio supera una soglia.

Logica "solo al superamento": l'avviso parte quando il vento SALE sopra la
soglia; non viene ripetuto finche' il vento non riscende sotto e poi risale.
Lo stato e' salvato in state.json (committato dal workflow GitHub Actions).

Variabili d'ambiente richieste:
    TELEGRAM_TOKEN    token del bot (da @BotFather)
    TELEGRAM_CHAT_ID  id della chat a cui scrivere
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# --------------------------------------------------------------------------
# CONFIGURAZIONE
# --------------------------------------------------------------------------

# Soglia in nodi sul vento medio/attuale.
SOGLIA_NODI = 10.0

# Isteresi: lo stato si "riarma" (pronto a un nuovo avviso) solo quando il
# vento riscende sotto questo valore. Evita avvisi ripetuti se il vento
# oscilla attorno alla soglia.
SOGLIA_RIARMO = 9.0

# Fascia oraria in cui inviare gli avvisi (ora locale italiana, 24h).
ORA_INIZIO = 7
ORA_FINE = 21

# Fuso orario per il calcolo della fascia oraria.
TZ = ZoneInfo("Europe/Rome")

# Elenco delle stazioni da controllare.
# Per aggiungere una stazione a nord in futuro basta aggiungere un dict qui.
#   nome       -> etichetta mostrata nel messaggio
#   url        -> pagina da scaricare
#   direzioni  -> None = avvisa per qualsiasi direzione;
#                 oppure lista di settori (es. ["S", "SSW", "SW"]) per
#                 avvisare solo quando il vento arriva da quelle direzioni.
# Campo "tipo": indica quale lettore usare per quella pagina
#   "meteosystem" -> pagine Meteosystem/WeatherLink (es. Porto Corsini)
#   "saratoga"    -> template Saratoga/Meteobridge (es. Lido di Volano)
STAZIONI = [
    {
        "nome": "Porto Corsini",
        "url": "http://www.meteosystem.com/wlip/awc/",
        "tipo": "meteosystem",
        "direzioni": None,            # avvisa per qualsiasi direzione
    },
    {
        "nome": "Lido di Volano",
        "url": "http://dkwa.it/meteo/",
        "tipo": "saratoga",
        # Stazione a nord: avvisa solo per i venti da nord (Tramontana/Bora).
        "direzioni": ["N", "NNE", "NE", "ENE", "NNW", "NW"],
    },
]

STATE_FILE = Path(__file__).with_name("state.json")


# --------------------------------------------------------------------------
# PARSING
# --------------------------------------------------------------------------

def _solo_testo(html: str) -> str:
    """Rimuove i tag HTML e normalizza gli spazi."""
    testo = re.sub(r"<[^>]+>", " ", html)
    testo = (testo.replace("&nbsp;", " ")
                  .replace("&deg;", " ")
                  .replace("&agrave;", "a"))
    return re.sub(r"\s+", " ", testo)


def _num(s: str) -> float:
    """Converte un numero che puo' usare la virgola decimale."""
    return float(s.replace(",", "."))


def _parse_meteosystem(html: str) -> dict | None:
    """Pagine Meteosystem/WeatherLink, es. 'Velocita' attuale: 5.2 kts SSW'."""
    testo = _solo_testo(html)
    m_vento = re.search(
        r"attuale[:\s]*([\d.,]+)\s*kts?\s*([NSEWnsew]{1,3})",
        testo, re.IGNORECASE,
    )
    # "raffica ... 13.0 kts"  (raffica massima giornaliera)
    m_raffica = re.search(r"raffica[^0-9]{0,40}?([\d.,]+)\s*kts?",
                          testo, re.IGNORECASE)
    if not m_vento:
        return None
    return {
        "vento": _num(m_vento.group(1)),
        "direzione": m_vento.group(2).upper(),
        "raffica": _num(m_raffica.group(1)) if m_raffica else None,
    }


def _parse_saratoga(html: str) -> dict | None:
    """Template Saratoga/Meteobridge, es. testo 'S 4.7 Raffica: 5.4 kts'."""
    testo = _solo_testo(html)
    # velocita' attuale: il numero subito prima della parola "Raffica"
    m_vento = re.search(r"([\d.,]+)\s*Raffica", testo, re.IGNORECASE)
    # raffica: il numero subito dopo "Raffica:"
    m_raffica = re.search(r"Raffica:?\s*([\d.,]+)", testo, re.IGNORECASE)
    # direzione: dal nome dell'immagine della rosa dei venti (es. wr-it-S.png)
    m_dir = re.search(r"wr-it-([NSEW]{1,3})\.png", html, re.IGNORECASE)
    if not m_vento:
        return None
    return {
        "vento": _num(m_vento.group(1)),
        "direzione": m_dir.group(1).upper() if m_dir else "?",
        "raffica": _num(m_raffica.group(1)) if m_raffica else None,
    }


PARSER = {
    "meteosystem": _parse_meteosystem,
    "saratoga": _parse_saratoga,
}


def leggi_stazione(st: dict) -> dict | None:
    """Scarica la pagina della stazione ed estrae vento, direzione, raffica.

    Ritorna {vento, direzione, raffica} oppure None se il download o il
    parsing falliscono (es. il sito ha cambiato formato).
    """
    url = st["url"]
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[errore] download fallito da {url}: {e}")
        return None

    parser = PARSER[st.get("tipo", "meteosystem")]
    dati = parser(r.text)
    if dati is None:
        print(f"[errore] impossibile leggere il vento da {url}")
    return dati


# --------------------------------------------------------------------------
# TELEGRAM
# --------------------------------------------------------------------------

def invia_telegram(testo: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown"},
        timeout=30,
    )
    r.raise_for_status()
    print("[ok] messaggio Telegram inviato")


# --------------------------------------------------------------------------
# STATO
# --------------------------------------------------------------------------

def carica_stato() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def salva_stato(stato: dict) -> None:
    STATE_FILE.write_text(json.dumps(stato, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main() -> int:
    # Modalita' test: invia un messaggio di prova e termina.
    if os.environ.get("TEST_TELEGRAM", "").lower() in ("1", "true", "yes"):
        try:
            invia_telegram("✅ Test allerta vento: il bot funziona!")
        except Exception as e:  # noqa: BLE001
            print(f"[errore] invio Telegram di test fallito: {e}")
            return 1
        return 0

    adesso = datetime.now(TZ)
    in_orario = ORA_INIZIO <= adesso.hour < ORA_FINE

    stato = carica_stato()
    cambiato = False

    for st in STAZIONI:
        nome = st["nome"]
        dati = leggi_stazione(st)
        if dati is None:
            continue  # non tocco lo stato se non riesco a leggere

        vento = dati["vento"]
        direzione = dati["direzione"]
        raffica = dati["raffica"]
        print(f"[{nome}] vento {vento} kts {direzione} "
              f"raffica {raffica} kts (orario={in_orario})")

        era_sopra = stato.get(nome, {}).get("sopra", False)

        # Riarmo quando il vento riscende sotto la soglia di isteresi.
        if vento < SOGLIA_RIARMO and era_sopra:
            stato.setdefault(nome, {})["sopra"] = False
            cambiato = True
            era_sopra = False

        # Superamento: vento sopra soglia e prima eravamo sotto.
        if vento > SOGLIA_NODI and not era_sopra:
            stato.setdefault(nome, {})["sopra"] = True
            cambiato = True

            direzioni_ok = (st["direzioni"] is None
                            or direzione in st["direzioni"])

            if in_orario and direzioni_ok:
                raffica_txt = (f" — raffica *{raffica:.1f} nodi*"
                               if raffica is not None else "")
                testo = (f"🌬️ *{nome}*\n"
                         f"Vento *{vento:.1f} nodi* da {direzione}"
                         f"{raffica_txt}")
                try:
                    invia_telegram(testo)
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] invio Telegram fallito: {e}")
            else:
                motivo = "fuori orario" if not in_orario else "direzione esclusa"
                print(f"[info] superamento rilevato ma avviso non inviato "
                      f"({motivo})")

    if cambiato:
        salva_stato(stato)

    return 0


if __name__ == "__main__":
    sys.exit(main())
