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
import time
from datetime import datetime, time as dt_time, timedelta
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
# distinto dalla "Situazione vento" informativa che esce ogni 15 minuti.
LIVELLI = [
    {
        "soglia": 20.0,
        "riarmo": 19.0,
        "tag": "⚠️ *20+ nodi*",
        "descrizione": ("_Vento sostenuto: condizioni impegnative, adatte solo "
                        "a chi ha esperienza. Valutate bene prima di uscire._"),
    },
    {
        "soglia": 25.0,
        "riarmo": 24.0,
        "tag": "🟠 *25+ nodi*",
        "descrizione": ("_Vento forte: condizioni severe, adatte solo a "
                        "equipaggi molto esperti e ben attrezzati. Valutate "
                        "attentamente se uscire._"),
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
    {"soglia": 20.0, "riarmo": 19.0},
    {"soglia": 25.0, "riarmo": 24.0},
    {"soglia": 30.0, "riarmo": 29.0},
]

# Raffica 10' / vento medio: da questo rapporto in su il vento e' "a strappi"
# e l'ALERT VENTO lo segnala con una riga in piu'.
RAFFICOSO_FATTORE = 1.6

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

# --- CORRENTE A LIDO DI SPINA (Arpae) ---------------------------------------
# Previsione locale dal modello oceanografico Adriac di Arpae (1 km, run
# giornaliero 00 UTC, +72h ORARIE — verificato sul file: 72 istanti a passo
# 3600 s): molto piu' rappresentativo di Open-Meteo per la costa ferrarese.
# Il file pesa ~65 MB, quindi si scarica UNA VOLTA AL GIORNO e la serie oraria
# sul punto viene messa in cache in state.json (chiave "_corrente"): a ogni
# giro dei 15 minuti si legge dalla cache, senza traffico.
#
# Piu' frequenza NON si puo' avere dai modelli (Adriac, Copernicus e Open-Meteo
# girano tutti una volta al giorno), quindi il dato "vivo" ogni 15 minuti viene
# dalle MISURE:
#   - boa Nausicaa 2 (Cesenatico): unica che misura la corrente, ogni 10 min,
#     ma e' a 48 km a SE -> dice l'andamento della corrente costiera in
#     generale, non il dato locale;
#   - mareografo di Porto Garibaldi: livello del mare ogni 10 min a ~2 km dal
#     circolo -> da' la FASE DI MAREA misurata sul posto (in salita = flusso
#     verso NW, in calo = verso SE).
# Attenzione: gli orari delle API Arpae sono in UTC (verificato).
PUNTO_CORRENTE = (44.665, 12.31)   # ~2 km al largo del circolo
ADRIAC_URL = ("https://dati-simc.arpae.it/opendata/adriac/"
              "{data}_adriac_1km_his_2dcur_fc.nc.gz")
BOA_URL = ("https://apps.arpae.it/REST/meteo_marefe/"
           "?where=%7B%22anagrafica.nome%22%3A%22Nausicaa%202%22%7D")
MAREA_URL = ("https://apps.arpae.it/REST/meteo_marefe/"
             "?where=%7B%22anagrafica.nome%22%3A%22Porto%20Garibaldi%22%7D")
MAREA_FINESTRA_MIN = 90   # minuti su cui si calcola la pendenza del livello
MAREA_STANCA_CM = 3.0     # sotto questa variazione oraria: marea "stanca"
CORRENTE_MIN_KN = 0.1     # sotto: "trascurabile", la direzione non ha senso
UTC = ZoneInfo("UTC")


def _adesso_utc() -> datetime:
    """Istante attuale in UTC, senza fuso (come gli orari delle API Arpae)."""
    return datetime.now(TZ).astimezone(UTC).replace(tzinfo=None)


def _scarica_adriac(data: str):
    """Serie oraria della corrente prevista sul punto, dal run `data`.

    Ritorna {"run", "t0" (UTC), "passo_min", "u", "v"} con u/v in m/s
    (None dove il modello non ha dato), oppure None se il run non c'e'
    o manca netCDF4.
    """
    try:
        import gzip
        import netCDF4
        import numpy as np
    except ImportError as e:
        print(f"[info] adriac saltato, libreria mancante: {e}")
        return None

    try:
        r = requests.get(ADRIAC_URL.format(data=data), timeout=300)
        r.raise_for_status()
        ds = netCDF4.Dataset("adriac", memory=gzip.decompress(r.content))
    except Exception as e:  # noqa: BLE001
        print(f"[info] adriac {data} non disponibile: {e}")
        return None

    try:
        lat = ds.variables["lat_rho"][:]
        lon = ds.variables["lon_rho"][:]
        j, i = np.unravel_index(
            np.argmin((lat - PUNTO_CORRENTE[0]) ** 2
                      + (lon - PUNTO_CORRENTE[1]) ** 2), lat.shape)
        tvar = ds.variables["ocean_time"]
        tempi = netCDF4.num2date(tvar[:], tvar.units,
                                 only_use_cftime_datetimes=False,
                                 only_use_python_datetimes=True)
        u = ds.variables["ubar_eastward"][:, j, i]
        v = ds.variables["vbar_northward"][:, j, i]
    except Exception as e:  # noqa: BLE001
        print(f"[errore] adriac: estrazione fallita: {e}")
        return None
    finally:
        ds.close()

    if len(tempi) < 2:
        return None
    passo = max(1, round((tempi[1] - tempi[0]).total_seconds() / 60))

    def _val(x):
        return None if np.ma.is_masked(x) else round(float(x), 3)

    print(f"[info] adriac: uso il run {data} ({len(tempi)} istanti, "
          f"passo {passo} min)")
    return {"run": data,
            "t0": tempi[0].strftime("%Y-%m-%dT%H:%M"),
            "passo_min": passo,
            "u": [_val(x) for x in u],
            "v": [_val(x) for x in v]}


def serie_corrente(stato: dict):
    """Serie oraria Adriac sul punto, con cache giornaliera in state.json.

    Scarica solo quando serve: se in cache c'e' gia' il run piu' recente
    pubblicato non tocca la rete, e in ogni caso ritenta al massimo una
    volta all'ora (il run di oggi compare verso le 9:30-9:40, quindi il
    bollettino delle 9:00 usa ancora quello di ieri: l'orizzonte di 72 ore
    copre comunque la giornata).
    """
    cache = stato.get("_corrente") or {}
    ora = datetime.now(TZ)
    ora_tag = ora.strftime("%Y%m%d%H")
    candidati = [(ora - timedelta(days=d)).strftime("%Y%m%d")
                 for d in (0, 1, 2)]
    if cache.get("run") == candidati[0]:
        return cache
    if cache.get("tentativo") == ora_tag:
        return cache or None

    cache = dict(cache, tentativo=ora_tag)
    stato["_corrente"] = cache
    for data in candidati:
        if cache.get("run") == data:
            return cache          # in cache c'e' gia' il run piu' recente
        nuova = _scarica_adriac(data)
        if nuova:
            nuova["tentativo"] = ora_tag
            stato["_corrente"] = nuova
            return nuova
    return cache if cache.get("run") else None


def _uv_serie(serie: dict, quando: datetime):
    """(u, v) in m/s all'istante UTC `quando`, o None se fuori serie."""
    if not serie or not serie.get("u"):
        return None
    try:
        t0 = datetime.strptime(serie["t0"], "%Y-%m-%dT%H:%M")
    except (ValueError, KeyError):
        return None
    passo = serie.get("passo_min") or 60
    k = round((quando - t0).total_seconds() / 60 / passo)
    if not 0 <= k < len(serie["u"]):
        return None
    u, v = serie["u"][k], serie["v"][k]
    return None if u is None or v is None else (u, v)


def _nodi_gradi(u: float, v: float):
    """Da (u est, v nord) in m/s a (nodi, gradi VERSO cui scorre)."""
    return (math.hypot(u, v) * 1.94384,
            math.degrees(math.atan2(u, v)) % 360)


def corrente_ora(stato: dict, quando: datetime | None = None):
    """Corrente prevista adesso sul punto: (nodi, gradi_verso) o None."""
    serie = serie_corrente(stato)
    uv = _uv_serie(serie, quando or _adesso_utc())
    return _nodi_gradi(*uv) if uv else None


def corrente_fasce(stato: dict):
    """Corrente media di mattina (9-13) e pomeriggio (13-19), da Adriac.

    Media vettoriale sugli istanti di oggi. Ritorna
    {"mattina": (nodi, dir16_verso), "pomeriggio": (...)} oppure None.
    """
    serie = serie_corrente(stato)
    if not serie or not serie.get("u"):
        return None
    oggi = datetime.now(TZ).date()
    out = {}
    for nome_fascia, (h1, h2) in (("mattina", (9, 13)),
                                  ("pomeriggio", (13, 19))):
        us, vs = [], []
        for h in range(h1, h2):
            t_loc = datetime.combine(oggi, dt_time(h), tzinfo=TZ)
            uv = _uv_serie(serie, t_loc.astimezone(UTC).replace(tzinfo=None))
            if uv:
                us.append(uv[0])
                vs.append(uv[1])
        if not us:
            continue
        nodi, gradi = _nodi_gradi(sum(us) / len(us), sum(vs) / len(vs))
        out[nome_fascia] = (nodi, _dir16(gradi))
    return out or None


def _letture_arpae(url: str):
    """Letture [(istante UTC, valori)] di una stazione marina Arpae.

    Prende gli ultimi due giorni disponibili in ordine cronologico, cosi'
    la finestra a cavallo della mezzanotte UTC non si spezza.
    """
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        voci = r.json().get("_items") or []
    except Exception as e:  # noqa: BLE001
        print(f"[errore] stazione marina Arpae non raggiungibile: {e}")
        return []
    if not voci:
        return []
    dati = (voci[0].get("dati") or {})
    out = []
    for giorno in sorted(dati)[-2:]:
        for ora in sorted(dati[giorno] or {}):
            try:
                t = datetime.strptime(giorno + ora, "%Y%m%d%H%M")
            except ValueError:
                continue
            out.append((t, dati[giorno][ora] or {}))
    return out


def corrente_boa():
    """Corrente superficiale misurata dalla boa Nausicaa 2 (Cesenatico).

    Ritorna (nodi, gradi_verso, "HH:MM" ora italiana) dell'ultima lettura
    valida, oppure None. La boa e' ~48 km a SE di Lido di Spina: e' un
    riscontro della corrente costiera generale, non il dato locale.
    """
    for t, v in reversed(_letture_arpae(BOA_URL)):
        vel = v.get("intensita_istantanea_corrente_superficie")
        gradi = v.get("direzione_istantanea_corrente_superficie")
        if vel is None or gradi is None:
            continue
        locale = t.replace(tzinfo=UTC).astimezone(TZ)
        return float(vel) * 1.94384, float(gradi), f"{locale:%H:%M}"
    return None


def fase_marea():
    """Fase di marea misurata a Porto Garibaldi (~2 km dal circolo).

    Regressione lineare sul livello del mare degli ultimi
    MAREA_FINESTRA_MIN minuti disponibili (letture ogni 10 min, con una
    latenza fino a ~40 min). Ritorna (testo, cm_orari) — es.
    ("in salita", 7.4) — oppure None se i dati non bastano.
    """
    punti = [(t, float(v["livello_mare_igm_radar"]))
             for t, v in _letture_arpae(MAREA_URL)
             if v.get("livello_mare_igm_radar") is not None
             and abs(float(v["livello_mare_igm_radar"])) < 5]
    if len(punti) < 3:
        return None
    fine = punti[-1][0]
    finestra = [(t, h) for t, h in punti
                if (fine - t).total_seconds() <= MAREA_FINESTRA_MIN * 60]
    if len(finestra) < 3:
        return None

    # Pendenza ai minimi quadrati: il livello ha un rumore di 2-3 cm da una
    # lettura all'altra, la differenza fra due sole letture ingannerebbe.
    xs = [(t - fine).total_seconds() / 3600 for t, _ in finestra]
    ys = [h * 100 for _, h in finestra]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    cm_ora = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    if abs(cm_ora) < MAREA_STANCA_CM:
        return "stanca", cm_ora
    return ("in salita" if cm_ora > 0 else "in calo"), cm_ora


def testo_corrente(nodi: float, verso: str) -> str:
    """Corrente a parole: sotto il decimo di nodo non vale la pena darne
    la direzione (il modello e' rumore a quelle intensita')."""
    return ("trascurabile" if nodi < CORRENTE_MIN_KN
            else f"~{nodi:.1f} kn verso {verso}")


def riga_corrente(stato: dict):
    """Riga unica su corrente e marea per la SITUAZIONE VENTO dei 15 minuti.

    Pensata per essere letta al volo su telefono o smartwatch mentre si
    naviga: intensita', freccia che punta DOVE VA la corrente, sigla della
    direzione, fase di marea. Es.:
        🌊 *Corrente* ~0.4 kn ↘️ SE · marea in salita
    Il numero e' la previsione Adriac per l'ora in corso (griglia 1 km sul
    punto); se manca si ripiega sulla misura della boa di Cesenatico, e in
    quel caso lo si dichiara. Ritorna None se non c'e' proprio nulla.
    """
    marea = fase_marea()
    coda = f" · marea {marea[0]}" if marea else ""

    fonte = ""
    valore = corrente_ora(stato)
    if valore is None:
        boa = corrente_boa()
        if boa:
            valore = (boa[0], boa[1])
            fonte = " _(boa Cesenatico)_"
    if valore is None:
        return f"🌊 *Marea* {marea[0]}" if marea else None

    nodi, gradi = valore
    if nodi < CORRENTE_MIN_KN:
        return f"🌊 *Corrente* trascurabile{fonte}{coda}"
    return (f"🌊 *Corrente* ~{nodi:.1f} kn {freccia_verso(gradi)} "
            f"{_dir16(gradi)}{fonte}{coda}")


def riga_corrente_pomeriggio(stato: dict):
    """Media prevista per il pomeriggio (13-19), per la scheda delle 14:00.

    Risponde a una domanda diversa da riga_corrente(), che dice com'e' la
    corrente ADESSO: qui serve a decidere prima di scendere in acqua, e a
    quell'ora il run Adriac del giorno e' ormai pubblicato. Niente riscontro
    della boa di Cesenatico: da quando ogni messaggio porta la marea
    misurata a 2 km dal circolo, un dato a 48 km aggiunge poco, e la boa
    resta comunque il ripiego automatico se Adriac manca.
    Ritorna la riga, oppure None se non c'e' la previsione.
    """
    fasce = corrente_fasce(stato)
    if not fasce or "pomeriggio" not in fasce:
        return None
    nodi, verso = fasce["pomeriggio"]
    if nodi < CORRENTE_MIN_KN:
        return "🕐 *Nel pomeriggio*: corrente trascurabile"
    return (f"🕐 *Nel pomeriggio*: corrente prevista "
            f"~{nodi:.1f} kn verso {verso}")


# --- BENVENUTO SERALE -------------------------------------------------------
# I nuovi iscritti vengono raccolti durante il giorno (il bot, admin del
# canale, riceve una notifica a ogni iscrizione) e salutati per nome con un
# unico messaggio alle BENVENUTO_ORA, per non disturbare durante la giornata.
BENVENUTO_ORA = 21
BENVENUTO_TEMPLATE = (
    "👋 *Benvenuti a bordo!*\n\n"
    "{iscritti}\n\n"
    "Grazie per esservi iscritti a *INFO VENTO*! Qui trovate gli alert "
    "vento, raffica, bora e pressione, il bollettino del mattino e la "
    "situazione in tempo reale dalle 9 alle 19.\n"
    "Se il canale vi è utile, giratelo agli amici appassionati di vela: "
    "più siamo, più diventa utile per tutti. ⛵"
)

# --- ALERT BORA -----------------------------------------------------------
# La bora scende da nord-est in modo violento: due stazioni "sentinella" a
# nord-est del circolo (rete meteo-mareografica CPSM / Comune di Venezia,
# open data aggiornati ogni 5 minuti) la vedono con 1-2 ore di anticipo
# rispetto a Lido di Spina. L'avviso scatta solo con vento dal settore NE.
BORA_URL = ("https://dati.venezia.it/sites/default/files/dataset/"
            "opendata/vento.json")
BORA_SENTINELLE = [
    {"id": "1024", "nome": "Sottomarina (Diga Sud Chioggia)",
     "coord": (45.220, 12.308)},
    {"id": "1021", "nome": "Piattaforma CNR (largo di Venezia)",
     "coord": (45.314, 12.508)},
]
# Gradi di provenienza ammessi: solo i settori N, NNE e NE (348.75-56.25,
# a cavallo del nord). Vento forte da altre direzioni non e' bora.
BORA_SETTORE = (348.75, 56.25)
BORA_MAX_ETA_MIN = 40         # scarto lettura piu' vecchia di cosi' (guasto)
BORA_LIVELLI = [
    {"soglia": 20.0, "riarmo": 18.0, "tag": "⚠️ *Bora 20+ nodi*",
     "descrizione": ("_Bora sostenuta sulle sentinelle a nord-est: puo' "
                     "arrivare in modo violento. Se siete in acqua con la "
                     "deriva, valutate il rientro._")},
    {"soglia": 25.0, "riarmo": 23.0, "tag": "🔴 *Bora 25+ nodi*",
     "descrizione": ("_Bora forte in avvicinamento: rientrare a riva "
                     "e' prudente._")},
    {"soglia": 30.0, "riarmo": 28.0, "tag": "🛑 *Bora 30+ nodi*",
     "descrizione": ("_Bora molto forte: rientrate subito, condizioni "
                     "pericolose in arrivo._")},
]

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

# Bollettino periodico "situazione stazioni": pubblicato una volta ogni quarto
# d'ora (slot :00-:14, :15-:29, :30-:44, :45-:59), al passo del controllo delle
# stazioni, nella fascia oraria attiva, SEMPRE, anche se i dati non sono
# cambiati. Il vento in tempo reale interessa ai soci del circolo.

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
#   "gca"         -> Guardia Costiera Ausiliaria Ravenna (Marina di Ravenna)
# Campo opzionale "riserva": {url, tipo} di una stazione di scorta nello
# stesso punto. Se la principale non risponde si usano i suoi dati; se la
# principale funziona, dalla riserva si prende comunque la raffica degli
# ultimi 10 minuti (raffica_10min), piu' tempestiva della massima giornaliera.
STAZIONI = [
    {
        "nome": "Porto Corsini",
        "url": "http://www.meteosystem.com/wlip/awc/",
        "tipo": "meteosystem",
        "coord": (44.493, 12.279),    # a sud del circolo (~20 km)
        # Semicerchio sud: venti da E, SE, S, SW, O (e settori intermedi).
        "direzioni": ["E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W"],
        # Stazione GCA di Marina di Ravenna: stesso punto, dall'altra parte
        # del canale del porto. Fa da riserva e fornisce la raffica 10 min.
        "riserva": {
            "url": ("https://www.guardcostaus-ravenna.it/MeteoPagine/"
                    "datimeteocompatti.php"),
            "tipo": "gca",
        },
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


# I fronti e i rinforzi viaggiano in genere PIU' VELOCI del vento misurato a
# 10 metri (li guida il vento in quota): il limite basso della forchetta
# accorcia la stima di questo fattore.
ETA_FATTORE_VELOCE = 0.7


def eta_forchetta(eta) -> str:
    """Stima d'arrivo come forchetta, es. '~20–30 min'.

    Il limite alto e' la stima alla velocita' del vento al suolo; quello
    basso tiene conto che il rinforzo puo' arrivare prima. Entrambi
    arrotondati ai 5 minuti; se coincidono, valore secco.
    """
    lento = max(5, int(round(eta / 5.0) * 5))
    veloce = max(5, int(round(eta * ETA_FATTORE_VELOCE / 5.0) * 5))
    if veloce == lento:
        return f"~{lento} min"
    return f"~{veloce}–{lento} min"


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


def freccia_verso(gradi: float) -> str:
    """Freccia che punta verso DOVE scorre la corrente.

    A differenza del vento (indicato per provenienza), la corrente si
    indica per destinazione: i gradi in ingresso sono gia' il "verso".
    """
    return _FRECCE[int((gradi + 22.5) // 45) % 8]


_COMPASS16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _dir16(gradi: float) -> str:
    """Converte i gradi nella sigla a 16 punte (es. 135 -> SE)."""
    return _COMPASS16[int((gradi + 11.25) // 22.5) % 16]


# Fascia consigliata per uscire in deriva, calcolata sulla previsione oraria:
# vento medio ne' troppo debole ne' vicino alla soglia del primo alert, e
# raffiche previste non violente.
FASCIA_VENTO_MIN = 6.0    # nodi: sotto, non si plana e ci si annoia
FASCIA_VENTO_MAX = 16.0   # nodi: sopra, meglio lasciare ai piu' esperti
FASCIA_RAFFICA_MAX = 22.0  # nodi: raffiche oltre = vento troppo irregolare


def fascia_migliore(ore, ws, wg, wd):
    """Fascia oraria contigua piu' lunga con vento "da deriva", o None.

    Un'ora e' buona se il vento medio previsto sta tra FASCIA_VENTO_MIN e
    FASCIA_VENTO_MAX e le raffiche sotto FASCIA_RAFFICA_MAX, dentro l'orario
    attivo del canale. Serve una fascia di almeno 2 ore.
    Ritorna (ora_inizio, ora_fine, media_nodi, sigla_direzione).
    """
    buone = []
    for i, t in enumerate(ore):
        ora = int(t[11:13])
        if (ORA_INIZIO <= ora < ORA_FINE
                and FASCIA_VENTO_MIN <= ws[i] <= FASCIA_VENTO_MAX
                and wg[i] <= FASCIA_RAFFICA_MAX):
            buone.append((ora, i))
    if not buone:
        return None
    migliore = corrente = [buone[0]]
    for prec, cur in zip(buone, buone[1:]):
        corrente = corrente + [cur] if cur[0] == prec[0] + 1 else [cur]
        if len(corrente) > len(migliore):
            migliore = corrente
    if len(migliore) < 2:
        return None
    idx = [i for _, i in migliore]
    media = sum(ws[i] for i in idx) / len(idx)
    sigla = _dir16(wd[idx[len(idx) // 2]])
    return migliore[0][0], migliore[-1][0] + 1, media, sigla


def bollettino_mattutino(stato: dict):
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

    # Fascia consigliata per la deriva: solo quando esiste davvero una
    # finestra di almeno 2 ore con vento "giusto"; se il giorno e' tutto
    # bonaccia o tutto burrasca, niente riga (il quadro sopra basta).
    fascia = fascia_migliore(ore, ws, wg, wd)
    if fascia:
        f_da, f_a, f_media, f_dir = fascia
        righe.append(f"🕐 *Fascia migliore per uscire: {f_da}–{f_a}* — "
                     f"~{f_media:.0f} nodi da {f_dir}.")

    # Corrente: previsione locale Arpae Adriac (punto davanti al circolo),
    # con il riscontro misurato dalla boa Nausicaa 2. Se Adriac non e'
    # disponibile si ripiega sulla corrente Open-Meteo come prima.
    # Le maree restano da Open-Meteo Marine (best effort).
    mare = dati_marini()
    adriac = corrente_fasce(stato)
    boa = corrente_boa()
    if mare or adriac or boa:
        righe.append("")
    if adriac:
        parti = [f"{fascia} {testo_corrente(nodi, verso)}"
                 for fascia, (nodi, verso) in adriac.items()]
        righe.append("🌊 *Corrente a Lido di Spina* (previsione Arpae): "
                     + ", ".join(parti))
    elif mare:
        c = mare.get("corrente")
        if c and c.get("dir") is not None:
            vtxt = (f" (~{c['vel']:.1f} km/h)"
                    if c.get("vel") is not None else "")
            righe.append(f"🌊 *Corrente di superficie*: verso "
                         f"{_dir16(c['dir'])}{vtxt}")
    if boa:
        nodi_b, gradi_b, hhmm_b = boa
        righe.append(f"  _Misurata alle {hhmm_b} dalla boa di Cesenatico: "
                     f"~{nodi_b:.1f} kn verso {_dir16(gradi_b)}_")
    if mare:
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
            # Nota extra solo quando serve: un'alta sotto media (segno -)
            # o una bassa sopra media (segno +) altrimenti disorientano.
            alta_neg = any(t == "alta" and round(a * 100) < 0
                           for t, _, a in maree)
            bassa_pos = any(t == "bassa" and round(a * 100) > 0
                            for t, _, a in maree)
            if alta_neg:
                righe.append("  _Un'alta marea può risultare leggermente "
                             "sotto la media, quindi −, pur essendo "
                             "un'alta marea: succede quando la giornata è "
                             "\"in salita\" (il mare cresce nel corso del "
                             "giorno e il picco notturno resta sotto la "
                             "media complessiva)._")
            elif bassa_pos:
                righe.append("  _Una bassa marea può risultare leggermente "
                             "sopra la media, quindi +, pur essendo "
                             "una bassa marea: succede quando il livello "
                             "generale sale o scende molto nel corso della "
                             "giornata, e quel minimo capita in un momento "
                             "in cui il mare è comunque sopra la media "
                             "complessiva._")

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


def _parse_gca(html: str) -> dict | None:
    """Stazione Guardia Costiera Ausiliaria Ravenna (Marina di Ravenna).

    Tabella PHP con i valori gia' in nodi: vento attuale, gradi di
    provenienza, raffica continua degli ultimi 10 minuti e massima odierna.
    """
    testo = _solo_testo(html)
    m_vento = re.search(r"vento attuale:\s*([\d.,]+)", testo, re.IGNORECASE)
    m_gradi = re.search(r"Gradi di provenienza del vento:\s*([\d.,]+)",
                        testo, re.IGNORECASE)
    m_raf10 = re.search(r"raffica continua:\s*([\d.,]+)",
                        testo, re.IGNORECASE)
    m_rafmax = re.search(r"massima del vento di oggi:\s*([\d.,]+)",
                         testo, re.IGNORECASE)
    m_press = re.search(r"Pressione:\s*([\d.,]+)", testo, re.IGNORECASE)
    if not (m_vento and m_gradi):
        return None
    return {
        "vento": _num(m_vento.group(1)),
        "direzione": _dir16(_num(m_gradi.group(1))),
        "raffica": _num(m_rafmax.group(1)) if m_rafmax else None,
        "raffica_10min": _num(m_raf10.group(1)) if m_raf10 else None,
        "pressione": _num(m_press.group(1)) if m_press else None,
    }


PARSER = {
    "meteosystem": _parse_meteosystem,
    "saratoga": _parse_saratoga,
    "gca": _parse_gca,
}


def _leggi_fonte(fonte: dict) -> dict | None:
    """Scarica e interpreta una singola pagina stazione (o riserva)."""
    url = fonte["url"]
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[errore] download fallito da {url}: {e}")
        return None

    parser = PARSER[fonte.get("tipo", "meteosystem")]
    dati = parser(r.text)
    if dati is None:
        print(f"[errore] impossibile leggere il vento da {url}")
    return dati


def leggi_stazione(st: dict) -> dict | None:
    """Legge la stazione, con eventuale riserva nello stesso punto.

    Ritorna {vento, direzione, raffica, [raffica_10min]} oppure None se
    falliscono sia la principale sia la riserva. Se la principale funziona
    e la riserva pure, dalla riserva si prende la raffica degli ultimi
    10 minuti (piu' tempestiva della massima giornaliera).
    """
    dati = _leggi_fonte(st)
    ris = st.get("riserva")
    if ris is None:
        return dati

    dati_ris = _leggi_fonte(ris)
    if dati is None and dati_ris is not None:
        print(f"[info] {st['nome']}: principale giu', uso la riserva "
              f"({ris['tipo']})")
        return dati_ris
    if dati is not None and dati_ris is not None:
        if dati_ris.get("raffica_10min") is not None:
            dati["raffica_10min"] = dati_ris["raffica_10min"]
    return dati


# --------------------------------------------------------------------------
# TELEGRAM
# --------------------------------------------------------------------------

# Id del messaggio piu' recente che questo processo ha inviato al canale.
# Serve alla pulizia giornaliera per sapere dove finiscono i messaggi di
# "ieri": tutto cio' che il bot manda oggi avra' un id piu' alto e va salvato.
_ULTIMO_MSG_ID = 0


def invia_telegram(testo: str, silenzioso: bool = False):
    """Manda un messaggio al canale.

    Con silenzioso=True il messaggio arriva senza suoneria (Telegram
    "disable_notification"): si usa per i contenuti di contorno (bollettino
    del mattino, grafici, riepilogo, benvenuti). Suonano invece gli ALERT
    e la situazione vento, i contenuti principali del canale.
    """
    global _ULTIMO_MSG_ID
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown",
              "disable_notification": silenzioso},
        timeout=30,
    )
    r.raise_for_status()
    mid = r.json().get("result", {}).get("message_id")
    if isinstance(mid, int):
        _ULTIMO_MSG_ID = max(_ULTIMO_MSG_ID, mid)
    print("[ok] messaggio Telegram inviato")
    return mid if isinstance(mid, int) else None


def invia_foto(png: bytes, didascalia: str, silenzioso: bool = False):
    """Manda una foto (PNG in memoria) al canale, con didascalia."""
    global _ULTIMO_MSG_ID
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data={"chat_id": chat_id, "caption": didascalia,
              "parse_mode": "Markdown",
              "disable_notification": json.dumps(silenzioso)},
        files={"photo": ("grafico.png", png, "image/png")},
        timeout=60,
    )
    r.raise_for_status()
    mid = r.json().get("result", {}).get("message_id")
    if isinstance(mid, int):
        _ULTIMO_MSG_ID = max(_ULTIMO_MSG_ID, mid)
    print("[ok] foto Telegram inviata")
    return mid if isinstance(mid, int) else None


def invia_telegram_admin(testo: str) -> None:
    """Messaggio PRIVATO all'admin del canale (non passa dal canale).

    Usa TELEGRAM_ADMIN_CHAT_ID (l'id della chat privata tra admin e bot).
    Se la variabile non e' configurata non fa nulla: il watchdog e' una
    funzione opzionale di manutenzione.
    """
    admin = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    if not admin:
        print("[info] TELEGRAM_ADMIN_CHAT_ID non configurato, avviso saltato")
        return
    token = os.environ["TELEGRAM_TOKEN"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": admin, "text": testo, "parse_mode": "Markdown"},
        timeout=30,
    )
    r.raise_for_status()
    print("[ok] avviso admin inviato")


GUASTO_AVVISO_MIN = 60  # minuti di stazione illeggibile prima dell'avviso


def watchdog_stazione(stato: dict, nome: str, ok: bool,
                      adesso: datetime, in_orario: bool) -> bool:
    """Avvisa l'admin (in privato) se una stazione resta illeggibile a lungo.

    Il guasto puo' essere della stazione o del parser (pagina cambiata):
    in entrambi i casi il canale mostrerebbe "dati non disponibili" senza
    che nessuno se ne accorga. Un solo avviso per guasto, piu' uno quando
    la stazione torna a rispondere. Il canale non viene toccato.
    Ritorna True se lo stato e' cambiato.
    """
    s = stato.setdefault(nome, {})
    if ok:
        if "guasto_da" not in s:
            return False
        if s.pop("guasto_avvisato", None):
            try:
                invia_telegram_admin(f"✅ *{nome}* è tornata leggibile.")
            except Exception as e:  # noqa: BLE001
                print(f"[errore] avviso admin fallito: {e}")
        s.pop("guasto_da", None)
        return True
    if not in_orario:
        return False  # di notte i siti fanno manutenzione: niente conteggi
    da = s.get("guasto_da")
    if da is None:
        s["guasto_da"] = adesso.isoformat()
        return True
    minuti = (adesso - datetime.fromisoformat(da)).total_seconds() / 60
    if not s.get("guasto_avvisato") and minuti >= GUASTO_AVVISO_MIN:
        try:
            invia_telegram_admin(
                f"🛠️ *{nome}* illeggibile da ~{int(minuti)} minuti: "
                f"stazione guasta o pagina cambiata? Il canale intanto "
                f"mostra \"dati non disponibili\".")
            s["guasto_avvisato"] = True
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[errore] avviso admin fallito: {e}")
    return False


def id_corrente_canale() -> int:
    """Scopre l'id del messaggio piu' recente del canale.

    Telegram non permette a un bot di elencare i messaggi, ma gli id sono
    progressivi: mando un messaggio-sonda silenzioso e ne leggo l'id. La sonda
    resta nel canale ma verra' cancellata dalla pulizia che segue.
    """
    global _ULTIMO_MSG_ID
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id,
              "text": "\U0001f9f9 Pulizia del canale...",
              "disable_notification": True},
        timeout=30,
    )
    r.raise_for_status()
    sonda = r.json()["result"]["message_id"]
    _ULTIMO_MSG_ID = max(_ULTIMO_MSG_ID, sonda)
    return sonda


def pulizia_canale(da_id: int, a_id: int, salva=()) -> list:
    """Cancella i messaggi del canale con id da (da_id+1) fino ad a_id compreso.

    Ritorna la lista degli id che Telegram ha RIFIUTATO di cancellare.

    Gli id in `salva` non vengono MAI cancellati: e' l'eccezione per i
    riepiloghi serali, che restano nel canale come archivio storico (utili
    per statistiche future grazie ai grafici che contengono).

    LIMITE TELEGRAM (verificato sul campo il 30/07/2026): un bot NON puo'
    cancellare messaggi piu' vecchi di 48 ORE, nemmeno con il permesso admin
    "Elimina messaggi". In piu' deleteMessages e' ATOMICO: se anche UN SOLO id
    del blocco e' oltre le 48 ore, l'intera chiamata torna 400 e non cancella
    NIENTE. Per questo un blocco rifiutato viene ritentato spezzandolo a meta',
    fino al singolo messaggio: cosi' si perdono solo i messaggi davvero fuori
    tempo massimo, non tutto il blocco. (Gli id gia' inesistenti vengono
    ignorati da Telegram senza errore.)
    """
    da_id = max(da_id, 0)
    if a_id <= da_id:
        print("[ok] pulizia canale: niente da cancellare")
        return []
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    base = f"https://api.telegram.org/bot{token}"
    da_salvare = set(salva)
    ids = [i for i in range(a_id, da_id, -1) if i not in da_salvare]
    if not ids:
        print("[ok] pulizia canale: niente da cancellare")
        return []

    motivi = {}  # id non cancellato -> motivo detto da Telegram

    def cancella(blocco: list) -> list:
        """Un blocco: se Telegram lo rifiuta lo spezza a meta' e ritenta.

        Ritorna gli id rimasti non cancellati.
        """
        motivo = ""
        try:
            r = requests.post(
                f"{base}/deleteMessages",
                json={"chat_id": chat_id, "message_ids": blocco},
                timeout=30,
            )
            if r.status_code == 429:  # flood limit: aspetto e riprovo una volta
                attesa = r.json().get("parameters", {}).get("retry_after", 3)
                time.sleep(attesa)
                r = requests.post(
                    f"{base}/deleteMessages",
                    json={"chat_id": chat_id, "message_ids": blocco},
                    timeout=30,
                )
            if r.ok:
                return []
            try:  # il motivo vero sta nel corpo, non nello status
                motivo = r.json().get("description", r.text[:200])
            except Exception:  # noqa: BLE001
                motivo = r.text[:200]
        except Exception as e:  # noqa: BLE001 - un blocco storto non ferma il resto
            motivo = str(e)
        if len(blocco) == 1:
            motivi[blocco[0]] = motivo
            return blocco
        meta = len(blocco) // 2
        time.sleep(0.2)
        return cancella(blocco[:meta]) + cancella(blocco[meta:])

    rimasti = []
    for i in range(0, len(ids), 100):
        rimasti += cancella(ids[i:i + 100])
        time.sleep(0.2)
    print(f"[ok] pulizia canale: passati i messaggi {da_id + 1}..{a_id} "
          f"({len(rimasti)} non cancellabili)")
    if rimasti:  # un motivo per ciascuno, ma raggruppati: il log resta corto
        per_motivo = {}
        for i in sorted(rimasti):
            per_motivo.setdefault(motivi.get(i, "?"), []).append(i)
        for motivo, elenco in per_motivo.items():
            print(f"[avviso] {len(elenco)} messaggi non cancellati "
                  f"(id {elenco[0]}-{elenco[-1]}): {motivo}")
    return rimasti


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
# ALERT BORA (sentinelle CPSM a nord-est: Sottomarina e Piattaforma CNR)
# --------------------------------------------------------------------------

def leggi_bora() -> dict:
    """Legge il vento delle sentinelle bora dal JSON open data del CPSM.

    Ritorna {id_stazione: {"vento", "raffica" (nodi), "gradi", "quando"}}.
    Salta le letture invalide (-999) o piu' vecchie di BORA_MAX_ETA_MIN
    (la rete aggiorna ogni 5 minuti: un dato vecchio indica un guasto).
    NB: il CPSM pubblica gli orari in ora solare (UTC+1) tutto l'anno.
    """
    voluti = {s["id"] for s in BORA_SENTINELLE}
    try:
        r = requests.get(BORA_URL, timeout=30)
        r.raise_for_status()
        voci = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[errore] download vento CPSM fallito: {e}")
        return {}

    adesso = datetime.now(TZ)
    out = {}
    for voce in voci:
        sid = voce.get("ID_stazione")
        if sid not in voluti:
            continue
        m = re.match(r"\s*([\d.]+)\s*gradi,\s*(-?[\d.]+)\s*m/s,"
                     r"\s*(-?[\d.]+)\s*m/s",
                     voce.get("valore") or "")
        if not m:
            continue
        gradi, vento_ms, raffica_ms = map(float, m.groups())
        if not (0 <= vento_ms < 90 and 0 <= raffica_ms < 90):
            continue  # -999 o valore assurdo: sensore in avaria
        try:
            quando = datetime.strptime(voce["data"], "%Y-%m-%d %H:%M:%S")
            quando = quando.replace(tzinfo=ZoneInfo("Etc/GMT-1"))
        except (KeyError, ValueError):
            continue
        if (adesso - quando).total_seconds() / 60.0 > BORA_MAX_ETA_MIN:
            print(f"[bora] lettura vecchia scartata ({voce.get('stazione')})")
            continue
        out[sid] = {"vento": vento_ms * 1.94384,
                    "raffica": raffica_ms * 1.94384,
                    "gradi": gradi, "quando": quando}
    return out


def controlla_bora(stato: dict, in_orario: bool) -> bool:
    """Controlla le sentinelle bora e avvisa al salire di soglia.

    Il livello sale solo con vento dai settori N/NNE/NE (BORA_SETTORE, a
    cavallo del nord): un vento forte da un'altra direzione non e' bora e
    azzera il livello. Stessa isteresi degli altri alert: niente messaggi
    ripetuti a condizioni stabili. Ritorna True se lo stato e' cambiato.
    """
    letture = leggi_bora()
    if not letture:
        return False

    cambiato = False
    s_bora = stato.setdefault("_bora", {})
    for sent in BORA_SENTINELLE:
        dati = letture.get(sent["id"])
        if dati is None:
            print(f"[bora] {sent['nome']}: dati non disponibili")
            continue

        gradi = dati["gradi"]
        # Il settore scavalca il nord (348.75 -> 56.25): dentro se la
        # provenienza e' oltre l'inizio O sotto la fine.
        in_settore = gradi >= BORA_SETTORE[0] or gradi <= BORA_SETTORE[1]
        vento_eff = dati["vento"] if in_settore else 0.0

        s = s_bora.setdefault(sent["nome"], {})
        prima = s.get("livello", 0)
        ora_liv = calcola_livello(vento_eff, prima, BORA_LIVELLI)

        sigla = _dir16(gradi)
        print(f"[bora] {sent['nome']}: vento {dati['vento']:.1f} kts da "
              f"{sigla} ({gradi:.0f} gradi), raffica {dati['raffica']:.1f} "
              f"kts (liv {prima}->{ora_liv}, settore={in_settore}, "
              f"orario={in_orario})")

        if ora_liv != prima:
            s["livello"] = ora_liv
            cambiato = True

        if ora_liv > prima:
            if not in_orario:
                print(f"[info] bora oltre soglia ma fuori orario "
                      f"({sent['nome']})")
                continue
            liv = BORA_LIVELLI[ora_liv - 1]
            dir_txt = f"{sigla} {freccia(sigla)}".strip()
            corpo = (f"💨 *ALERT BORA — {sent['nome']}*\n"
                     f"{liv['tag']}\n\n"
                     f"Vento *{dati['vento']:.1f} nodi* da {dir_txt} — "
                     f"raffica *{dati['raffica']:.1f} nodi*")
            eta = stima_arrivo_min(sent.get("coord"), sigla, dati["vento"])
            if eta is not None:
                corpo += (f"\n⏱️ Possibile arrivo a Lido di Spina tra "
                          f"{eta_forchetta(eta)}")
            corpo += f"\n{liv['descrizione']}"
            try:
                invia_telegram(corpo)
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio alert bora fallito: {e}")

    return cambiato


# --------------------------------------------------------------------------
# BENVENUTO SERALE AI NUOVI ISCRITTI
# --------------------------------------------------------------------------

def raccogli_nuovi_iscritti(stato: dict) -> bool:
    """Raccoglie i nuovi iscritti al canale (update chat_member del bot).

    Telegram non permette a un bot di elencare gli iscritti di un canale,
    ma un bot admin riceve una notifica quando qualcuno si iscrive. Gli
    update restano disponibili 24 ore: il giro ogni 15 minuti basta con
    largo margine. I nomi finiscono in stato['_benvenuti']['in_attesa']
    per il saluto serale. Ritorna True se lo stato e' cambiato.
    """
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = str(os.environ["TELEGRAM_CHAT_ID"])
    ben = stato.setdefault("_benvenuti", {})
    params = {"timeout": 0, "allowed_updates": json.dumps(["chat_member"])}
    if ben.get("offset"):
        params["offset"] = ben["offset"]
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params=params, timeout=30)
        r.raise_for_status()
        dati = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[errore] getUpdates fallito: {e}")
        return False
    if not dati.get("ok"):
        print(f"[errore] getUpdates: {dati.get('description')}")
        return False

    cambiato = False
    for up in dati["result"]:
        ben["offset"] = max(ben.get("offset", 0), up["update_id"] + 1)
        cambiato = True
        cm = up.get("chat_member")
        if not cm:
            continue
        chat = cm.get("chat", {})
        # Accetto sia l'id numerico sia lo @username del canale.
        se_nostro = (str(chat.get("id")) == chat_id
                     or f"@{chat.get('username', '')}" == chat_id)
        if not se_nostro:
            continue
        vecchio = (cm.get("old_chat_member") or {}).get("status")
        nuovo_m = cm.get("new_chat_member") or {}
        if nuovo_m.get("status") != "member" or vecchio == "member":
            continue  # non e' una nuova iscrizione (es. uscita, promozione)
        utente = nuovo_m.get("user") or {}
        if utente.get("is_bot"):
            continue
        nome = " ".join(p for p in (utente.get("first_name"),
                                    utente.get("last_name")) if p).strip()
        nome = re.sub(r"[*_`\[\]]", "", nome) or "un nuovo velista"
        attesa = ben.setdefault("in_attesa", [])
        if utente.get("id") not in {a.get("id") for a in attesa}:
            attesa.append({"id": utente.get("id"), "nome": nome})
            print(f"[benvenuto] nuovo iscritto in attesa: {nome}")
    return cambiato


def invia_benvenuti(stato: dict, adesso: datetime) -> bool:
    """Alle BENVENUTO_ORA saluta per nome gli iscritti raccolti in giornata.

    Un solo messaggio al giorno, e solo se c'e' almeno un nuovo iscritto.
    Ritorna True se lo stato e' cambiato.
    """
    ben = stato.get("_benvenuti") or {}
    attesa = ben.get("in_attesa") or []
    if not attesa or adesso.hour < BENVENUTO_ORA:
        return False
    oggi = adesso.strftime("%Y-%m-%d")
    if ben.get("data_invio") == oggi:
        return False

    nomi = [f"*{a['nome']}*" for a in attesa]
    if len(nomi) == 1:
        iscritti = f"Oggi si è unito al canale {nomi[0]}."
    else:
        iscritti = ("Oggi si sono uniti al canale "
                    f"{', '.join(nomi[:-1])} e {nomi[-1]}.")
    try:
        invia_telegram(BENVENUTO_TEMPLATE.format(iscritti=iscritti),
                       silenzioso=True)
    except Exception as e:  # noqa: BLE001
        print(f"[errore] invio benvenuto fallito: {e}")
        return False
    ben["data_invio"] = oggi
    ben["in_attesa"] = []
    return True


# --------------------------------------------------------------------------
# CONTROLLO PRESSIONE (workflow separato, sfasato rispetto al vento)
# --------------------------------------------------------------------------

def _eta_min(iso: str, ora: datetime) -> float:
    """Eta' in minuti di una lettura (timestamp ISO) rispetto a `ora`."""
    return (ora - datetime.fromisoformat(iso)).total_seconds() / 60.0


def controlla_pressione(stato: dict, letture: dict | None = None) -> bool:
    """Legge la pressione delle stazioni, aggiorna lo storico e avvisa.

    Tiene in state.json una finestra di letture per stazione, calcola la caduta
    di pressione normalizzata a 3 ore e, al superamento delle soglie, invia un
    avviso Telegram (solo in fascia oraria). Ritorna True se lo stato e'
    cambiato (e va quindi salvato).

    Gira dentro il giro dei 15 minuti, che legge gia' le stazioni: `letture`
    (nome -> dati) evita di interrogarle una seconda volta. Senza `letture`
    se le rilegge da solo, cosi' resta possibile lanciarlo a mano.
    """
    adesso = datetime.now(TZ)
    in_orario = ORA_INIZIO <= adesso.hour < ORA_FINE
    cambiato = False

    for st in STAZIONI:
        nome = st["nome"]
        dati = letture.get(nome) if letture is not None else leggi_stazione(st)
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
# GRAFICO SERALE - andamento del vento della giornata
# --------------------------------------------------------------------------
# Le letture accumulate ogni 15 minuti in stato["_serie"] diventano, all'ora
# del riepilogo, un grafico dell'andamento reale del vento: il complemento
# "a consuntivo" del grafico previsioni weekend.

GRAFICO_GIORNO_MIN_PUNTI = 4  # sotto questa soglia il grafico non dice nulla


def grafico_giornata(serie: dict, adesso: datetime) -> bytes | None:
    """PNG con l'andamento del vento di oggi, o None se dati insufficienti.

    serie: {nome: [["HH:MM", vento, raffica10' | None, direzione], ...]}
    (il quarto campo puo' mancare nelle serie salvate prima di questa
    funzione). Sul grafico, una freccia per ogni ora mostra la direzione di
    PROVENIENZA del vento: la freccia "vola col vento", come le frecce delle
    app meteo (vento da N = freccia che punta in basso).
    Matplotlib viene importato qui dentro: serve una volta al giorno e
    caricarlo a ogni run dei controlli sarebbe uno spreco.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colori = {"Porto Corsini": "#075985", "Lido di Volano": "#d3500a"}
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
    disegnato = False
    frecce = []  # (x, y, u, v, colore): una per ora per stazione
    for nome, punti in serie.items():
        if len(punti) < GRAFICO_GIORNO_MIN_PUNTI:
            continue
        ore = [int(p[0][:2]) + int(p[0][3:]) / 60.0 for p in punti]
        venti = [p[1] for p in punti]
        colore = colori.get(nome)
        ax.plot(ore, venti, label=nome, color=colore, linewidth=2.2)
        raffiche = [p[2] if p[2] is not None else float("nan") for p in punti]
        if any(p[2] is not None for p in punti):
            ax.plot(ore, raffiche, label=f"{nome} — raffica", color=colore,
                    linewidth=1.3, linestyle="--", alpha=0.65)
        # Una freccia di direzione per ogni ora: il primo punto di ogni ora
        # (i run non cadono mai esattamente allo scoccare).
        ora_fatta = set()
        for p, x, y in zip(punti, ore, venti):
            sigla = p[3] if len(p) > 3 else None
            if sigla not in COMPASS or int(x) in ora_fatta:
                continue
            ora_fatta.add(int(x))
            verso = math.radians((COMPASS[sigla] + 180) % 360)
            frecce.append((x, y, math.sin(verso), math.cos(verso), colore))
        disegnato = True
    if not disegnato:
        plt.close(fig)
        return None

    if frecce:
        # Le frecce stanno un po' SOPRA la linea del vento, per non coprirla.
        salto = ax.get_ylim()[1] * 0.06
        xs, ys, us, vs, cs = zip(*frecce)
        ax.quiver(xs, [y + salto for y in ys], us, vs, color=cs,
                  angles="uv", pivot="mid", scale=30, width=0.004,
                  headwidth=4.5, headlength=5, headaxislength=4.5,
                  alpha=0.85, zorder=5)

    # Linee delle soglie d'alert, ma solo quelle vicine ai valori del giorno:
    # con un massimo di 8 nodi tirare l'asse fino a 30 schiaccerebbe tutto.
    ymax = ax.get_ylim()[1]
    for liv in LIVELLI:
        if liv["soglia"] <= ymax + 2:
            ax.axhline(liv["soglia"], color="#a51818", linewidth=0.8,
                       linestyle=":", alpha=0.6)
            ax.annotate(f"{liv['soglia']:.0f} nodi", xy=(1.0, liv["soglia"]),
                        xycoords=("axes fraction", "data"),
                        xytext=(-4, 3), textcoords="offset points",
                        ha="right", fontsize=8, color="#a51818", alpha=0.8)

    ax.set_title(f"Vento di oggi — {adesso:%d/%m/%Y}", fontsize=13,
                 fontweight="bold", color="#12384f")
    ax.set_ylabel("nodi")
    ax.set_xlabel("ora")
    ax.set_xlim(ORA_INIZIO, ORA_FINE)
    ax.set_xticks(range(ORA_INIZIO, ORA_FINE + 1))
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()

    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


# --------------------------------------------------------------------------
# ARCHIVIO STORICO - un CSV per anno con tutte le letture della stagione
# --------------------------------------------------------------------------
# La serie giornaliera viene azzerata ogni notte: prima di buttarla via la
# accodo a storico/<anno>.csv (committato dal workflow come state.json).
# Il canale conserva i grafici, questo file conserva i numeri: e' la materia
# prima per le statistiche stagionali (giorni uscibili, profilo orario della
# brezza, rosa dei venti, previsto-vs-reale...).

STORICO_DIR = Path(__file__).with_name("storico")


def archivia_serie(serie: dict, data: str) -> None:
    """Accoda le letture di una giornata al CSV storico dell'anno.

    Una riga per lettura: data, ora, stazione, vento, raffica 10' (vuota se
    non disponibile), direzione di provenienza. Idempotente per giornata: la
    chiama solo il reset giornaliero, che poi azzera la serie.
    """
    if not serie or not data:
        return
    percorso = STORICO_DIR / f"{data[:4]}.csv"
    STORICO_DIR.mkdir(exist_ok=True)
    nuovo = not percorso.exists()
    with percorso.open("a", encoding="utf-8") as f:
        if nuovo:
            f.write("data,ora,stazione,vento_nodi,raffica10_nodi,direzione\n")
        for nome, punti in serie.items():
            for p in punti:
                raffica = ("" if len(p) < 3 or p[2] is None else f"{p[2]}")
                direzione = p[3] if len(p) > 3 and p[3] else ""
                f.write(f"{data},{p[0]},{nome},{p[1]},{raffica},{direzione}\n")
    n = sum(len(v) for v in serie.values())
    print(f"[ok] archivio storico: {n} letture del {data} in {percorso.name}")


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
    # Se accanto allo script c'e' annuncio_foto.png, dopo il testo viene
    # inviata anche la foto (didascalia opzionale in annuncio_foto.txt):
    # per allegare un'immagine basta committarla, per non allegarla toglierla.
    if os.environ.get("INVIA_ANNUNCIO", "").lower() in ("1", "true", "yes"):
        testo = Path(__file__).with_name("annuncio.md").read_text(
            encoding="utf-8").strip()
        if not testo:
            print("[info] annuncio.md vuoto: nessun invio.")
            return 0
        foto = Path(__file__).with_name("annuncio_foto.png")
        didascalia_file = Path(__file__).with_name("annuncio_foto.txt")
        try:
            invia_telegram(testo)
            if foto.exists():
                didascalia = ""
                if didascalia_file.exists():
                    didascalia = didascalia_file.read_text(
                        encoding="utf-8").strip()
                invia_foto(foto.read_bytes(), didascalia)
        except Exception as e:  # noqa: BLE001
            print(f"[errore] invio annuncio fallito: {e}")
            return 1
        return 0

    # Modalita' pulizia: svuota SUBITO il canale (tutto, fino a questo momento)
    # e termina. Usata dal pulsante manuale (workflow_dispatch) come reset a
    # richiesta. A differenza della pulizia giornaliera, qui cancello anche i
    # messaggi di oggi e di ieri perche' e' un'azione esplicita e voluta ora.
    # I riepiloghi serali restano comunque intoccabili (archivio storico).
    if os.environ.get("PULIZIA_CANALE", "").lower() in ("1", "true", "yes"):
        stato = carica_stato()
        try:
            adesso = id_corrente_canale()
            pulizia_canale(stato.get("_pulito_fino_a", 0), adesso,
                           salva=stato.get("_riepilogo_ids", []))
            stato["_pulito_fino_a"] = adesso
            stato["_ultimo_id"] = adesso
            stato["_id_fine_ieri"] = adesso  # niente da oggi da preservare
        except Exception as e:  # noqa: BLE001
            print(f"[errore] pulizia canale fallita: {e}")
            return 1
        salva_stato(stato)
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
        bora = leggi_bora()
        for sent in BORA_SENTINELLE:
            dati = bora.get(sent["id"])
            if dati is None:
                righe.append(f"\n*{sent['nome']}* (sentinella bora): "
                             "dati non disponibili")
                continue
            righe.append(
                f"\n💨 *{sent['nome']}* (sentinella bora)\n"
                f"Vento {dati['vento']:.1f} nodi da {_dir16(dati['gradi'])}"
                f" — raffica {dati['raffica']:.1f} nodi"
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
        # Prima di azzerare la serie, la accodo al CSV storico: e' l'unico
        # punto in cui i numeri della giornata stanno per sparire.
        try:
            archivia_serie(stato.get("_serie") or {}, stato.get("_data") or "")
        except Exception as e:  # noqa: BLE001
            print(f"[errore] archivio storico fallito: {e}")
        stato["_data"] = oggi
        for st in STAZIONI:
            s = stato.setdefault(st["nome"], {})
            s["vento_max"] = 0.0
            s["raffica_max"] = 0.0
            s.pop("vento_prec", None)
        stato.pop("_serie", None)  # serie del grafico serale: riparte da zero
        # Fotografo i confini per la pulizia giornaliera: "fine di ieri"
        # scala a "fine dell'altroieri", e l'ultimo id inviato finora diventa
        # il nuovo "fine di ieri". (Primo run del giorno: qui non e' ancora
        # stato inviato nulla, quindi _ultimo_id e' quello di ieri.)
        stato["_id_fine_altroieri"] = stato.get("_id_fine_ieri", 0)
        stato["_id_fine_ieri"] = stato.get("_ultimo_id", 0)
        cambiato = True

    # --- Pulizia giornaliera: al PRIMO RUN DOPO MEZZANOTTE (subito dopo il
    # rollover qui sopra), cancella i messaggi dal PENULTIMO giorno
    # all'indietro: restano nel canale oggi e ieri (confine
    # _id_fine_altroieri), cosi' gli iscritti non si ritrovano la chat
    # intasata. ECCEZIONE: i riepiloghi serali (_riepilogo_ids) non si
    # cancellano MAI — restano come archivio storico con i loro grafici.
    # Imposto il flag _pulizia in OGNI caso (anche se qualcosa va storto)
    # cosi' NON si ripete durante la giornata.
    #
    # PERCHE' A MEZZANOTTE E NON ALLE 9 (bug del 30/07/2026): Telegram non
    # lascia cancellare a un bot i messaggi oltre le 48 ORE. Alle 9:00 il
    # primo messaggio dell'altroieri (il bollettino delle 9:00) ne ha
    # esattamente 48 e finiva oltre il limite per pochi secondi: la chiamata
    # e' atomica, quindi bastava quel messaggio a far rifiutare l'intero
    # blocco e nel canale non si cancellava piu' niente. A mezzanotte i
    # messaggi da cancellare hanno fra le 27 e le 39 ore: 9 ore di margine.
    if stato.get("_pulizia") != oggi:
        ceiling = stato.get("_id_fine_altroieri", 0)
        try:
            rimasti = pulizia_canale(stato.get("_pulito_fino_a", 0), ceiling,
                                     salva=stato.get("_riepilogo_ids", []))
            stato["_pulito_fino_a"] = max(stato.get("_pulito_fino_a", 0),
                                          ceiling)
            if rimasti:
                # Oltre le 48 ore non si recuperano piu': lo dico all'admin,
                # che puo' toglierli a mano dall'app.
                stato["_non_cancellati"] = sorted(
                    set(stato.get("_non_cancellati", [])) | set(rimasti))[-500:]
                try:
                    invia_telegram_admin(
                        f"🧹 Pulizia canale: {len(rimasti)} messaggi NON "
                        f"cancellabili (id {min(rimasti)}-{max(rimasti)}). "
                        f"Telegram non lascia cancellare a un bot i messaggi "
                        f"oltre le 48 ore: vanno tolti a mano dall'app.")
                except Exception as e:  # noqa: BLE001
                    print(f"[errore] avviso admin pulizia fallito: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[errore] pulizia canale fallita: {e}")
        stato["_pulizia"] = oggi
        cambiato = True

    # --- Bollettino mattutino: una volta al giorno, in mattinata ---
    # Esce TUTTI i giorni (giovedi' compreso): il grafico previsioni weekend
    # (grafico_settimanale.py, gio-ven-sab alle 9:05) ora mostra solo i giorni
    # FUTURI, quindi non duplica piu' il giorno di oggi.
    if (stato.get("_bollettino") != oggi
            and ORA_INIZIO <= adesso.hour < ORA_INIZIO + 3):
        msg = bollettino_mattutino(stato)
        if msg:
            try:
                invia_telegram(msg, silenzioso=True)
                stato["_bollettino"] = oggi
                cambiato = True
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio bollettino fallito: {e}")

    # Il bollettino periodico stazioni esce una volta per "slot" di un quarto
    # d'ora (:00-:14 / :15-:29 / :30-:44 / :45-:59) in fascia oraria. Lo calcolo
    # PRIMA del giro sulle stazioni.
    slot = None
    bollettino_dovuto = False
    if in_orario:
        slot = f"{oggi} {adesso.hour:02d}{'ABCD'[adesso.minute // 15]}"
        bollettino_dovuto = stato.get("_stazioni_slot") != slot

    letture = {}          # nome -> dati (o None): serve al bollettino periodico
    tendenze = {}         # nome -> tendenza (📈/➖/📉) per il bollettino
    messaggi_alert = []   # avvisi vento/raffica pronti da inviare a se' stanti
    for st in STAZIONI:
        nome = st["nome"]
        dati = leggi_stazione(st)
        letture[nome] = dati
        if watchdog_stazione(stato, nome, dati is not None, adesso, in_orario):
            cambiato = True
        if dati is None:
            continue  # non tocco lo stato se non riesco a leggere

        vento = dati["vento"]
        direzione = dati["direzione"]
        raffica = dati["raffica"]
        s = stato.setdefault(nome, {})

        livello_prima = s.get("livello", 0)
        livello_ora = calcola_livello(vento, livello_prima, LIVELLI)

        # Per l'alert raffica preferisco la raffica degli ultimi 10 minuti
        # (dalla stazione di riserva GCA, se disponibile): e' un dato attuale,
        # quindi il livello si riarma quando il vento cala e puo' riscattare
        # nella stessa giornata. La massima giornaliera resta il ripiego.
        raffica_alert = dati.get("raffica_10min")
        if raffica_alert is None:
            raffica_alert = raffica
        raf_prima = s.get("livello_raffica", 0)
        raf_ora = (calcola_livello(raffica_alert, raf_prima, RAFFICA_LIVELLI)
                   if raffica_alert is not None else raf_prima)

        # Tendenza rispetto al bollettino precedente (solo in orario attivo).
        vento_prec = s.get("vento_prec")
        tendenza = None
        if in_orario and vento_prec is not None:
            delta = vento - vento_prec
            tendenza = ("📈 in aumento" if delta >= 1
                        else "📉 in calo" if delta <= -1
                        else "➖ stazionario")

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
            # Serie del giorno per il grafico serale: come raffica uso quella
            # degli ultimi 10 minuti (dato attuale); la massima giornaliera
            # non ha senso in un grafico orario. La direzione serve per le
            # frecce di provenienza disegnate ora per ora sul grafico.
            raf10 = dati.get("raffica_10min")
            stato.setdefault("_serie", {}).setdefault(nome, []).append(
                [f"{adesso:%H:%M}", round(vento, 1),
                 round(raf10, 1) if raf10 is not None else None,
                 direzione])
            cambiato = True

        # Direzione "verso il circolo": True se il vento arriva da un settore
        # che spinge verso Lido di Spina (semicerchio sud per Porto Corsini,
        # nord per Volano). Vale sia per l'avviso vento sia per l'alert raffica.
        direzioni_ok = (st["direzioni"] is None
                        or direzione in st["direzioni"])

        tendenze[nome] = tendenza

        # Stima di arrivo al circolo, usata nel messaggio ALERT VENTO qui
        # sotto (solo se il livello e' salito e la direzione punta verso il
        # circolo).
        eta_txt = None
        if direzioni_ok and livello_ora >= 1:
            eta = stima_arrivo_min(st.get("coord"), direzione, vento)
            if eta is not None:
                eta_txt = eta_forchetta(eta)

        # --- ALERT VENTO: solo quando il livello SALE (e direzione OK). E'
        # sempre un messaggio a se' stante, mai confluito nel bollettino: vedi
        # invio ritardato di un minuto piu' sotto. ---
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
                # Vento a strappi: se la raffica degli ultimi 10 minuti
                # supera di molto la media (rapporto >= RAFFICOSO_FATTORE),
                # il vento e' irregolare — condizione insidiosa in deriva
                # anche quando la media non spaventa.
                raf10 = dati.get("raffica_10min")
                if (raf10 is not None and vento >= 8
                        and raf10 / vento >= RAFFICOSO_FATTORE):
                    corpo += ("\n💨 _Vento irregolare: raffiche ben sopra "
                              "la media_")
                if eta_txt is not None:
                    corpo += (f"\n⏱️ Possibile arrivo al circolo tra "
                              f"{eta_txt}")
                messaggi_alert.append(corpo)
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
                         f"La raffica ha raggiunto *{raffica_alert:.1f} nodi* "
                         f"(soglia {soglia:.0f}) da {dir_txt}.")
                messaggi_alert.append(testo)
            else:
                motivo = "fuori orario" if not in_orario else "direzione esclusa"
                print(f"[info] soglia raffica superata ma avviso non inviato "
                      f"({motivo})")

    # --- ALERT BORA: sentinelle CPSM a nord-est. Indipendente dalle stazioni
    # locali: la bora va segnalata appena si vede sulle sentinelle, quindi
    # parte sempre come messaggio a se' stante (non confluisce nel bollettino).
    if controlla_bora(stato, in_orario):
        cambiato = True

    # --- Benvenuto ai nuovi iscritti: raccolti a ogni giro (il workflow gira
    # tutto il giorno), salutati per nome in un unico messaggio serale.
    if raccogli_nuovi_iscritti(stato):
        cambiato = True
    if invia_benvenuti(stato, adesso):
        cambiato = True

    # --- Bollettino periodico stazioni: una volta ogni 15 minuti, in fascia
    # oraria, SEMPRE (anche a dati invariati) perche' la situazione vento in
    # tempo reale interessa ai soci. Box snello: solo vento, direzione e
    # tendenza rispetto al bollettino precedente. Gli alert vento/raffica non
    # confluiscono piu' qui: partono come messaggi a se' stanti (vedi sotto),
    # cosi' restano ben visibili. ---
    bollettino_inviato = False
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
            dir_txt = f"{dati['direzione']} {freccia(dati['direzione'])}".strip()
            blocco = [f"🌬️ *{nome}*",
                      f"Vento *{dati['vento']:.1f} nodi* da {dir_txt}"]
            tnd = tendenze.get(nome)
            if tnd:
                blocco.append(tnd)
            righe.append("\n" + "\n".join(blocco))
        # Corrente e marea "adesso", a ogni giro: una riga sola, leggibile
        # al volo su telefono o smartwatch mentre si naviga.
        riga = riga_corrente(stato)
        if riga:
            righe.append("\n" + riga)
        # Alle 14:00 (primo slot dell'ora) si aggiunge la MEDIA prevista per
        # il pomeriggio: spesso il vento del mattino e' debole e si esce al
        # pomeriggio, e a quest'ora il run Adriac di oggi e' gia' pubblicato.
        if adesso.hour == 14 and slot.endswith("A"):
            pomeriggio = riga_corrente_pomeriggio(stato)
            if pomeriggio:
                # Sta attaccata alla riga della corrente, di cui e' il
                # seguito; se quella manca, apre lei il blocco.
                righe.append(pomeriggio if riga else "\n" + pomeriggio)
        if almeno_uno:
            try:
                # Con notifica sonora, come gli ALERT: la situazione vento e'
                # il contenuto principale del canale per i soci.
                invia_telegram("\n".join(righe))
                stato["_stazioni_slot"] = slot
                cambiato = True
                bollettino_inviato = True
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio bollettino stazioni fallito: {e}")

    # --- Alert vento/raffica: messaggi a se' stanti, con un box tutto loro
    # per farli risaltare. Se in questo run e' uscito anche il bollettino
    # stazioni, li pubblico un minuto dopo, cosi' arrivano in sequenza chiara
    # (prima la situazione vento, poi l'eventuale alert). ---
    if messaggi_alert:
        if bollettino_inviato:
            time.sleep(60)
        for testo in messaggi_alert:
            try:
                invia_telegram(testo)
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio Telegram alert fallito: {e}")

    # --- Pressione: stessa cadenza dei 15 minuti, sulle letture gia' fatte.
    # Gira anche fuori fascia oraria (senza mandare niente): la tendenza si
    # misura su 3 ore, quindi lo storico della notte serve ad avere gia' una
    # baseline valida alle 9:00. L'eventuale alert esce per ultimo, dopo la
    # situazione vento e gli alert di vento e raffica. ---
    if controlla_pressione(stato, letture):
        cambiato = True

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
            righe.append("💡 Suggerimenti o errori da segnalare? "
                         "Scrivi a zenogovoni@annunziata.it")
            righe.append("⛵ Buona serata!")
            # Il riepilogo viaggia come didascalia del grafico della giornata:
            # un solo messaggio con numeri e andamento. Se il grafico non si
            # puo' fare (dati troppo scarsi o matplotlib assente), testo e
            # basta come prima.
            png = None
            try:
                png = grafico_giornata(stato.get("_serie") or {}, adesso)
            except Exception as e:  # noqa: BLE001
                print(f"[errore] grafico giornata fallito: {e}")
            try:
                if png:
                    mid = invia_foto(png, "\n".join(righe), silenzioso=True)
                else:
                    mid = invia_telegram("\n".join(righe), silenzioso=True)
                # Il riepilogo non va MAI cancellato dalla pulizia: archivio
                # storico per statistiche future (vedi pulizia_canale).
                if mid:
                    stato.setdefault("_riepilogo_ids", []).append(mid)
            except Exception as e:  # noqa: BLE001
                print(f"[errore] invio riepilogo fallito: {e}")
        stato["_riepilogo"] = oggi
        cambiato = True

    # Tengo aggiornato l'id piu' recente inviato: e' il confine che domani
    # diventera' _id_fine_ieri (vedi reset giornaliero e pulizia giornaliera).
    if _ULTIMO_MSG_ID > stato.get("_ultimo_id", 0):
        stato["_ultimo_id"] = _ULTIMO_MSG_ID
        cambiato = True

    if cambiato:
        salva_stato(stato)

    return 0


if __name__ == "__main__":
    sys.exit(main())
