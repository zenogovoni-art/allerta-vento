# 🌬️ INFO VENTO — Guida al servizio

Avvisi automatici sul vento per i soci, direttamente su Telegram.

## Cos'è

Un servizio **gratuito e automatico** che controlla due stazioni meteo della
nostra zona e pubblica un avviso sul canale Telegram **«INFO VENTO»**
quando il vento si alza. Nessun PC acceso, nessuna app da installare: basta
iscriversi al canale.

## Come iscriversi

👉 **t.me/INFOVENTO**

Apri il link, premi **Iscriviti / Join** e riceverai gli avvisi sul telefono.

## Le stazioni controllate

- **Porto Corsini** (a sud) — Adriatico Wind Club
- **Lido di Volano** (a nord)

Avere una stazione a sud e una a nord aiuta ad anticipare l'arrivo del vento a
seconda della direzione.

## Quando arrivano gli avvisi

- Controllo **ogni 15 minuti**
- Solo nella fascia **09:00 – 19:00**
- Ogni messaggio indica **intensità (nodi), direzione e raffica**

## I tre livelli di avviso

| Livello | Vento medio | Messaggio |
|--------|-------------|-----------|
| 🟢 Navigabile | **da 8 nodi** | dati del vento (intensità, direzione, raffica) |
| 🟠 Attenzione | **da 20 nodi** | ⚠️ **ALERT VENTO !!!** — *Vento sostenuto: condizioni impegnative, adatte solo a chi ha esperienza. Valutate bene prima di uscire.* |
| 🔴 Sconsigliato | **da 30 nodi** | 🛑 **ALERT VENTO !!!** — *Vento molto forte: si sconsiglia di uscire in acqua. Pericoloso anche per i più esperti.* |

## 🌀 ALERT RAFFICA

Oltre al vento, il bot avvisa quando la **raffica** della giornata raggiunge
**15, 20, 25 o 30 nodi** (un avviso per soglia, una volta al giorno):

> 🌀 *ALERT RAFFICA — Porto Corsini*
> Oggi la raffica ha raggiunto **22.0 nodi** (soglia 20).

⚠️ Le stazioni forniscono la raffica **massima della giornata**, non quella
dell'istante: l'avviso indica che oggi le raffiche hanno toccato quel valore,
non necessariamente che stia raffica ora.

## Come "ragiona" il bot (per non riempirti di messaggi)

L'avviso parte **solo quando il vento sale di fascia**:

- se il vento supera gli 8 nodi → ricevi l'avviso;
- se resta più o meno stabile → **non** ricevi altri messaggi;
- se sale ancora di fascia (es. da 8 a 20, o da 20 a 30) → ricevi il nuovo
  ALERT;
- se scende sotto soglia e poi risale → ricevi di nuovo l'avviso.

## ⚠️ Importante

I dati sono **indicativi e non ufficiali**. Servono come indicazione di massima:
**verificate sempre le condizioni reali** prima di andare in acqua. La sicurezza
viene prima di tutto.

---

## 🆕 Ultimi aggiornamenti

- **ALERT RAFFICA**: avviso quando la raffica di giornata raggiunge 15, 20, 25,
  30 nodi.
- **Filtri direzione**: Porto Corsini avvisa per venti da sud (E→S→O), Lido di
  Volano per venti da nord (O→N→E).
- **Tre livelli di avviso**: oltre all'avviso normale (8 nodi), aggiunti due
  ALERT di sicurezza a **20 nodi** (attenzione) e **30 nodi** (uscita
  sconsigliata).
- **Soglia abbassata a 8 nodi** (prima era 10).
- **Controllo ogni 15 minuti** (prima ogni 30).
- **Fascia oraria 09:00 – 19:00** (prima 07:00 – 21:00).
- **Aggiunta la stazione di Lido di Volano** (nord), in più a Porto Corsini.
- Se una stazione è momentaneamente offline, il servizio continua con l'altra.
