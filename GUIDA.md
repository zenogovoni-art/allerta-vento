# 🌬️ INFO VENTO — Guida al servizio

Avvisi automatici sul vento per i soci, direttamente su Telegram.

## Cos'è

Un servizio **gratuito e automatico** che controlla due stazioni meteo della
nostra zona e pubblica avvisi sul canale Telegram **«INFO VENTO»**: quando il
vento si alza, quando la pressione cala in fretta, più previsioni e riepiloghi.
Nessun PC acceso, nessuna app da installare: basta iscriversi al canale.

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

## ⏳ Stima di arrivo al circolo

Negli **avvisi di vento** (non nelle raffiche) trovi una riga come:

> ⏱️ Possibile arrivo al circolo tra ~80 min

È una stima di quanto può metterci il rinforzo ad arrivare al circolo di
**Lido di Spina**, calcolata in base a distanza, direzione e intensità del
vento. Compare solo quando il vento sta effettivamente puntando verso il
circolo (es. da sud per Porto Corsini, da nord per Lido di Volano). È un valore
**indicativo**, utile come anticipo.

## 📉 ALERT VARIAZIONE PRESSIONE

Un **calo rapido della pressione atmosferica** è uno dei segnali più affidabili
di vento in rinforzo o di peggioramento in arrivo. Il servizio tiene d'occhio la
pressione a **Porto Corsini** e **Lido di Volano** e avvisa quando scende troppo
in fretta (calo misurato sulle ultime **3 ore**):

| Livello | Calo in 3 ore | Cosa significa |
|--------|---------------|----------------|
| 🟡 Attenzione | **≥ 3 hPa** | probabile rinforzo di vento |
| 🔴 Alert | **≥ 6 hPa** | peggioramento marcato, possibile groppo: prudenza |

Il controllo è automatico durante la giornata, sfasato rispetto a quello del
vento per non sovrapporsi.

## 🌬️ Situazione vento ogni 30 minuti

Dalle **9:00 alle 19:00**, ogni **mezz'ora**, il canale pubblica **sempre** la
situazione di **Porto Corsini** e **Lido di Volano** — intensità del vento,
direzione e raffica massima della giornata — **anche quando le condizioni non
cambiano**. È un quadro in tempo reale utile prima di decidere se uscire:

> 🌬️ *Situazione vento — 11:30*\
> 🌬️ *Porto Corsini* — 🟢 *Vento a 10 nodi*\
> Vento **10.5 nodi** da SSW ↗️ — raffica max oggi **16.0 nodi**\
> 📈 in aumento · ⏱️ arrivo al circolo ~70 min\
> 🌬️ *Lido di Volano*\
> Vento **2.7 nodi** da E ⬅️ — raffica max oggi **5.4 nodi**

A differenza degli ALERT (che scattano solo quando le condizioni peggiorano),
questo bollettino esce a orari regolari a prescindere, così avete il dato sempre
aggiornato.

Se in quel momento ci sono anche le **condizioni di un avviso** (vento sopra
soglia o nuova raffica), l'avviso **confluisce dentro il bollettino** — con il
livello raggiunto, la **tendenza** (in aumento / in calo) e la stima di arrivo
al circolo — invece di arrivare come messaggio separato: niente doppioni. Tra un
bollettino e l'altro, invece, gli avvisi partono subito da soli.

## 🌅 Bollettino del mattino

Ogni mattina verso le **9:00** la **previsione vento della giornata** per Lido di
Spina (fonte Open-Meteo): cosa aspettarsi nelle ore principali, raffiche
comprese. Viene inviato **tutti i giorni**, giovedì compreso.

Da questo bollettino trovi anche due dati marini utili alla navigazione:

- 🌊 **Corrente di superficie** — la direzione verso cui scorre la corrente
  (con velocità indicativa).
- 🌙 **Maree del giorno** — orari di **alta** e **bassa marea** con la relativa
  altezza (livello sul medio mare: valori positivi sopra la media, negativi
  sotto). La previsione tiene conto anche della spinta del vento, non solo della
  marea astronomica. Orari su base oraria, quindi indicativi al minuto.

## 📊 Grafico previsioni weekend (giovedì, venerdì, sabato)

**Giovedì, venerdì e sabato verso le 9:05**, subito dopo il bollettino, un
grafico con il vento previsto a **Lido di Spina** per i **giorni che restano del
weekend**: giovedì → ven/sab/dom, venerdì → sab/dom, sabato → domenica. Il giorno
di oggi non viene ripetuto, perché è già nel bollettino qui sopra. Ogni barra è
il vento massimo previsto in nodi, con sopra una freccia che indica la direzione:
utile per programmare le uscite del fine settimana. *Previsione indicativa.*

## 📊 Riepilogo della sera

Ogni sera verso le **19:00** un riepilogo con **vento massimo e raffica massima**
registrati nella giornata.

## 📈 Tendenza e direzione negli avvisi

Negli avvisi di vento trovi sempre se il vento è 📈 **in aumento**, 📉 **in calo**
o ➖ **stabile**, e una **freccia** che mostra verso dove sta soffiando.

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

- **Situazione vento ogni 30 minuti** (9:00–19:00): vento, direzione e raffica
  delle due stazioni pubblicati sempre, anche a condizioni invariate. Se coincide
  con un avviso, l'avviso confluisce nel bollettino (niente messaggi doppi).
- **Correnti e maree nel bollettino delle 9:00**: direzione della corrente di
  superficie e orari/altezze di alta e bassa marea del giorno.
- **ALERT variazione pressione**: avviso quando la pressione cala rapidamente
  (≥3 hPa/3h giallo, ≥6 hPa/3h rosso), su entrambe le stazioni.
- **Grafico previsioni weekend**: giovedì, venerdì e sabato alle 9:05 il vento
  previsto a Lido di Spina per i giorni che restano del weekend (gio → ven/sab/dom,
  ven → sab/dom, sab → dom). Il bollettino del mattino ora esce tutti i giorni.
- **Bollettino del mattino** (~9:00) e **riepilogo della sera** (~19:00).
- **Tendenza** del vento (in aumento / in calo / stabile) e **freccia** della
  direzione negli avvisi.
- **Stima di arrivo al circolo**: negli avvisi vento, una stima dei minuti
  perché il rinforzo raggiunga Lido di Spina.
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
