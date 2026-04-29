# ERPsim Spielregeln (Manufacturing Intro)

Quelle: `Docs/2023-24_Slides_Manuf_Intro_EN.pdf`  
Status: Verbindliche Arbeitsgrundlage fuer den Probelauf und die weiteren Sessions.

## 1) Ziel und Siegbedingung

- Gewinner ist das Team mit der **hoechsten Company Valuation** am Ende der Simulation.
- Company Valuation ist damit die zentrale Zielgroesse, nicht nur kurzfristiger Umsatz.

## 2) Harte Hauptregeln

- **No stock, no sales.** Ohne Bestand gibt es keine Verkaeufe.
- Kundenpraeferenzen bleiben **innerhalb desselben Spiels konstant**.
- Es gilt ein **ethisches Verhalten** waehrend des gesamten Spiels.
- Endbestand wird im Abschluss mit **Kostenpreis** bewertet; daher **nicht unter Kosten verkaufen**.

## 3) Markt- und Auftragslogik

- Verkaufsfokus im Intro auf **DC12 (Grocery Chains)**.
- Regionen: **North, South, West** mit regional unterschiedlichen Praeferenzen.
- Kundenauftraege haben eine **Zahlungsverzoegerung von 10-20 Tagen**.
- **Jeder Auftrag enthaelt 4 Produkte** (wichtig fuer Warenkorbanalyse und Planung).
- Marktgroesse als grobe Orientierung: **ca. EUR 360.000 pro Team und Woche**.

## 4) Spielstruktur und Zeit

- Das Spiel laeuft in **3 Runden**.
- Jede Runde umfasst **20 virtuelle Tage**.
- Operativ laufen Planung, Beschaffung, Produktion und Verkauf kontinuierlich ueber die Runden.

## 5) Produktions- und Kapazitaetsregeln

- Es gibt **eine Produktionslinie**: nur ein Produkt gleichzeitig.
- Produktionskapazitaet: **16.000 Einheiten pro virtuellem Tag**.
- Setup-Zeit: **8 Stunden** pro Produktionslauf (reduziert verfuegbare Produktionszeit).
- Lotgroesse (min/max): **16.000 / 16.000**.

## 6) Beschaffung und Lieferanten

- Lieferanten: **V01** und **V02**.
- Lieferzeit variiert je Lieferant/Material (typisch **1-5 Tage**).
- Zahlung an Lieferanten: **20 Tage**.
- Lieferverzoegerungen muessen in Material- und Produktionsplanung einkalkuliert werden.

## 7) Produkte und Inventar (Intro)

- Insgesamt 12 Endprodukte (500g/1kg Varianten).

  | ProduktID | Gewicht | Name       |
  | --------- | ------- | ---------- |
  | F-01      | 500g    | Nut        |
  | F-02      | 500g    | Blueberry  |
  | F-03      | 500g    | Strawberry |
  | F-04      | 500g    | Raisin     |
  | F-05      | 500g    | Original   |
  | F-06      | 500g    | Mixed      |
  | F-07      | 1kg     | Nut        |
  | F-08      | 1kg     | Blueberry  |
  | F-09      | 1kg     | Strawberry |
  | F-10      | 1kg     | Raisin     |
  | F-11      | 1kg     | Original   |
  | F-12      | 1kg     | Mixed      |

- Startbestand:
  - F01-F04 und F11-F14: jeweils **30.000 Einheiten**.
  - F05/F06 und F15/F16: **kein Startbestand**.
- In spaeteren Runden kommen die fehlenden Produkte aktiv in die operative Planung.

## 8) Lager- und Kostenregeln

- Lagerkapazitaeten sind begrenzt; Ueberkapazitaet erzeugt Zusatzkosten.
- Richtwerte Zusatzkosten je zusaetzliche 50.000 Einheiten:
  - Finished goods: EUR 500/Tag
  - Raw materials: EUR 1.000/Tag
  - Packaging: EUR 100/Tag
- Fixkosten laufen periodisch auf (u. a. Labor, Overhead, SG&A, Depreciation).

## 9) Operativer Pflichtablauf pro Entscheidungszyklus

1. Forecast in `MD61`
2. MRP in `MD01`
3. Purchase Orders in `ME59N`
4. Production release in `CO41`
5. Marketingplanung in `ZADS`
6. Preisanpassung in `VK32`
7. Monitoring ueber Reports (`ZMB52`, `ZME2N`, `ZCOOIS`, `ZVC2`, `ZVA05`, `ZMARKET`, `F.01`, `ZFF7B`)

## 10) Strategieimplikationen (aus den Regeln abgeleitet)

- Stockout-Vermeidung hat Prioritaet, da verlorene Nachfrage direkt an Wettbewerber geht.
- Liquiditaet aktiv steuern (Zahlungsziele + Vorfinanzierung von Bestand/Produktion).
- Produktion mit Setup-Zeiten und Einlinien-Constraint eng takten.
- Preise, Marketing, Bestand und Beschaffung immer gemeinsam optimieren.
- Co-Purchase-Logik (4er-Warenkoerbe) fuer Sortiments- und Verfuegbarkeitsentscheidungen nutzen.

---

## Verbindlichkeit fuer meine Arbeit

Ich halte mich bei allen Empfehlungen und Auswertungen an diese Datei.  
Wenn neue oder abweichende Spielregeln von der Spielleitung kommen, aktualisiere ich diese Datei sofort.