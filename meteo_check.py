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

# Livelli di avviso sul VENTO ATTUALE, dal piu' basso al piu' alto.
#   soglia       -> nodi oltre i quali scatta il livello
#   riarmo       -> nodi sotto cui il livello si "disarma" (isteresi: evita
#                   avvisi ripetuti se il vento oscilla attorno alla soglia)
#   intestazione -> testo speciale premesso ai dati (None = avviso normale)
LIVELLI = [
    {
        "soglia": 8.0,
        "riarmo": 7.0,
        "intestazione": None,
    },
    {
        "soglia": 20.0,
        "riarmo": 19.0,
        "intestazione": (
            "⚠️ *ALERT VENTO !!!*\n"
            "_Vento sostenuto: condizioni impegnative, adatte solo a chi ha "
            "esperienza. Valutate bene prima di uscire._"
        ),
    },
    {
        "soglia": 30.0,
        "riarmo": 29.0,
        "intestazione": (
            "🛑 *ALERT VENTO !!!*\n"
            "_Vento molto forte: si sconsiglia di uscire in acqua. Pericoloso "
            "anche per i piu' esperti._"
        ),
    },
]

# Livelli di avviso sulla RAFFICA. ATTENZIONE: le stazioni espongono solo la
# raffica MASSIMA della giornata (non la raffica istantanea), quindi l'avviso
# scatta la prima volta che il picco di giornata supera ciascuna soglia (poi si
# ri-arma quando il dato si azzera a mezzanotte).
RAFFICA_LIVELLI = [
    {"soglia": 15.0, "riarmo": 14.0},
    {"soglia": 20.0, "riarmo": 19.0},
    {"soglia": 25.0, "riarmo": 24.0},
    {"soglia": 30.0, "riarmo": 29.0},
]

# Fascia oraria in cui inviare gli avvisi (ora locale italiana, 24h).
ORA_INIZIO = 9
ORA_FINE = 19

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
        # Semicerchio sud: venti da E, SE, S, SW, O (e settori intermedi).
        "direzioni": ["E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W"],
    },
    {
        "nome": "Lido di Volano",
        "url": "http://dkwa.it/meteo/",
        "tipo": "saratoga",
        # Semicerchio nord: venti da O, NW, N, NE, E (e settori intermedi).
        "direzioni": ["W", "WNW", "NW", "NNW", "N", "NNE", "NE", "ENE", "E"],
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


def calcola_livello(valore: float, livello_attuale: int, livelli: list) -> int:
    """Calcola il livello (0 = sotto soglia, 1..N) con isteresi.

    Partendo dal livello attuale: prima scende finche' il valore e' sotto la
    soglia di riarmo, poi sale finche' il valore supera le soglie successive.
    Vale sia per il vento (LIVELLI) sia per la raffica (RAFFICA_LIVELLI).
    """
    livello = livello_attuale
    # Discesa: scendo di livello solo se il valore e' sotto il riarmo.
    while livello > 0 and valore < livelli[livello - 1]["riarmo"]:
        livello -= 1
    # Salita: salgo di livello se il valore supera la soglia successiva.
    while livello < len(livelli) and valore >= livelli[livello]["soglia"]:
        livello += 1
    return livello


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main() -> int:
    # Modalita' annuncio: pubblica sul canale il contenuto di annuncio.md e
    # termina. Usata dal workflow annuncio.yml quando il file viene aggiornato.
    if os.environ.get("INVIA_ANNUNCIO", "").lower() in ("1", "true", "yes"):
        testo = Path(__file__).with_name("annuncio.md").read_text(
            encoding="utf-8").strip()
        if not testo:
            print("[info] annuncio.md vuoto: nessun invio.")
            return 0
        try:
            invia_telegram(testo)
        except Exception as e:  # noqa: BLE001
            print(f"[errore] invio annuncio fallito: {e}")
            return 1
        return 0

    # Modalita' test: legge i dati attuali di tutte le stazioni e li invia
    # (anche sotto soglia), poi termina. Utile per verificare che funzioni.
    if os.environ.get("TEST_TELEGRAM", "").lower() in ("1", "true", "yes"):
        righe = ["🧪 *Test allerta vento — dati attuali*"]
        for st in STAZIONI:
            dati = leggi_stazione(st)
            if dati is None:
                righe.append(f"\n*{st['nome']}*: dati non disponibili")
                continue
            raffica = dati["raffica"]
            raffica_txt = (f" — raffica {raffica:.1f} nodi"
                           if raffica is not None else "")
            righe.append(
                f"\n🌬️ *{st['nome']}*\n"
                f"Vento {dati['vento']:.1f} nodi da {dati['direzione']}"
                f"{raffica_txt}"
            )
        try:
            invia_telegram("\n".join(righe))
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

        livello_prima = stato.get(nome, {}).get("livello", 0)
        livello_ora = calcola_livello(vento, livello_prima, LIVELLI)

        raf_prima = stato.get(nome, {}).get("livello_raffica", 0)
        raf_ora = (calcola_livello(raffica, raf_prima, RAFFICA_LIVELLI)
                   if raffica is not None else raf_prima)

        print(f"[{nome}] vento {vento} kts {direzione} raffica {raffica} kts "
              f"(vento liv {livello_prima}->{livello_ora}, "
              f"raffica liv {raf_prima}->{raf_ora}, orario={in_orario})")

        if livello_ora != livello_prima:
            stato.setdefault(nome, {})["livello"] = livello_ora
            cambiato = True
        if raf_ora != raf_prima:
            stato.setdefault(nome, {})["livello_raffica"] = raf_ora
            cambiato = True

        # --- Avviso VENTO: solo quando il livello SALE (e direzione OK) ---
        if livello_ora > livello_prima:
            direzioni_ok = (st["direzioni"] is None
                            or direzione in st["direzioni"])

            if in_orario and direzioni_ok:
                intestazione = LIVELLI[livello_ora - 1]["intestazione"]
                raffica_txt = (f" — raffica *{raffica:.1f} nodi*"
                               if raffica is not None else "")
                corpo = (f"🌬️ *{nome}*\n"
                         f"Vento *{vento:.1f} nodi* da {direzione}"
                         f"{raffica_txt}")
                testo = f"{intestazione}\n\n{corpo}" if intestazione else corpo
                try:
                    invia_telegram(testo)
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] invio Telegram fallito: {e}")
            else:
                motivo = "fuori orario" if not in_orario else "direzione esclusa"
                print(f"[info] superamento vento ma avviso non inviato "
                      f"({motivo})")

        # --- Avviso RAFFICA: quando il picco di giornata sale di soglia ---
        if raf_ora > raf_prima:
            if in_orario:
                soglia = RAFFICA_LIVELLI[raf_ora - 1]["soglia"]
                testo = (f"🌀 *ALERT RAFFICA — {nome}*\n"
                         f"Oggi la raffica ha raggiunto *{raffica:.1f} nodi* "
                         f"(soglia {soglia:.0f}).")
                try:
                    invia_telegram(testo)
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] invio Telegram raffica fallito: {e}")
            else:
                print("[info] soglia raffica superata ma fuori orario")

    if cambiato:
        salva_stato(stato)

    return 0


if __name__ == "__main__":
    sys.exit(main())
