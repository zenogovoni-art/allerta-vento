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

A Porto Corsini c'è anche una **stazione di riserva**: quella della **Guardia
Costiera Ausiliaria di Ravenna** (Marina di Ravenna, dall'altra parte del
canale del porto). Se la stazione principale non risponde, subentra
automaticamente senza interruzioni del servizio. In più fornisce la **raffica
degli ultimi 10 minuti** — un dato in tempo reale, più tempestivo della
massima giornaliera — che rende l'ALERT RAFFICA del settore sud più preciso:
può riarmarsi quando il vento cala e riscattare nella stessa giornata.

Per l'ALERT BORA si controllano inoltre due stazioni sentinella a nord-est
(vedi la sezione dedicata).

## Quando arrivano gli avvisi

- Controllo **ogni 15 minuti**
- Solo nella fascia **09:00 – 19:00**
- Ogni messaggio indica **intensità (nodi), direzione e raffica**

## 📇 Le schede che ricevi

In cima a ogni messaggio Telegram mostra il nome del canale **«INFO VENTO»**: la
**prima riga della scheda** ti dice subito di che tipo si tratta. C'è una scheda
**informativa** che esce sempre, e quattro **ALERT** che scattano solo quando serve.

| Scheda | Titolo (prima riga) | Quando arriva |
|--------|---------------------|---------------|
| Situazione vento | 🌬️ **SITUAZIONE VENTO — HH:MM** | ogni 30 minuti (9–19), sempre |
| Alert vento | 🌬️ **ALERT VENTO — Stazione** | il vento medio supera una soglia |
| Alert raffica | 🌀 **ALERT RAFFICA — Stazione** | la raffica del giorno supera una soglia |
| Alert pressione | 📉 **ALERT VARIAZIONE PRESSIONE — Stazione** | la pressione cala in fretta |
| Alert bora | 💨 **ALERT BORA — Sentinella** | vento forte da NE sulle sentinelle a nord |

Se un ALERT capita proprio mentre esce la *Situazione vento*, confluisce dentro
di essa: niente doppioni (vedi più sotto).

## 🌬️ I livelli dell'ALERT VENTO

Quando il vento medio supera una soglia arriva un **ALERT VENTO**, sempre con lo
stesso titolo **🌬️ ALERT VENTO — Stazione** e un'etichetta che ne dice la forza:

| Soglia | Etichetta | Cosa dice |
|--------|-----------|-----------|
| **da 8 nodi** | 🟢 8+ nodi | Prime arie: si comincia a navigare. |
| **da 10 nodi** | 🟢 10+ nodi | Bella arietta da planata. |
| **da 15 nodi** | 💨 15+ nodi | Vento teso: divertente ma impegnativo. |
| **da 20 nodi** | ⚠️ 20+ nodi | Vento sostenuto: solo per chi ha esperienza, valutate bene. |
| **da 30 nodi** | 🛑 30+ nodi | Vento molto forte: si sconsiglia di uscire, pericoloso anche per i più esperti. |

Esempio di scheda:

> 🌬️ *ALERT VENTO — Porto Corsini*\
> 🟢 *10+ nodi* — *Bella arietta da planata.*
>
> Vento **10.5 nodi** da SSW ↗️ — raffica **16.0 nodi**\
> 📈 in aumento\
> ⏱️ Possibile arrivo al circolo tra ~70 min

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

## 💨 ALERT BORA — le sentinelle a nord-est

La **bora** scende da nord-est e arriva in modo **violento**, spesso con poco
preavviso: per chi naviga in deriva è il vento più temuto. Per vederla
arrivare **prima** che tocchi i lidi ferraresi, il servizio controlla due
stazioni "sentinella" a nord-est del circolo, sulla rotta da cui scende la
bora:

- **Sottomarina (Diga Sud Chioggia)** — anemometro sulla diga foranea di
  Sottomarina, esposto al mare aperto;
- **Piattaforma CNR (largo di Venezia)** — la torre oceanografica a ~15 km al
  largo, che la bora raggiunge ancora prima.

Sono stazioni della **rete meteo-mareografica del Centro Maree di Venezia**
(la stessa rete istituzionale delle previsioni di acqua alta), con dati
aggiornati **ogni 5 minuti**.

L'ALERT BORA scatta **solo con vento dal settore nord-est** (da NNE a E) e ha
tre livelli:

| Livello | Vento medio | Cosa significa |
|--------|-------------|----------------|
| ⚠️ Bora 20+ nodi | **≥ 20 nodi** | bora sostenuta a nord: se siete in acqua, valutate il rientro |
| 🔴 Bora 25+ nodi | **≥ 25 nodi** | bora forte in avvicinamento: rientrare è prudente |
| 🛑 Bora 30+ nodi | **≥ 30 nodi** | bora molto forte: rientrare subito |

Quando possibile l'avviso include la **stima di arrivo a Lido di Spina**
(es. "tra ~90 min"): la distanza dalle sentinelle dà in genere **1–2 ore di
preavviso**. Come gli altri alert, scatta solo **al salire di livello**:
niente messaggi ripetuti finché la situazione resta stabile. Un vento forte
da un'altra direzione (es. scirocco da SE) **non** fa scattare l'ALERT BORA:
per quello ci sono gli alert delle stazioni locali.

## 🌬️ Situazione vento ogni 30 minuti

Dalle **9:00 alle 19:00**, ogni **mezz'ora**, il canale pubblica **sempre** la
situazione di **Porto Corsini** e **Lido di Volano** — intensità del vento,
direzione e raffica massima della giornata — **anche quando le condizioni non
cambiano**. È un quadro in tempo reale utile prima di decidere se uscire:

> 🌬️ *SITUAZIONE VENTO — 11:30*\
> 🌬️ *Porto Corsini* — 🟢 *Vento a 10 nodi*\
> Vento **10.5 nodi** da SSW ↗️ — raffica max oggi **16.0 nodi**\
> 📈 in aumento · ⏱️ arrivo al circolo ~70 min\
> 🌬️ *Lido di Volano*\
> Vento **2.7 nodi** da E ⬅️ — raffica max oggi **5.4 nodi**

A differenza degli ALERT (che scattano solo quando le condizioni peggiorano),
questo bollettino esce a orari regolari a prescindere, così avete il dato sempre
aggiornato.

La scheda delle **14:00** include in più l'**aggiornamento della corrente per
il pomeriggio** (previsione Arpae + misura della boa): spesso al mattino il
vento è debole e si esce dopo pranzo — a quell'ora la previsione della
corrente è anche più fresca, perché il run del giorno del modello Adriac è
ormai pubblicato.

Se in quel momento ci sono anche le **condizioni di un avviso** (vento sopra
soglia o nuova raffica), l'avviso **confluisce dentro il bollettino** — con il
livello raggiunto, la **tendenza** (in aumento / in calo) e la stima di arrivo
al circolo — invece di arrivare come messaggio separato: niente doppioni. Tra un
bollettino e l'altro, invece, gli avvisi partono subito da soli.

## 🌅 Bollettino del mattino

Ogni mattina verso le **9:00** la **previsione vento della giornata** per Lido di
Spina (fonte Open-Meteo): cosa aspettarsi nelle ore principali, raffiche
comprese. Viene inviato **tutti i giorni**, giovedì compreso.

Da questo bollettino trovi anche alcuni dati marini utili alla navigazione:

- 🌊 **Corrente a Lido di Spina** — la previsione della corrente di superficie
  per il punto davanti al circolo, divisa in **mattina (9–13)** e **pomeriggio
  (13–19)**: intensità in nodi e direzione **verso cui** scorre. Utile per
  decidere da che lato conviene allungare i bordi. Il dato viene dal modello
  oceanografico **Adriac di Arpae Emilia-Romagna** (risoluzione 1 km, tiene
  conto anche della portata reale del Po — il motore principale delle correnti
  sulla costa ferrarese). Sotto, in corsivo, la **corrente misurata** dalla
  boa Nausicaa 2 di Arpae (al largo di Cesenatico): è il riscontro reale della
  corrente costiera generale, non il dato locale.
- 🌊 **Maree del giorno** — orari di **alta** e **bassa marea** con l'altezza in
  **centimetri rispetto al livello medio del mare di oggi**: `+26 cm` vuol dire
  che il mare sale 26 cm sopra la media della giornata, `−19 cm` che scende
  19 cm sotto. In più l'**escursione della giornata**, cioè la differenza tra
  il punto più alto e quello più basso. La previsione tiene conto anche della
  spinta del vento, non solo della marea astronomica. Orari su base oraria,
  quindi indicativi al minuto.
- 🌗 **Fase lunare** — se la luna è **crescente o calante**, con quanti giorni
  mancano alla luna piena o alla luna nuova. Utile anche perché nei giorni di
  luna piena e luna nuova le maree sono più marcate (sizigie), mentre ai quarti
  sono più deboli (quadrature).

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

- **Corrente aggiornata alle 14:00**: la Situazione vento delle 14 include la
  corrente prevista per il pomeriggio (con la misura live della boa), per chi
  esce dopo pranzo.
- **Corrente locale dal modello Arpae**: nel bollettino del mattino la corrente
  davanti a Lido di Spina ora viene dal modello Adriac di Arpae (1 km, con la
  portata reale del Po), divisa in mattina e pomeriggio, con il riscontro
  misurato dalla boa Nausicaa 2 al largo di Cesenatico.
- **Stazione di riserva a sud e raffica in tempo reale**: la stazione della
  Guardia Costiera Ausiliaria di Ravenna (Marina di Ravenna) fa da riserva a
  Porto Corsini e fornisce la raffica degli ultimi 10 minuti, per un ALERT
  RAFFICA più tempestivo nel settore sud.
- **Benvenuto serale ai nuovi iscritti**: ogni sera alle **21:00**, se durante
  il giorno qualcuno si è unito al canale, un messaggio dà il benvenuto per
  nome ai nuovi arrivati (un solo messaggio al giorno, niente disturbo in
  orario di navigazione).
- **ALERT BORA**: due stazioni sentinella a nord-est (Sottomarina Diga Sud e
  Piattaforma CNR al largo di Venezia) avvisano quando la bora supera 20, 25
  o 30 nodi, con stima di arrivo a Lido di Spina — in genere 1–2 ore di
  preavviso.
- **Titoli delle schede più chiari**: gli avvisi ora hanno un titolo di famiglia
  riconoscibile — **ALERT VENTO**, **ALERT RAFFICA**, **ALERT VARIAZIONE
  PRESSIONE** — ben distinti dalla **Situazione vento** informativa delle ogni
  mezz'ora (vedi tabella "Le schede che ricevi").
- **Situazione vento ogni 30 minuti** (9:00–19:00): vento, direzione e raffica
  delle due stazioni pubblicati sempre, anche a condizioni invariate. Se coincide
  con un avviso, l'avviso confluisce nel bollettino (niente messaggi doppi).
- **Maree più chiare e fase lunare nel bollettino delle 9:00**: altezze di
  marea in centimetri rispetto al livello medio del giorno (+ sopra, − sotto),
  escursione della giornata e luna crescente/calante.
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
