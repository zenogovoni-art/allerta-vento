#!/usr/bin/env python3
"""
Grafico previsioni vento per il weekend, inviato sul canale Telegram.

Pensato per girare il GIOVEDI' mattina: genera un istogramma con la velocita'
massima del vento prevista per i prossimi giorni (da oggi fino alla domenica
inclusa) in due localita' -- Porto Corsini (sud) e Lido di Volano (nord) --
con sopra ogni barra una freccia che indica la direzione dominante del vento.

I dati vengono dalla previsione giornaliera di Open-Meteo (stessa fonte del
bollettino mattutino di meteo_check.py). Niente raffiche: a qualche giorno di
distanza sono troppo aleatorie, mostriamo solo la velocita' max e la direzione.

Variabili d'ambiente richieste:
    TELEGRAM_TOKEN    token del bot (da @BotFather)
    TELEGRAM_CHAT_ID  id della chat/canale a cui inviare l'immagine
"""

import io
import math
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")  # nessun display sui runner di GitHub Actions
import matplotlib.pyplot as plt
import requests

# --------------------------------------------------------------------------
# CONFIGURAZIONE
# --------------------------------------------------------------------------

TZ = ZoneInfo("Europe/Rome")

# Localita' da confrontare: stesso ordine = stesso colore in tutto il grafico.
#   coord -> (lat, lon) usate per interrogare la previsione Open-Meteo
#   colore -> colore della barra
LOCALITA = [
    {"nome": "Porto Corsini", "coord": (44.493, 12.279), "colore": "#1f6fb4"},  # blu
    {"nome": "Lido di Volano", "coord": (44.797, 12.268), "colore": "#c0392b"},  # rosso
]

# Numero massimo di giorni da mostrare partendo da oggi (cap di sicurezza).
MAX_GIORNI = 7

GIORNI_IT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
GIORNI_IT_LUNGHI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
                    "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


# --------------------------------------------------------------------------
# PREVISIONE
# --------------------------------------------------------------------------

def previsione_giornaliera(coord, giorni: int):
    """Velocita' max (nodi) e direzione dominante (gradi) per i prossimi giorni.

    Ritorna due liste parallele (velocita, direzioni) lunghe `giorni`, oppure
    (None, None) se la richiesta fallisce.
    """
    lat, lon = coord
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&daily=wind_speed_10m_max,wind_direction_10m_dominant"
           "&wind_speed_unit=kn&timezone=Europe/Rome"
           f"&forecast_days={giorni}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        d = r.json()["daily"]
        return d["wind_speed_10m_max"], d["wind_direction_10m_dominant"]
    except (requests.RequestException, KeyError, ValueError) as e:
        print(f"[errore] previsione non disponibile per {coord}: {e}")
        return None, None


def giorni_da_mostrare(oggi: datetime) -> int:
    """Quanti giorni mostrare: da oggi fino alla domenica inclusa.

    Giovedi' -> 4 giorni (gio, ven, sab, dom). Se lanciato in un altro giorno
    si adatta da solo (es. venerdi' -> 3). Cap a MAX_GIORNI.
    """
    fino_a_domenica = (6 - oggi.weekday()) + 1  # +1 per includere oggi
    return max(1, min(fino_a_domenica, MAX_GIORNI))


# --------------------------------------------------------------------------
# GRAFICO
# --------------------------------------------------------------------------

def _dxdy_verso_dove_soffia(dir_provenienza_gradi: float):
    """Versore (dx, dy) nella direzione VERSO CUI soffia il vento.

    Open-Meteo da' la direzione DA CUI proviene il vento (convenzione meteo).
    Il vento si muove verso l'opposto: aggiungiamo 180 gradi. Bussola: 0=N (su),
    90=E (destra), quindi dx=sin, dy=cos. Coerente con la freccia di meteo_check.
    """
    rotta = math.radians((dir_provenienza_gradi + 180) % 360)
    return math.sin(rotta), math.cos(rotta)


def costruisci_grafico(etichette_giorni, dati, oggi: datetime) -> bytes:
    """Crea l'istogramma e lo restituisce come PNG in memoria (bytes).

    etichette_giorni -> lista di stringhe sull'asse x (es. ['gio 12', ...])
    dati             -> lista (parallela a LOCALITA) di liste di velocita' nodi
    """
    n_giorni = len(etichette_giorni)
    n_loc = len(LOCALITA)
    x = list(range(n_giorni))
    larghezza = 0.8 / n_loc

    fig, ax = plt.subplots(figsize=(1.7 * n_giorni + 1.5, 5.2), dpi=130)

    vmax = max((v for d in dati for v in d["velocita"]), default=0) or 1

    # Raccogliamo le frecce e le disegniamo DOPO aver fissato i limiti, cosi'
    # la conversione in pixel (sotto) usa la scala definitiva degli assi.
    frecce = []  # (px, ay, dx, dy, colore)
    for j, loc in enumerate(LOCALITA):
        offset = (j - (n_loc - 1) / 2) * larghezza
        posizioni = [xi + offset for xi in x]
        velocita = dati[j]["velocita"]
        direzioni = dati[j]["direzioni"]
        ax.bar(posizioni, velocita, width=larghezza,
               color=loc["colore"], label=loc["nome"], zorder=3)

        for px, v, dirg in zip(posizioni, velocita, direzioni):
            # numero (nodi) appena sopra la barra
            ax.text(px, v + vmax * 0.02, f"{v:.0f}", ha="center", va="bottom",
                    fontsize=9, color=loc["colore"], fontweight="bold")
            dx, dy = _dxdy_verso_dove_soffia(dirg)
            frecce.append((px, v + vmax * 0.13, dx, dy, loc["colore"]))

    ax.set_xticks(x)
    ax.set_xticklabels(etichette_giorni, fontsize=11)
    ax.set_ylabel("Vento max (nodi)", fontsize=11)
    ax.set_ylim(0, vmax * 1.30)
    ax.set_xlim(-0.5, n_giorni - 0.5)

    # Frecce a lunghezza fissa in pixel (angolo corretto a prescindere dalla
    # scala degli assi): convertiamo il centro in pixel, applichiamo l'offset
    # e torniamo in coordinate-dati per annotate.
    trans = ax.transData
    inv = trans.inverted()
    half_px = 16  # mezza lunghezza della freccia, in pixel
    for px, ay, dx, dy, colore in frecce:
        cx, cy = trans.transform((px, ay))
        testa = inv.transform((cx + dx * half_px, cy + dy * half_px))
        coda = inv.transform((cx - dx * half_px, cy - dy * half_px))
        ax.annotate("", xy=testa, xytext=coda,
                    arrowprops=dict(arrowstyle="-|>", color=colore, lw=2),
                    zorder=4)
    ax.set_title(f"Previsioni vento per il weekend — Lido di Spina\n"
                 f"{GIORNI_IT_LUNGHI[oggi.weekday()]} {oggi.day} "
                 f"{MESI_IT[oggi.month - 1]}",
                 fontsize=13, fontweight="bold")
    ax.legend(loc="best", fontsize=10, framealpha=0.9)
    ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.text(0.5, 0.01,
             "Freccia = direzione verso cui soffia il vento · "
             "previsione Open-Meteo, indicativa",
             ha="center", fontsize=8, color="gray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


# --------------------------------------------------------------------------
# TELEGRAM
# --------------------------------------------------------------------------

def invia_foto(png: bytes, didascalia: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    r = requests.post(
        url,
        data={"chat_id": chat_id, "caption": didascalia,
              "parse_mode": "Markdown"},
        files={"photo": ("previsioni_weekend.png", png, "image/png")},
        timeout=60,
    )
    r.raise_for_status()
    print("[ok] grafico inviato su Telegram")


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main() -> int:
    oggi = datetime.now(TZ)
    n = giorni_da_mostrare(oggi)

    etichette = [f"{GIORNI_IT[(oggi + timedelta(days=i)).weekday()]} "
                 f"{(oggi + timedelta(days=i)).day}" for i in range(n)]

    dati = []
    for loc in LOCALITA:
        vel, dirs = previsione_giornaliera(loc["coord"], n)
        if vel is None:
            print(f"[errore] niente dati per {loc['nome']}, esco.")
            return 1
        dati.append({"velocita": vel[:n], "direzioni": dirs[:n]})

    png = costruisci_grafico(etichette, dati, oggi)

    # In locale (senza token) salva un file da guardare invece di inviare.
    if not os.environ.get("TELEGRAM_TOKEN"):
        out = "previsioni_weekend.png"
        with open(out, "wb") as f:
            f.write(png)
        print(f"[locale] nessun TELEGRAM_TOKEN: grafico salvato in {out}")
        return 0

    didascalia = ("🌬️ *Previsioni vento per il weekend* — Lido di Spina\n"
                  "Velocità massima e direzione, "
                  "blu Porto Corsini · rosso Lido di Volano.")
    try:
        invia_foto(png, didascalia)
    except Exception as e:  # noqa: BLE001
        print(f"[errore] invio grafico fallito: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
