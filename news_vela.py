#!/usr/bin/env python3
"""3 NEWS DI VELA — rubrica quotidiana per il canale Telegram INFO VENTO.

Ogni giorno alle 10:20 (via cron-job.org -> workflow_dispatch, come il
grafico weekend), in stagione velica (maggio-settembre), pubblica un
messaggio SILENZIOSO con tre notizie da leggere in spiaggia:

  1. BARCHE E PROGETTI  - l'articolo piu' fresco sulle nuove barche A VELA
                          (filtro anti-motore) dai feed RSS di Giornale
                          della Vela e Farevela;
  2. TECNICA & REGATE   - articolo fresco di tecnica o regate dai feed;
                          se non ce n'e' uno nuovo, una voce della libreria
                          curata dati/tecnica.json (rotazione);
  3. IL NODO DEL GIORNO - una voce della libreria dati/nodi.json
                          (rotazione), con link all'animazione passo-passo.

Stato in state.json (chiave "_news3"): link gia' usati (anti-doppioni),
indici di rotazione delle librerie, data dell'ultimo invio (max 1 al giorno).

Variabili d'ambiente:
  TELEGRAM_TOKEN / TELEGRAM_CHAT_ID  - credenziali canale (come meteo_check)
  NEWS_DRY_RUN=1   - stampa il messaggio senza inviare e senza toccare lo stato
  NEWS_FORZA=1     - ignora stagione e flag giornaliero (per i test)
"""

import json
import os
import re
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Rome")
STATO_FILE = Path(__file__).with_name("state.json")
DATI_DIR = Path(__file__).with_name("dati")

MESE_INIZIO, MESE_FINE = 5, 9  # stagione velica, come il resto del canale

# I siti delle testate rifiutano i client "da bot": serve uno User-Agent
# da browser (verificato: con questo rispondono 200).
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0 Safari/537.36")}

FEEDS = [
    "https://www.giornaledellavela.com/feed/",
    "https://www.farevela.net/feed/",
]

# Categorie dei feed che alimentano le due sezioni "fresche".
CAT_BARCHE = {"barche test & cantieri", "barche"}
CAT_TECNICA_REGATE = {"tecnica&accessori", "tecnica accessori&pratica",
                      "regate&sport", "regate", "olimpiadi", "altura",
                      "derive", "america's cup", "classe olimpica"}

# Filtro SOLO VELA: se una di queste parole compare nel titolo o nelle
# categorie, l'articolo viene scartato (il feed GdV mescola anche motore).
PAROLE_MOTORE = ["gommon", "tender", "motoscaf", "fuoribordo", "entrobordo",
                 "motor yacht", "motoryacht", "trawler", " a motore",
                 "barche a motore", "chartering a motore"]

GIORNI_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
             "sabato", "domenica"]
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
           "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

MAX_USATI = 80          # quanti link "gia' visti" ricordare
MAX_RIGHE_DESC = 200    # lunghezza massima della spiegazione (caratteri)


# --------------------------------------------------------------------------
# FEED RSS
# --------------------------------------------------------------------------

def _campo(blocco: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>",
                  blocco, re.S)
    return unescape(m.group(1).strip()) if m else ""


def leggi_feed(url: str) -> list:
    """Voci di un feed RSS: titolo, link, categorie, descrizione, data."""
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    voci = []
    for blocco in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        desc = re.sub(r"<[^>]+>", " ", _campo(blocco, "description"))
        desc = re.sub(r"\s+", " ", desc)
        # via la coda standard di WordPress ("The post ... appeared first on")
        desc = re.sub(r"The post .*$", "", desc).replace("[…]", "").strip()
        try:
            quando = parsedate_to_datetime(_campo(blocco, "pubDate"))
        except (ValueError, TypeError):
            quando = None
        voci.append({
            "titolo": _campo(blocco, "title"),
            "link": _campo(blocco, "link"),
            "cats": [c.lower() for c in re.findall(
                r"<category><!\[CDATA\[(.*?)\]\]></category>", blocco)],
            "desc": desc,
            "quando": quando,
        })
    return voci


def voci_feed_ordinate() -> list:
    """Tutte le voci di tutti i feed, dalla piu' recente. Feed giu' = pazienza."""
    voci = []
    for url in FEEDS:
        try:
            voci.extend(leggi_feed(url))
        except Exception as e:  # noqa: BLE001
            print(f"[avviso] feed non raggiungibile ({url}): {e}")
    vecchia = datetime(1970, 1, 1, tzinfo=TZ)
    voci.sort(key=lambda v: v["quando"] or vecchia, reverse=True)
    return voci


def sa_di_motore(voce: dict) -> bool:
    testo = (voce["titolo"] + " " + " ".join(voce["cats"])).lower()
    return any(p in testo for p in PAROLE_MOTORE)


def scegli_fresca(voci, categorie, usati, esclusi=()):
    """La voce piu' recente della categoria giusta, mai usata, solo vela."""
    for v in voci:
        if (v["link"] and v["link"] not in usati and v["link"] not in esclusi
                and any(c in categorie for c in v["cats"])
                and not sa_di_motore(v)):
            return v
    return None


# --------------------------------------------------------------------------
# COMPOSIZIONE
# --------------------------------------------------------------------------

def pulisci(testo: str) -> str:
    """Niente caratteri che rompono il Markdown di Telegram."""
    return re.sub(r"[*_`\[\]]", "", testo).strip()


def righe_desc(desc: str) -> str:
    """Accorcia la descrizione del feed a 1-2 righe pulite."""
    desc = pulisci(desc)
    # via l'eventuale "Citta'-" iniziale degli articoli di agenzia
    desc = re.sub(r"^[A-Za-zÀ-ù' ]{2,20}– ?", "", desc)
    if len(desc) > MAX_RIGHE_DESC:
        desc = desc[:MAX_RIGHE_DESC]
        desc = desc[:desc.rfind(" ")].rstrip(",;:.") + "…"
    return desc


def sezione_feed(emoji: str, rubrica: str, voce: dict) -> str:
    return (f"{emoji} *{rubrica}*\n"
            f"*{pulisci(voce['titolo'])}* — {righe_desc(voce['desc'])}\n"
            f"👉 {voce['link']}")


def componi(adesso: datetime, n1, n2, nodo) -> str:
    testata = (f"📰 *3 NEWS DI VELA — {GIORNI_IT[adesso.weekday()]} "
               f"{adesso.day} {MESI_IT[adesso.month - 1]}*")
    parti = [testata]
    if n1:
        parti.append(sezione_feed("⛵", "BARCHE E PROGETTI", n1))
    if n2:
        if "desc" in n2:   # voce fresca dal feed
            parti.append(sezione_feed("🎓", "TECNICA & REGATE", n2))
        else:              # voce della libreria curata
            parti.append(f"🎓 *TECNICA & REGATE*\n"
                         f"*{pulisci(n2['titolo'])}* — {pulisci(n2['testo'])}\n"
                         f"👉 {n2['link']}")
    parti.append(f"🪢 *IL NODO DEL GIORNO: {nodo['nome']}*\n"
                 f"{pulisci(nodo['testo'])}\n"
                 f"👉 {nodo['link']} (animazione passo-passo)")
    return "\n\n".join(parti)


# --------------------------------------------------------------------------
# TELEGRAM E STATO
# --------------------------------------------------------------------------

def invia_telegram(testo: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": testo, "parse_mode": "Markdown",
              "disable_web_page_preview": False,
              "disable_notification": True},   # lettura da spiaggia: silenzioso
        timeout=30,
    )
    r.raise_for_status()
    print("[ok] news inviate")


def main() -> int:
    adesso = datetime.now(TZ)
    oggi = adesso.strftime("%Y-%m-%d")
    dry = os.environ.get("NEWS_DRY_RUN", "").lower() in ("1", "true", "yes")
    forza = os.environ.get("NEWS_FORZA", "").lower() in ("1", "true", "yes")

    if not forza and not (MESE_INIZIO <= adesso.month <= MESE_FINE):
        print("[info] fuori stagione (mag-set): niente news")
        return 0

    stato = json.loads(STATO_FILE.read_text(encoding="utf-8"))
    news = stato.setdefault("_news3", {})
    if not forza and not dry and news.get("data") == oggi:
        print("[info] news di oggi gia' pubblicate")
        return 0

    usati = news.get("usati", [])
    nodi = json.loads((DATI_DIR / "nodi.json").read_text(encoding="utf-8"))["nodi"]
    tecnica = json.loads((DATI_DIR / "tecnica.json").read_text(
        encoding="utf-8"))["articoli"]

    voci = voci_feed_ordinate()
    n1 = scegli_fresca(voci, CAT_BARCHE, usati)
    n2 = scegli_fresca(voci, CAT_TECNICA_REGATE, usati,
                       esclusi=[n1["link"]] if n1 else [])
    if n2 is None:
        n2 = tecnica[news.get("idx_tecnica", 0) % len(tecnica)]
    nodo = nodi[news.get("idx_nodi", 0) % len(nodi)]

    if n1 is None and n2 is None:
        # feed giu' e librerie esaurite? La rubrica salta senza drammi.
        print("[avviso] nessuna news disponibile: rubrica saltata")
        return 0

    testo = componi(adesso, n1, n2, nodo)
    if dry:
        print("[dry-run] messaggio che verrebbe inviato:\n")
        print(testo)
        return 0

    try:
        invia_telegram(testo)
    except Exception as e:  # noqa: BLE001
        print(f"[errore] invio news fallito: {e}")
        return 1

    # Aggiorna lo stato SOLO dopo l'invio riuscito.
    for v in (n1, n2):
        if v and v.get("link") and "desc" in v:
            usati.append(v["link"])
    news["usati"] = usati[-MAX_USATI:]
    if n2 is not None and "desc" not in n2:
        news["idx_tecnica"] = (news.get("idx_tecnica", 0) + 1) % len(tecnica)
    news["idx_nodi"] = (news.get("idx_nodi", 0) + 1) % len(nodi)
    news["data"] = oggi
    STATO_FILE.write_text(
        json.dumps(stato, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("[ok] stato news aggiornato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
