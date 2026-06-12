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
import math
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

# Livelli di avviso sulla CADUTA di pressione, normalizzata a 3 ore (hPa).
# La tendenza barometrica si misura sullo standard delle 3 ore: un calo di
# 3 hPa/3h mette l'equipaggio in allerta, oltre i 6 hPa/3h e' un calo "molto
# rapido" -> peggioramento marcato / possibile groppo. Stessa isteresi del
# vento (riarmo poco sotto la soglia) per non ripetere l'avviso.
PRESSIONE_LIVELLI = [
    {"soglia": 3.0, "riarmo": 2.0},
    {"soglia": 6.0, "riarmo": 5.0},
]

# Finestra per la tendenza di pressione (minuti):
#   FINESTRA  -> quanto storico di letture teniamo in state.json
#   MIN_SPAN  -> baseline minima necessaria per poter valutare la tendenza
PRESS_FINESTRA_MIN = 195
PRESS_MIN_SPAN_MIN = 150

# Fascia oraria in cui inviare gli avvisi (ora locale italiana, 24h).
ORA_INIZIO = 9
ORA_FINE = 19

# Fuso orario per il calcolo della fascia oraria.
TZ = ZoneInfo("Europe/Rome")

# Posizione del circolo (Lido di Spina, Comacchio), riferimento per stimare
# tra quanto il rinforzo di vento puo' raggiungere il circolo.
CIRCOLO = (44.665, 12.231)  # (lat, lon) approssimati

# Elenco delle stazioni da controllare.
# Per aggiungere una stazione a nord in futuro basta aggiungere un dict qui.
#   nome       -> etichetta mostrata nel messaggio
#   url        -> pagina da scaricare
#   coord      -> (lat, lon) della stazione, per la stima del tempo di arrivo
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
        "coord": (44.493, 12.279),    # a sud del circolo (~20 km)
        # Semicerchio sud: venti da E, SE, S, SW, O (e settori intermedi).
        "direzioni": ["E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W"],
    },
    {
        "nome": "Lido di Volano",
        "url": "http://dkwa.it/meteo/",
        "tipo": "saratoga",
        "coord": (44.797, 12.268),    # a nord del circolo (~15 km)
        # Semicerchio nord: venti da O, NW, N, NE, E (e settori intermedi).
        "direzioni": ["W", "WNW", "NW", "NNW", "N", "NNE", "NE", "ENE", "E"],
    },
]

# Direzioni della bussola (16 punte) in gradi, per la stima del tempo di arrivo.
COMPASS = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90, "ESE": 112.5,
    "SE": 135, "SSE": 157.5, "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
    "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}

# Nomi italiani di giorni e mesi: li costruiamo a mano perche' sui runner di
# GitHub il locale it_IT spesso non e' installato e strftime darebbe i nomi in
# inglese.
GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
             "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_estesa(dt: datetime) -> str:
    """Data in italiano senza anno, es. 'mercoledì 10 giugno'."""
    return f"{GIORNI_IT[dt.weekday()]} {dt.day} {MESI_IT[dt.month - 1]}"


STATE_FILE = Path(__file__).with_name("state.json")


# --------------------------------------------------------------------------
# STIMA TEMPO DI ARRIVO AL CIRCOLO
# --------------------------------------------------------------------------

def _dist_bearing(lat1: float, lon1: float,
                  lat2: float, lon2: float) -> tuple[float, float]:
    """Distanza (km) e rotta iniziale (gradi) dal punto 1 al punto 2."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    dist = 2 * r * math.asin(math.sqrt(a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brg = (math.degrees(math.atan2(y, x)) + 360) % 360
    return dist, brg


def stima_arrivo_min(coord, direzione: str, vento: float):
    """Stima in minuti quanto impiega il rinforzo ad arrivare al circolo.

    Il rinforzo viaggia con il vento: si proietta la velocita' del vento
    sulla direzione stazione->circolo. Se il vento non punta verso il circolo
    (angolo troppo ampio) ritorna None: in quel caso non ha senso una stima.
    """
    if not coord or direzione not in COMPASS or vento <= 0:
        return None
    dist, brg_circolo = _dist_bearing(coord[0], coord[1],
                                      CIRCOLO[0], CIRCOLO[1])
    # Direzione verso cui si sposta l'aria (opposta a quella di provenienza).
    rotta_aria = (COMPASS[direzione] + 180) % 360
    diff = abs((rotta_aria - brg_circolo + 180) % 360 - 180)  # 0..180
    if diff > 45:             # vento non abbastanza diretto verso il circolo
        return None
    componente = vento * math.cos(math.radians(diff))  # nodi utili
    if componente <= 0:
        return None
    return dist / (componente * 1.852) * 60  # km / (nodi->km/h) -> minuti


# Frecce (8 punte) per le 8 direzioni della bussola.
_FRECCE = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]  # N NE E SE S SW W NW


def freccia(direzione: str) -> str:
    """Freccia che punta verso DOVE soffia il vento (vuota se sconosciuta).

    Il vento si muove verso la direzione opposta a quella di provenienza:
    es. 'da SE' -> soffia verso NW -> ↖️.
    """
    if direzione not in COMPASS:
        return ""
    rotta = (COMPASS[direzione] + 180) % 360
    return _FRECCE[int((rotta + 22.5) // 45) % 8]


_COMPASS16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _dir16(gradi: float) -> str:
    """Converte i gradi nella sigla a 16 punte (es. 135 -> SE)."""
    return _COMPASS16[int((gradi + 11.25) // 22.5) % 16]


def bollettino_mattutino():
    """Previsione vento del giorno per il circolo (Open-Meteo). None se fallisce."""
    lat, lon = CIRCOLO
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&hourly=wind_speed_10m,wind_gusts_10m,wind_direction_10m"
           "&wind_speed_unit=kn&timezone=Europe/Rome&forecast_days=1")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        h = r.json()["hourly"]
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"[errore] bollettino non disponibile: {e}")
        return None

    ore, ws, wg, wd = (h["time"], h["wind_speed_10m"],
                       h["wind_gusts_10m"], h["wind_direction_10m"])
    righe = ["🌅 *Bollettino di oggi — Lido di Spina*",
             f"_{data_estesa(datetime.now(TZ))}_",
             "Previsione vento (Open-Meteo):", ""]
    vmax = gmax = 0.0
    ora_vmax = None
    for i, t in enumerate(ore):
        ora = int(t[11:13])
        if ORA_INIZIO <= ora < ORA_FINE:
            if ws[i] > vmax:
                vmax, ora_vmax = ws[i], ora
            gmax = max(gmax, wg[i])
        if ora in (9, 12, 15, 18):
            righe.append(f"• {t[11:16]} — {ws[i]:.0f} nodi {_dir16(wd[i])}, "
                         f"raffiche {wg[i]:.0f}")
    righe.append("")
    if ora_vmax is not None:
        righe.append(f"Max previsto: ~{vmax:.0f} nodi (raffiche fino a "
                     f"{gmax:.0f}) verso le {ora_vmax}:00.")
    righe.append("ℹ️ Previsione indicativa, non sostituisce gli avvisi reali.")
    return "\n".join(righe)


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
    # "Pressione: 1016.9 hPa"
    m_press = re.search(r"Pressione[:\s]*([\d.,]+)\s*hPa", testo, re.IGNORECASE)
    if not m_vento:
        return None
    return {
        "vento": _num(m_vento.group(1)),
        "direzione": m_vento.group(2).upper(),
        "raffica": _num(m_raffica.group(1)) if m_raffica else None,
        "pressione": _num(m_press.group(1)) if m_press else None,
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
    # "Barometro: 1016.6 hPa"
    m_press = re.search(r"Barometro[:\s]*([\d.,]+)\s*hPa", testo, re.IGNORECASE)
    if not m_vento:
        return None
    return {
        "vento": _num(m_vento.group(1)),
        "direzione": m_dir.group(1).upper() if m_dir else "?",
        "raffica": _num(m_raffica.group(1)) if m_raffica else None,
        "pressione": _num(m_press.group(1)) if m_press else None,
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
# CONTROLLO PRESSIONE (workflow separato, sfasato rispetto al vento)
# --------------------------------------------------------------------------

def _eta_min(iso: str, ora: datetime) -> float:
    """Eta' in minuti di una lettura (timestamp ISO) rispetto a `ora`."""
    return (ora - datetime.fromisoformat(iso)).total_seconds() / 60.0


def controlla_pressione(stato: dict) -> bool:
    """Legge la pressione delle stazioni, aggiorna lo storico e avvisa.

    Tiene in state.json una finestra di letture per stazione, calcola la caduta
    di pressione normalizzata a 3 ore e, al superamento delle soglie, invia un
    avviso Telegram (solo in fascia oraria). Ritorna True se lo stato e'
    cambiato (e va quindi salvato).
    """
    adesso = datetime.now(TZ)
    in_orario = ORA_INIZIO <= adesso.hour < ORA_FINE
    cambiato = False

    for st in STAZIONI:
        nome = st["nome"]
        dati = leggi_stazione(st)
        if dati is None or dati.get("pressione") is None:
            print(f"[{nome}] pressione non disponibile")
            continue

        p = dati["pressione"]
        s = stato.setdefault(nome, {})

        # Aggiungo la lettura corrente e poto quelle fuori finestra.
        storia = s.get("pressioni", [])
        storia.append([adesso.isoformat(), p])
        storia = [e for e in storia if _eta_min(e[0], adesso) <= PRESS_FINESTRA_MIN]
        s["pressioni"] = storia
        cambiato = True

        # Baseline = lettura piu' vecchia rimasta nella finestra.
        span = _eta_min(storia[0][0], adesso)
        if span < PRESS_MIN_SPAN_MIN:
            print(f"[{nome}] pressione {p:.1f} hPa, storico insufficiente "
                  f"({span:.0f} min)")
            continue

        # Caduta normalizzata a 3 ore (positiva se la pressione SCENDE).
        caduta = (storia[0][1] - p) * 180.0 / span
        liv_prima = s.get("livello_pressione", 0)
        liv_ora = calcola_livello(max(0.0, caduta), liv_prima, PRESSIONE_LIVELLI)

        print(f"[{nome}] pressione {p:.1f} hPa, caduta ~{caduta:.1f} hPa/3h "
              f"(liv {liv_prima}->{liv_ora}, span {span:.0f} min, "
              f"orario={in_orario})")

        if liv_ora != liv_prima:
            s["livello_pressione"] = liv_ora
            cambiato = True

        # Avviso solo quando il livello SALE (e in fascia oraria).
        if liv_ora > liv_prima:
            if not in_orario:
                print(f"[info] caduta pressione ma fuori orario ({nome})")
                continue
            if liv_ora >= 2:
                testo = (f"🔴 *ALERT PRESSIONE — {nome}*\n"
                         f"Pressione *{p:.1f} hPa*, in calo di "
                         f"~*{caduta:.1f} hPa* nelle ultime 3 ore.\n"
                         f"_Calo marcato: possibile peggioramento o groppo in "
                         f"arrivo, prudenza in acqua._")
            else:
                testo = (f"🟡 *Pressione in calo — {nome}*\n"
                         f"Pressione *{p:.1f} hPa*, scesa di "
                         f"~*{caduta:.1f} hPa* nelle ultime 3 ore.\n"
                         f"_Probabile rinforzo di vento in arrivo._")
            try:
                invia_telegram(testo)
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio alert pressione fallito: {e}")

    return cambiato


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main() -> int:
    # Modalita' pressione: gira sul workflow dedicato (sfasato dal vento) e
    # controlla solo la tendenza barometrica, poi termina.
    if os.environ.get("MODO_PRESSIONE", "").lower() in ("1", "true", "yes"):
        stato = carica_stato()
        if controlla_pressione(stato):
            salva_stato(stato)
        return 0

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
    oggi = adesso.strftime("%Y-%m-%d")
    in_orario = ORA_INIZIO <= adesso.hour < ORA_FINE

    stato = carica_stato()
    cambiato = False

    # Reset giornaliero di massimi e tendenza all'inizio di un nuovo giorno.
    if stato.get("_data") != oggi:
        stato["_data"] = oggi
        for st in STAZIONI:
            s = stato.setdefault(st["nome"], {})
            s["vento_max"] = 0.0
            s["raffica_max"] = 0.0
            s.pop("vento_prec", None)
        cambiato = True

    # --- Bollettino mattutino: una volta al giorno, in mattinata ---
    # Esce TUTTI i giorni (giovedi' compreso): il grafico previsioni weekend
    # (grafico_settimanale.py, gio-ven-sab alle 9:05) ora mostra solo i giorni
    # FUTURI, quindi non duplica piu' il giorno di oggi.
    if (stato.get("_bollettino") != oggi
            and ORA_INIZIO <= adesso.hour < ORA_INIZIO + 3):
        msg = bollettino_mattutino()
        if msg:
            try:
                invia_telegram(msg)
                stato["_bollettino"] = oggi
                cambiato = True
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio bollettino fallito: {e}")

    for st in STAZIONI:
        nome = st["nome"]
        dati = leggi_stazione(st)
        if dati is None:
            continue  # non tocco lo stato se non riesco a leggere

        vento = dati["vento"]
        direzione = dati["direzione"]
        raffica = dati["raffica"]
        s = stato.setdefault(nome, {})

        livello_prima = s.get("livello", 0)
        livello_ora = calcola_livello(vento, livello_prima, LIVELLI)

        raf_prima = s.get("livello_raffica", 0)
        raf_ora = (calcola_livello(raffica, raf_prima, RAFFICA_LIVELLI)
                   if raffica is not None else raf_prima)

        # Tendenza rispetto alla lettura precedente (solo in orario attivo).
        vento_prec = s.get("vento_prec")
        tendenza = None
        if in_orario and vento_prec is not None:
            delta = vento - vento_prec
            tendenza = ("📈 in aumento" if delta >= 1
                        else "📉 in calo" if delta <= -1
                        else "➖ stabile")

        print(f"[{nome}] vento {vento} kts {direzione} raffica {raffica} kts "
              f"(vento liv {livello_prima}->{livello_ora}, "
              f"raffica liv {raf_prima}->{raf_ora}, orario={in_orario})")

        if livello_ora != livello_prima:
            s["livello"] = livello_ora
            cambiato = True
        if raf_ora != raf_prima:
            s["livello_raffica"] = raf_ora
            cambiato = True

        # Aggiorna tendenza e massimi giornalieri (solo in orario attivo).
        if in_orario:
            s["vento_prec"] = vento
            s["vento_max"] = max(s.get("vento_max", 0.0), vento)
            if raffica is not None:
                s["raffica_max"] = max(s.get("raffica_max", 0.0), raffica)
            cambiato = True

        # --- Avviso VENTO: solo quando il livello SALE (e direzione OK) ---
        if livello_ora > livello_prima:
            direzioni_ok = (st["direzioni"] is None
                            or direzione in st["direzioni"])

            if in_orario and direzioni_ok:
                intestazione = LIVELLI[livello_ora - 1]["intestazione"]
                dir_txt = f"{direzione} {freccia(direzione)}".strip()
                raffica_txt = (f" — raffica *{raffica:.1f} nodi*"
                               if raffica is not None else "")
                corpo = (f"🌬️ *{nome}*\n"
                         f"Vento *{vento:.1f} nodi* da {dir_txt}"
                         f"{raffica_txt}")
                if tendenza:
                    corpo += f"\n{tendenza}"
                # Stima di quando il rinforzo potrebbe arrivare al circolo.
                eta = stima_arrivo_min(st.get("coord"), direzione, vento)
                if eta is not None:
                    minuti = max(5, int(round(eta / 5.0) * 5))
                    corpo += (f"\n⏱️ Possibile arrivo al circolo tra "
                              f"~{minuti} min")
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

    # --- Riepilogo giornaliero: una volta sola, a fine fascia oraria ---
    if adesso.hour >= ORA_FINE and stato.get("_riepilogo") != oggi:
        righe = ["📊 *Riepilogo di oggi*", f"_{data_estesa(adesso)}_"]
        almeno_uno = False
        for st in STAZIONI:
            s = stato.get(st["nome"], {})
            vmax = s.get("vento_max", 0.0)
            rmax = s.get("raffica_max", 0.0)
            if vmax <= 0 and rmax <= 0:
                continue
            almeno_uno = True
            rtxt = f"{rmax:.1f} nodi" if rmax > 0 else "n.d."
            righe.append(f"🌬️ *{st['nome']}*: vento max *{vmax:.1f} nodi*, "
                         f"raffica max *{rtxt}*")
        if almeno_uno:
            righe.append("⛵ Buona serata!")
            try:
                invia_telegram("\n".join(righe))
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio riepilogo fallito: {e}")
        stato["_riepilogo"] = oggi
        cambiato = True

    if cambiato:
        salva_stato(stato)

    return 0


if __name__ == "__main__":
    sys.exit(main())
