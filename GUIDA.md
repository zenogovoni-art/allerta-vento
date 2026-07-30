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
| Situazione vento | 🌬️ **SITUAZIONE VENTO — HH:MM** | ogni 15 minuti (9–19), sempre |
| Alert vento | 🌬️ **ALERT VENTO — Stazione** | il vento medio supera una soglia |
| Alert raffica | 🌀 **ALERT RAFFICA — Stazione** | la raffica del giorno supera una soglia |
| Alert pressione | 📉 **ALERT VARIAZIONE PRESSIONE — Stazione** | la pressione cala in fretta |
| Alert bora | 💨 **ALERT BORA — Sentinella** | vento forte da NE sulle sentinelle a nord |

Ogni ALERT arriva sempre come scheda a sé, con un box tutto suo per farlo
risaltare: se scatta nello stesso momento della *Situazione vento*, viene
pubblicato **un minuto dopo** (vedi più sotto).

🔔 **Il telefono suona per gli ALERT e per la Situazione vento**, i contenuti
principali del canale. Le schede di contorno (bollettino del mattino,
grafici, riepilogo della sera, benvenuti) arrivano invece come **messaggi
silenziosi**: le trovi nel canale, ma non ti disturbano.

## 🌬️ I livelli dell'ALERT VENTO

Quando il vento medio supera una soglia arriva un **ALERT VENTO**, sempre con lo
stesso titolo **🌬️ ALERT VENTO — Stazione** e un'etichetta che ne dice la forza:

| Soglia | Etichetta | Cosa dice |
|--------|-----------|-----------|
| **da 20 nodi** | ⚠️ 20+ nodi | Vento sostenuto: solo per chi ha esperienza, valutate bene. |
| **da 25 nodi** | 🟠 25+ nodi | Vento forte: solo per equipaggi molto esperti e ben attrezzati. |
| **da 30 nodi** | 🛑 30+ nodi | Vento molto forte: si sconsiglia di uscire, pericoloso anche per i più esperti. |

Esempio di scheda:

> 🌬️ *ALERT VENTO — Porto Corsini*\
> ⚠️ *20+ nodi* — *Vento sostenuto: solo per chi ha esperienza, valutate bene.*
>
> Vento **21.5 nodi** da SSW ↗️ — raffica **26.0 nodi**\
> 📈 in aumento\
> ⏱️ Possibile arrivo al circolo tra ~50–70 min

Quando le raffiche superano di molto il vento medio (di oltre il 60%),
l'ALERT aggiunge una riga di attenzione in più — il vento "a strappi" è
insidioso in deriva anche quando la media non spaventa:

> 💨 *Vento irregolare: raffiche ben sopra la media*

## 🌀 ALERT RAFFICA

Oltre al vento, il bot avvisa quando la **raffica** della giornata raggiunge
**20, 25 o 30 nodi** (un avviso per soglia, una volta al giorno):

> 🌀 *ALERT RAFFICA — Porto Corsini*
> Oggi la raffica ha raggiunto **22.0 nodi** (soglia 20).

⚠️ Le stazioni forniscono la raffica **massima della giornata**, non quella
dell'istante: l'avviso indica che oggi le raffiche hanno toccato quel valore,
non necessariamente che stia raffica ora.

## ⏳ Stima di arrivo al circolo

Negli **avvisi di vento** (non nelle raffiche) trovi una riga come:

> ⏱️ Possibile arrivo al circolo tra ~55–80 min

È una stima di quanto può metterci il rinforzo ad arrivare al circolo di
**Lido di Spina**, calcolata in base a distanza, direzione e intensità del
vento. È una **forchetta**: il valore alto ipotizza che il rinforzo viaggi
alla velocità del vento misurato, quello basso tiene conto che i fronti si
muovono spesso più veloci del vento al suolo — prudenza: può arrivare prima.
Compare solo quando il vento sta effettivamente puntando verso il circolo
(es. da sud per Porto Corsini, da nord per Lido di Volano). È un valore
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

Il controllo gira **ogni 15 minuti**, insieme al rilievo del vento e sugli
stessi dati, quindi un calo rapido si vede entro un quarto d'ora. Continua
anche di notte, senza mandare nulla: la tendenza si misura su 3 ore, e così
alle 9:00 del mattino il confronto è già pronto. Se scatta insieme ad altri
messaggi, l'alert pressione esce per ultimo.

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

L'ALERT BORA scatta **solo con vento dai settori N, NNE e NE** e ha
tre livelli:

| Livello | Vento medio | Cosa significa |
|--------|-------------|----------------|
| ⚠️ Bora 20+ nodi | **≥ 20 nodi** | bora sostenuta a nord: se siete in acqua, valutate il rientro |
| 🔴 Bora 25+ nodi | **≥ 25 nodi** | bora forte in avvicinamento: rientrare è prudente |
| 🛑 Bora 30+ nodi | **≥ 30 nodi** | bora molto forte: rientrare subito |

Quando possibile l'avviso include la **stima di arrivo a Lido di Spina**
(es. "tra ~65–90 min"): la distanza dalle sentinelle dà in genere **1–2 ore di
preavviso**. Come gli altri alert, scatta solo **al salire di livello**:
niente messaggi ripetuti finché la situazione resta stabile. Un vento forte
da un'altra direzione (es. scirocco da SE) **non** fa scattare l'ALERT BORA:
per quello ci sono gli alert delle stazioni locali.

## 🌬️ Situazione vento ogni 15 minuti

Dalle **9:00 alle 19:00**, ogni **15 minuti**, il canale pubblica **sempre** la
situazione di **Porto Corsini** e **Lido di Volano** — intensità del vento,
direzione e tendenza — **anche quando le condizioni non cambiano**. È un
quadro in tempo reale utile prima di decidere se uscire, tenuto volutamente
snello:

> 🌬️ *SITUAZIONE VENTO — 11:15*\
> 🌬️ *Porto Corsini*\
> Vento **20.5 nodi** da SSW ↗️\
> 📈 in aumento\
> 🌬️ *Lido di Volano*\
> Vento **2.7 nodi** da E ⬅️\
> ➖ stazionario\
> 🌊 **Corrente** ~0.4 kn ↘️ SE · marea in salita

Ogni scheda mostra se il vento, rispetto alla Situazione vento precedente, è
📈 **in aumento**, ➖ **stazionario** o 📉 **in calo**.

### 🌊 La riga della corrente

L'ultima riga, sempre presente, è pensata per essere letta **al volo sul
telefono o sullo smartwatch mentre si naviga**:

- **~0.4 kn** — quanto tira la corrente davanti al circolo.
- **↘️ SE** — la freccia punta **dove va** la corrente (attenzione: quella del
  vento indica invece **da dove** arriva). Sotto **0.1 nodi** la direzione non
  ha senso e la riga dice solo *trascurabile*.
- **marea in salita / in calo / stanca** — misurata dal mareografo di **Porto
  Garibaldi**, a circa 2 km dal circolo, che pubblica il livello del mare ogni
  10 minuti. In salita la corrente tende a spingere verso **nord-ovest**, in
  calo verso **sud-est**: è la forzante che di solito conta di più sotto costa
  insieme al vento.

Il valore in nodi viene dal modello **Adriac** di Arpae (griglia da 1 km sul
punto davanti al circolo), che si aggiorna **una volta al giorno**: cambia di
ora in ora perché la previsione è oraria. Se per qualche motivo non è
disponibile, al suo posto compare la corrente **misurata** dalla boa di
Cesenatico, dichiarata come tale — è a 48 km, quindi indica l'andamento
generale della corrente costiera, non il dato locale.

A differenza degli ALERT (che scattano solo quando le condizioni peggiorano),
questo bollettino esce a orari regolari a prescindere, così avete il dato sempre
aggiornato. Il livello raggiunto, la stima di arrivo al circolo e la raffica
non compaiono qui: restano nella scheda dell'ALERT, per tenere questo
bollettino leggero.

La scheda delle **14:00** aggiunge una riga: la **corrente media prevista per
tutto il pomeriggio** (13-19), che risponde a una domanda diversa dalla riga
qui sopra — non «com'è adesso» ma «cosa mi aspetta se scendo in acqua ora»:

> 🌊 **Corrente** ~0.5 kn ↘️ SE · marea in calo\
> 🕐 **Nel pomeriggio**: corrente prevista ~0.5 kn verso SE

Spesso al mattino il vento è debole e si esce dopo pranzo, e a quell'ora la
previsione è anche più fresca, perché il run del giorno del modello Adriac è
ormai pubblicato.

Se in quel momento ci sono anche le **condizioni di un ALERT** (vento sopra
soglia o nuova raffica), l'ALERT **non confluisce più nel bollettino**: arriva
come scheda a sé, con un box tutto suo per farlo risaltare, pubblicata **un
minuto dopo** la Situazione vento. Tra un bollettino e l'altro, invece, gli
ALERT partono subito da soli.

## 🌅 Bollettino del mattino

Ogni mattina verso le **9:00** la **previsione vento della giornata** per Lido di
Spina (fonte Open-Meteo): cosa aspettarsi nelle ore principali, raffiche
comprese. Viene inviato **tutti i giorni**, giovedì compreso.

Quando la giornata lo permette, il bollettino indica anche la **fascia oraria
migliore per uscire in deriva**: la finestra (di almeno 2 ore) in cui è
previsto vento tra ~6 e ~16 nodi senza raffiche violente, con l'intensità
media e la direzione:

> 🕐 **Fascia migliore per uscire: 13–17** — ~10 nodi da SE.

Se il giorno è tutto bonaccia o tutto vento forte, la riga semplicemente non
compare.

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

## 📰 3 news di vela (ogni giorno alle 10:20)

Ogni giorno alle **10:20**, da maggio a settembre, tre notizie di vela da
leggere in spiaggia aspettando il vento:

- ⛵ **Barche e progetti** — la presentazione più fresca di una nuova barca
  **a vela** o di un progetto (solo vela, niente motore), dalle testate
  Giornale della Vela e Farevela;
- 🎓 **Tecnica & regate** — una spiegazione tecnica (manovre, regolazioni,
  componenti) oppure una notizia di regata, dai giri del mondo alle classi
  olimpiche;
- 🪢 **Il nodo del giorno** — un nodo marinaro con spiegazione in italiano e
  link all'**animazione passo-passo** per impararlo davvero.

Per ogni notizia: titolo, due righe per capire di cosa si tratta e il link
all'articolo completo. Il messaggio arriva **silenzioso** — è lettura da
ombrellone, non un alert.

## 📊 Riepilogo della sera

Ogni sera verso le **19:00** un riepilogo con **vento massimo e raffica massima**
registrati nella giornata, accompagnato dal **grafico dell'andamento reale del
vento**: le letture raccolte ogni 15 minuti dalle due stazioni diventano una
curva che mostra com'è andata davvero la giornata (vento pieno, raffica
tratteggiata, soglie d'alert segnate quando il vento ci si è avvicinato). Per
ogni ora, sopra la curva di ciascuna stazione, una **freccia mostra la
direzione di provenienza** del vento: la freccia "vola col vento", come nelle
app meteo (vento da N = freccia che punta in basso). È il complemento "a
consuntivo" del grafico delle previsioni weekend.

## 📈 Tendenza e direzione

Sia nella **Situazione vento** sia negli **ALERT VENTO** trovi sempre se il
vento è 📈 **in aumento**, ➖ **stazionario** o 📉 **in calo** rispetto alla
lettura precedente, e una **freccia** che mostra verso dove sta soffiando.

## Come "ragiona" il bot (per non riempirti di messaggi)

L'avviso parte **solo quando il vento sale di fascia**:

- se il vento supera i 20 nodi → ricevi l'avviso;
- se resta più o meno stabile → **non** ricevi altri messaggi;
- se sale ancora di fascia (es. da 20 a 25, o da 25 a 30) → ricevi il nuovo
  ALERT;
- se scende sotto soglia e poi risale → ricevi di nuovo l'avviso.

## 🧹 Pulizia giornaliera del canale

Ogni notte, **appena passata la mezzanotte**, il bot **cancella i messaggi dal
penultimo giorno all'indietro**: nel canale restano sempre e solo i messaggi
**di ieri e di oggi**, così gli iscritti non si ritrovano centinaia di vecchi
messaggi da scorrere. Non serve fare nulla: la cronologia sparisce da sola
anche dal telefono degli iscritti.

**Unica eccezione: i Riepiloghi della sera non vengono mai cancellati.**
Restano nel canale come archivio storico della stagione — con i loro grafici
dell'andamento del vento saranno utili in futuro per fare statistiche.

## ⚠️ Importante

I dati sono **indicativi e non ufficiali**. Servono come indicazione di massima:
**verificate sempre le condizioni reali** prima di andare in acqua. La sicurezza
viene prima di tutto.

---

## 🆕 Ultimi aggiornamenti

- **Corrente e marea in ogni Situazione vento (ogni 15 minuti)**: una riga
  sola — intensità, freccia che punta dove va la corrente, e fase di marea
  misurata a Porto Garibaldi — pensata per essere letta al volo sul telefono
  o sullo smartwatch mentre si naviga.
- **3 news di vela ogni giorno alle 10:20**: barche nuove (solo vela!),
  tecnica o regate, e il nodo del giorno con animazione — lettura da
  spiaggia in attesa del vento.
- **Stima di arrivo a forchetta**: la riga "possibile arrivo al circolo"
  ora dà un intervallo (es. ~55–80 min) — il valore basso ricorda che i
  fronti spesso viaggiano più veloci del vento al suolo.
- **ALERT BORA più selettivo**: scatta solo con vento dai settori N, NNE e
  NE (prima il settore arrivava fino a E).
- **Pulizia giornaliera (prima settimanale)**: nel canale restano solo i
  messaggi di oggi e di ieri. I Riepiloghi della sera però non si cancellano
  mai: restano come archivio storico con i grafici del vento.
- **Notifiche sonore solo per l'essenziale**: suonano gli ALERT e la
  Situazione vento; le schede di contorno (bollettini, grafici, riepilogo,
  benvenuti) ora arrivano come messaggi silenziosi.
- **Grafico serale del vento**: il riepilogo delle 19:00 include il grafico
  dell'andamento reale del vento della giornata alle due stazioni, con una
  freccia per ogni ora che mostra la direzione di provenienza.
- **Fascia migliore per uscire**: il bollettino del mattino indica la
  finestra oraria con vento previsto adatto alla deriva (~6–16 nodi).
- **Nota "vento irregolare"**: l'ALERT VENTO segnala quando le raffiche
  superano di molto il vento medio (vento a strappi).
- **ALERT sganciati dalla Situazione vento**: non confluiscono più nel
  bollettino, arrivano sempre come scheda a sé con un box tutto suo —
  pubblicata un minuto dopo — per essere più riconoscibili, mentre la
  Situazione vento resta più snella.
- **Tendenza sempre visibile nella Situazione vento**: ogni scheda mostra se
  il vento, rispetto al bollettino precedente, è 📈 in aumento, ➖
  stazionario o 📉 in calo.
- **Scala vento semplificata a tre livelli (20 · 25 · 30 nodi)**: eliminati
  gli avvisi a 8 e 10 nodi, troppo frequenti e poco utili come alert; aggiunto
  un livello intermedio a 25 nodi tra "attenzione" e "sconsigliato uscire".
- **ALERT RAFFICA a tre livelli (20 · 25 · 30 nodi)**: eliminato il livello a
  15 nodi.
- **Situazione vento ogni 15 minuti** (prima ogni 30): il quadro in tempo
  reale ora è aggiornato al passo del controllo delle stazioni.
- **Pulizia settimanale del canale**: ogni lunedì il bot cancella tutti i
  messaggi della settimana passata, così la chat resta leggera.
- **Corrente aggiornata alle 14:00**: la Situazione vento delle 14 include la
  corrente media prevista per il pomeriggio, per chi esce dopo pranzo.
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
  PRESSIONE** — ben distinti dalla **Situazione vento** informativa (vedi
  tabella "Le schede che ricevi").
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
- **Filtri direzione**: Porto Corsini avvisa per venti da sud (E→S→O), Lido di
  Volano per venti da nord (O→N→E).
- **Controllo ogni 15 minuti** (prima ogni 30).
- **Fascia oraria 09:00 – 19:00** (prima 07:00 – 21:00).
- **Aggiunta la stazione di Lido di Volano** (nord), in più a Porto Corsini.
- Se una stazione è momentaneamente offline, il servizio continua con l'altra.
