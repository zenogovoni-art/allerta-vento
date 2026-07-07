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
#   soglia      -> nodi oltre i quali scatta il livello
#   riarmo      -> nodi sotto cui il livello si "disarma" (isteresi: evita
#                  avvisi ripetuti se il vento oscilla attorno alla soglia)
#   tag         -> etichetta breve con emoji di gravita' (usata nel bollettino
#                  "Situazione vento" quando l'avviso vi confluisce)
#   descrizione -> frase estesa mostrata nell'ALERT VENTO a se' stante
# Il titolo della scheda ("🌬️ ALERT VENTO — Stazione") e' aggiunto dal codice,
# uguale per tutti i livelli: cosi' l'avviso e' riconoscibile a colpo d'occhio e
# distinto dalla "Situazione vento" informativa delle ogni mezz'ora.
LIVELLI = [
    {
        "soglia": 8.0,
        "riarmo": 7.0,
        "tag": "🟢 *8+ nodi*",
        "descrizione": "_Prime arie: si comincia a navigare._",
    },
    {
        "soglia": 10.0,
        "riarmo": 9.0,
        "tag": "🟢 *10+ nodi*",
        "descrizione": "_Bella arietta da planata._",
    },
    {
        "soglia": 15.0,
        "riarmo": 14.0,
        "tag": "💨 *15+ nodi*",
        "descrizione": "_Vento teso: divertente ma impegnativo._",
    },
    {
        "soglia": 20.0,
        "riarmo": 19.0,
        "tag": "⚠️ *20+ nodi*",
        "descrizione": ("_Vento sostenuto: condizioni impegnative, adatte solo "
                        "a chi ha esperienza. Valutate bene prima di uscire._"),
    },
    {
        "soglia": 30.0,
        "riarmo": 29.0,
        "tag": "🛑 *30+ nodi*",
        "descrizione": ("_Vento molto forte: si sconsiglia di uscire in acqua. "
                        "Pericoloso anche per i piu' esperti._"),
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

# Punto al largo di Lido di Spina per i dati marini (Open-Meteo Marine): il
# circolo e' praticamente sulla costa/valle, serve un punto in mare aperto
# perche' il modello oceanico restituisca correnti e livello del mare validi.
PUNTO_MARE = (44.665, 12.35)  # (lat, lon) ~9 km al largo del circolo

# Bollettino periodico "situazione stazioni": pubblicato una volta ogni mezz'ora
# (slot :00-:29 e :30-:59) nella fascia oraria attiva, SEMPRE, anche se i dati
# non sono cambiati. Il vento in tempo reale interessa ai soci del circolo.

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

    # Correnti di superficie e maree di oggi (Open-Meteo Marine, best effort).
    mare = dati_marini()
    if mare:
        righe.append("")
        c = mare.get("corrente")
        if c and c.get("dir") is not None:
            vtxt = (f" (~{c['vel']:.1f} km/h)"
                    if c.get("vel") is not None else "")
            righe.append(f"🌊 *Corrente di superficie*: verso "
                         f"{_dir16(c['dir'])}{vtxt}")
        maree = mare.get("maree") or []
        if maree:
            righe.append("🌊 *Maree di oggi*:")
            for tipo, ora_hhmm, alt in maree:
                icona = "🔺" if tipo == "alta" else "🔻"
                cm = round(alt * 100)
                segno = "+" if cm >= 0 else "−"
                righe.append(f"  {icona} {tipo.capitalize()} marea "
                             f"{ora_hhmm} — {segno}{abs(cm)} cm")
            alte = [alt for tipo, _, alt in maree if tipo == "alta"]
            basse = [alt for tipo, _, alt in maree if tipo == "bassa"]
            if alte and basse:
                esc = round((max(alte) - min(basse)) * 100)
                righe.append(f"  ↕️ Escursione della giornata: {esc} cm")
            righe.append("  _I cm dicono quanto il mare sale (+) o "
                         "scende (−) rispetto al livello medio di oggi._")

    emoji_luna, fase_luna = fase_lunare()
    righe.append("")
    righe.append(f"{emoji_luna} *Luna*: {fase_luna}")

    righe.append("ℹ️ Previsione indicativa, non sostituisce gli avvisi reali.")
    return "\n".join(righe)


def fase_lunare(quando=None):
    """Fase lunare stimata dal ciclo sinodico medio (~29.53 giorni).

    Ritorna (emoji, testo), es. ("🌔", "crescente — piena tra 3 giorni").
    L'approssimazione (mezza giornata circa) basta per crescente/calante.
    """
    if quando is None:
        quando = datetime.now(TZ)
    luna_nuova_rif = datetime(2000, 1, 6, 18, 14, tzinfo=ZoneInfo("UTC"))
    ciclo = 29.530588853
    eta = ((quando - luna_nuova_rif).total_seconds() / 86400.0) % ciclo

    emoji = "🌑🌒🌓🌔🌕🌖🌗🌘"[round(eta / ciclo * 8) % 8]
    if eta < 1.0 or eta > ciclo - 1.0:
        testo = "nuova"
    elif abs(eta - ciclo / 2) < 1.0:
        testo = "piena"
    elif eta < ciclo / 2:
        giorni = max(1, round(ciclo / 2 - eta))
        quando_txt = "domani" if giorni == 1 else f"tra {giorni} giorni"
        testo = f"crescente — piena {quando_txt}"
    else:
        giorni = max(1, round(ciclo - eta))
        quando_txt = "domani" if giorni == 1 else f"tra {giorni} giorni"
        testo = f"calante — nuova {quando_txt}"
    return emoji, testo


def dati_marini():
    """Corrente di superficie e maree di oggi al largo di Lido di Spina.

    Usa la Marine API di Open-Meteo (modello oceanico SMOC). Ritorna un dict
    {"corrente": {"dir": gradi, "vel": km/h}|None,
     "maree": [(tipo, "HH:MM", altezza_m), ...]}
    oppure None se la richiesta fallisce. La direzione della corrente segue la
    convenzione oceanografica (verso CUI scorre). Le altezze di marea sono
    riferite al livello medio della giornata (calcolato dalla serie oraria),
    non allo zero del modello: cosi' l'alta marea risulta sempre positiva e
    la bassa sempre negativa, come si aspetta chi legge il bollettino.
    """
    lat, lon = PUNTO_MARE
    url = ("https://marine-api.open-meteo.com/v1/marine"
           f"?latitude={lat}&longitude={lon}"
           "&hourly=sea_level_height_msl,ocean_current_velocity,"
           "ocean_current_direction"
           "&timezone=Europe/Rome&forecast_days=1")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        h = r.json()["hourly"]
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"[errore] dati marini non disponibili: {e}")
        return None

    ore = h["time"]
    liv = h.get("sea_level_height_msl") or []
    cv = h.get("ocean_current_velocity") or []
    cd = h.get("ocean_current_direction") or []

    # Corrente all'ora del bollettino; se manca, primo valore utile del giorno.
    corrente = None
    ora_ora = datetime.now(TZ).hour
    for i, t in enumerate(ore):
        if i >= len(cd) or cd[i] is None:
            continue
        vel = cv[i] if i < len(cv) else None
        if int(t[11:13]) == ora_ora:
            corrente = {"dir": cd[i], "vel": vel}
            break
        if corrente is None:  # fallback: prima lettura valida della giornata
            corrente = {"dir": cd[i], "vel": vel}

    # Maree: massimi (alta) e minimi (bassa) locali della serie oraria di oggi.
    # Le altezze vengono riportate come scarto dal livello medio della giornata,
    # perche' lo zero del modello puo' essere spostato anche di decine di cm
    # rispetto al mare reale (es. tutti i valori negativi con l'alta pressione).
    validi = [v for v in liv if v is not None]
    media_giorno = sum(validi) / len(validi) if validi else 0.0
    maree = []
    for i in range(1, len(liv) - 1):
        a, b, c = liv[i - 1], liv[i], liv[i + 1]
        if None in (a, b, c):
            continue
        if b >= a and b >= c and (b > a or b > c):
            maree.append(("alta", ore[i][11:16], b - media_giorno))
        elif b <= a and b <= c and (b < a or b < c):
            maree.append(("bassa", ore[i][11:16], b - media_giorno))

    # Collassa run di estremi consecutivi dello stesso tipo (plateau orari):
    # tiene il piu' alto per l'alta marea, il piu' basso per la bassa.
    compatti = []
    for e in maree:
        if compatti and compatti[-1][0] == e[0]:
            prec = compatti[-1]
            piu_estremo = ((e[0] == "alta" and e[2] > prec[2])
                           or (e[0] == "bassa" and e[2] < prec[2]))
            compatti[-1] = e if piu_estremo else prec
        else:
            compatti.append(e)

    return {"corrente": corrente, "maree": compatti}


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
                testo = (f"📉 *ALERT VARIAZIONE PRESSIONE — {nome}*\n"
                         f"🔴 *Calo marcato*\n\n"
                         f"Pressione *{p:.1f} hPa*, in calo di "
                         f"~*{caduta:.1f} hPa* nelle ultime 3 ore.\n"
                         f"_Possibile peggioramento o groppo in arrivo, "
                         f"prudenza in acqua._")
            else:
                testo = (f"📉 *ALERT VARIAZIONE PRESSIONE — {nome}*\n"
                         f"🟡 *Calo moderato*\n\n"
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

    # Il bollettino periodico stazioni esce una volta per "slot" di mezz'ora
    # (:00-:29 / :30-:59) in fascia oraria. Lo calcolo PRIMA del giro sulle
    # stazioni: se il bollettino esce in questo run, gli avvisi vento/raffica
    # non partono come messaggi a se' stanti ma confluiscono nel bollettino
    # (niente doppioni). Tra un bollettino e l'altro partono subito, da soli.
    slot = None
    bollettino_dovuto = False
    if in_orario:
        slot = f"{oggi} {adesso.hour:02d}{'A' if adesso.minute < 30 else 'B'}"
        bollettino_dovuto = stato.get("_stazioni_slot") != slot

    letture = {}  # nome -> dati (o None): serve al bollettino periodico
    extra = {}    # nome -> info avviso (tendenza/banner/eta/raffica) per il bollettino
    for st in STAZIONI:
        nome = st["nome"]
        dati = leggi_stazione(st)
        letture[nome] = dati
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

        # Direzione "verso il circolo": True se il vento arriva da un settore
        # che spinge verso Lido di Spina (semicerchio sud per Porto Corsini,
        # nord per Volano). Vale sia per l'avviso vento sia per l'alert raffica.
        direzioni_ok = (st["direzioni"] is None
                        or direzione in st["direzioni"])

        # Info dell'avviso (banner del livello, stima di arrivo, salto di
        # raffica) da mostrare solo quando la direzione punta verso il circolo.
        # Le raccolgo qui: servono sia al messaggio d'avviso a se' stante sia,
        # se in questo run esce il bollettino, per confluire dentro di esso.
        banner = raffica_note = None
        eta_min = None
        if direzioni_ok:
            if livello_ora >= 1:
                banner = LIVELLI[livello_ora - 1]["tag"]
                eta = stima_arrivo_min(st.get("coord"), direzione, vento)
                if eta is not None:
                    eta_min = max(5, int(round(eta / 5.0) * 5))
            if raf_ora > raf_prima:
                soglia = RAFFICA_LIVELLI[raf_ora - 1]["soglia"]
                raffica_note = (f"🌀 Raffica salita a *{raffica:.1f} nodi* "
                                f"(soglia {soglia:.0f})")
        extra[nome] = {"tendenza": tendenza, "banner": banner,
                       "eta_min": eta_min, "raffica_note": raffica_note}

        # Se il bollettino esce in questo run, gli avvisi confluiscono li'
        # dentro: non mando i messaggi a se' stanti.
        if bollettino_dovuto:
            if livello_ora > livello_prima or raf_ora > raf_prima:
                print(f"[info] avviso {nome} confluito nel bollettino stazioni")
            continue

        # --- ALERT VENTO: solo quando il livello SALE (e direzione OK) ---
        if livello_ora > livello_prima:
            if in_orario and direzioni_ok:
                liv = LIVELLI[livello_ora - 1]
                dir_txt = f"{direzione} {freccia(direzione)}".strip()
                raffica_txt = (f" — raffica *{raffica:.1f} nodi*"
                               if raffica is not None else "")
                corpo = (f"🌬️ *ALERT VENTO — {nome}*\n"
                         f"{liv['tag']} — {liv['descrizione']}\n\n"
                         f"Vento *{vento:.1f} nodi* da {dir_txt}{raffica_txt}")
                if tendenza:
                    corpo += f"\n{tendenza}"
                if eta_min is not None:
                    corpo += (f"\n⏱️ Possibile arrivo al circolo tra "
                              f"~{eta_min} min")
                try:
                    invia_telegram(corpo)
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] invio Telegram fallito: {e}")
            else:
                motivo = "fuori orario" if not in_orario else "direzione esclusa"
                print(f"[info] superamento vento ma avviso non inviato "
                      f"({motivo})")

        # --- Avviso RAFFICA: quando il picco di giornata sale di soglia ---
        # Come l'avviso vento, scatta solo se la direzione attuale punta verso
        # il circolo (semicerchio sud/nord della stazione).
        if raf_ora > raf_prima:
            if in_orario and direzioni_ok:
                soglia = RAFFICA_LIVELLI[raf_ora - 1]["soglia"]
                dir_txt = f"{direzione} {freccia(direzione)}".strip()
                testo = (f"🌀 *ALERT RAFFICA — {nome}*\n"
                         f"Oggi la raffica ha raggiunto *{raffica:.1f} nodi* "
                         f"(soglia {soglia:.0f}) da {dir_txt}.")
                try:
                    invia_telegram(testo)
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] invio Telegram raffica fallito: {e}")
            else:
                motivo = "fuori orario" if not in_orario else "direzione esclusa"
                print(f"[info] soglia raffica superata ma avviso non inviato "
                      f"({motivo})")

    # --- Bollettino periodico stazioni: una volta ogni mezz'ora, in fascia
    # oraria, SEMPRE (anche a dati invariati) perche' la situazione vento in
    # tempo reale interessa ai soci. Se in questo run scatterebbe un avviso
    # vento/raffica, le sue info confluiscono qui (banner del livello,
    # tendenza, stima di arrivo) invece di un messaggio a se' stante. ---
    if bollettino_dovuto:
        righe = [f"🌬️ *SITUAZIONE VENTO — {adesso:%H:%M}*"]
        almeno_uno = False
        for st in STAZIONI:
            nome = st["nome"]
            dati = letture.get(nome)
            if dati is None:
                righe.append(f"\n*{nome}*: dati non disponibili")
                continue
            almeno_uno = True
            ex = extra.get(nome, {})
            dir_txt = f"{dati['direzione']} {freccia(dati['direzione'])}".strip()
            raffica = dati.get("raffica")
            raf_txt = (f" — raffica max oggi *{raffica:.1f} nodi*"
                       if raffica is not None else "")
            testa = f"🌬️ *{nome}*"
            if ex.get("banner"):  # livello d'avviso in corso (es. 🟢 Vento 10 nodi)
                testa += f" — {ex['banner']}"
            blocco = [testa,
                      f"Vento *{dati['vento']:.1f} nodi* da {dir_txt}{raf_txt}"]
            info = []
            tnd = ex.get("tendenza")
            if tnd and ("aumento" in tnd or "calo" in tnd):
                info.append(tnd)  # la tendenza "stabile" la ometto (poco utile)
            if ex.get("eta_min") is not None:
                info.append(f"⏱️ arrivo al circolo ~{ex['eta_min']} min")
            if info:
                blocco.append(" · ".join(info))
            if ex.get("raffica_note"):
                blocco.append(ex["raffica_note"])
            righe.append("\n" + "\n".join(blocco))
        if almeno_uno:
            try:
                invia_telegram("\n".join(righe))
                stato["_stazioni_slot"] = slot
                cambiato = True
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio bollettino stazioni fallito: {e}")

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
