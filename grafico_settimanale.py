#!/usr/bin/env python3
"""
Grafico previsioni vento per il weekend a Lido di Spina, inviato sul canale.

Pensato per girare il GIOVEDI' mattina: genera un istogramma con la velocita'
massima del vento prevista per i prossimi giorni (da oggi fino alla domenica
inclusa) a Lido di Spina, con sopra ogni barra una freccia che indica la
direzione dominante del vento.

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
import time
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

# Coordinate del punto di previsione: Lido di Spina (44°38'37.1"N 12°15'22.5"E).
LIDO_SPINA = (44.6436, 12.2563)
COLORE = "#1f6fb4"  # blu

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
    # Open-Meteo ogni tanto cade in handshake/timeout dai runner: riproviamo
    # qualche volta con una breve pausa crescente prima di arrenderci.
    tentativi = 4
    for n in range(1, tentativi + 1):
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            d = r.json()["daily"]
            return d["wind_speed_10m_max"], d["wind_direction_10m_dominant"]
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"[tentativo {n}/{tentativi}] previsione non disponibile "
                  f"per {coord}: {e}")
            if n < tentativi:
                time.sleep(5 * n)  # 5s, 10s, 15s
    print(f"[errore] previsione non disponibile per {coord} dopo {tentativi} "
          f"tentativi")
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


def costruisci_grafico(etichette_giorni, velocita, direzioni,
                       oggi: datetime) -> bytes:
    """Crea l'istogramma e lo restituisce come PNG in memoria (bytes)."""
    n_giorni = len(etichette_giorni)
    x = list(range(n_giorni))

    fig, ax = plt.subplots(figsize=(1.7 * n_giorni + 1.5, 5.2), dpi=130)

    vmax = max(velocita, default=0) or 1

    ax.bar(x, velocita, width=0.6, color=COLORE, zorder=3)

    # Raccogliamo le frecce e le disegniamo DOPO aver fissato i limiti, cosi'
    # la conversione in pixel (sotto) usa la scala definitiva degli assi.
    frecce = []  # (px, ay, dx, dy)
    for px, v, dirg in zip(x, velocita, direzioni):
        # numero (nodi) appena sopra la barra
        ax.text(px, v + vmax * 0.02, f"{v:.0f}", ha="center", va="bottom",
                fontsize=11, color=COLORE, fontweight="bold")
        dx, dy = _dxdy_verso_dove_soffia(dirg)
        frecce.append((px, v + vmax * 0.15, dx, dy))

    ax.set_xticks(x)
    ax.set_xticklabels(etichette_giorni, fontsize=12)
    ax.set_ylabel("Vento max (nodi)", fontsize=11)
    ax.set_ylim(0, vmax * 1.32)
    ax.set_xlim(-0.5, n_giorni - 0.5)
    ax.set_title(f"Previsioni vento per il weekend — Lido di Spina\n"
                 f"{GIORNI_IT_LUNGHI[oggi.weekday()]} {oggi.day} "
                 f"{MESI_IT[oggi.month - 1]}",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="y", linestyle=":", alpha=0.5, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Frecce a lunghezza fissa in pixel (angolo corretto a prescindere dalla
    # scala degli assi): convertiamo il centro in pixel, applichiamo l'offset
    # e torniamo in coordinate-dati per annotate.
    trans = ax.transData
    inv = trans.inverted()
    half_px = 18  # mezza lunghezza della freccia, in pixel
    for px, ay, dx, dy in frecce:
        cx, cy = trans.transform((px, ay))
        testa = inv.transform((cx + dx * half_px, cy + dy * half_px))
        coda = inv.transform((cx - dx * half_px, cy - dy * half_px))
        ax.annotate("", xy=testa, xytext=coda,
                    arrowprops=dict(arrowstyle="-|>", color=COLORE, lw=2.2),
                    zorder=4)

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

    vel, dirs = previsione_giornaliera(LIDO_SPINA, n)
    if vel is None:
        print("[errore] niente dati di previsione, esco.")
        return 1
    vel, dirs = vel[:n], dirs[:n]

    png = costruisci_grafico(etichette, vel, dirs, oggi)

    # In locale (senza token) salva un file da guardare invece di inviare.
    if not os.environ.get("TELEGRAM_TOKEN"):
        out = "previsioni_weekend.png"
        with open(out, "wb") as f:
            f.write(png)
        print(f"[locale] nessun TELEGRAM_TOKEN: grafico salvato in {out}")
        return 0

    didascalia = ("🌬️ *Previsioni vento per il weekend* — Lido di Spina\n"
                  "Velocità massima e direzione del vento prevista, "
                  "giorno per giorno.")
    try:
        invia_foto(png, didascalia)
    except Exception as e:  # noqa: BLE001
        print(f"[errore] invio grafico fallito: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
