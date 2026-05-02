# Company Valuation (Company Value) – Logik, Daten und Agenten-Leitfaden

Diese Datei beschreibt, **was wir sicher wissen**, **was wir aus den Daten ableiten können**, und **wie Entscheidungen typischerweise** auf die Zielgröße **Company Valuation** wirken. Sie dient **zukünftigen Agents** und dem Team als gemeinsame Referenz.

**Siegbedingung (verbindlich laut Spielunterlagen / Handover):**

| Regel | Inhalt |
| :--- | :--- |
| Gewinner | Team mit **höchster `COMPANY_VALUATION`** am **Ende** der Simulation |
| Implikation | Kurzfristiger Umsatz allein ist nicht das Ziel; es zählt der **bewertete Unternehmenswert** zum Schluss |

---

## 1) Datenquelle: OData `Company_Valuation`

Die Bewertung wird vom Spiel **periodisch** ausgewiesen (je Step/Periode, siehe `SIM_*` Felder). Im Projekt werden Snapshots als CSV unter `automation/data/*_company_valuation.csv` abgelegt.

### 1.1 Felder (Stand: Beispiel-Snapshot Team JJ)

| Feld | Rolle (kurz) |
| :--- | :--- |
| `COMPANY_CODE` | Team |
| `SIM_ROUND`, `SIM_STEP`, `SIM_PERIOD`, `SIM_ELAPSED_STEPS`, `SIM_DATE` | Zeitbezug |
| `BANK_CASH_ACCOUNT` | Liquidität (Kasse/Bank) |
| `ACCOUNTS_RECEIVABLE` | Forderungen aus Kundenumsatz |
| `BANK_LOAN` | Darlehensstand (typisch negativ = Verbindlichkeit) |
| `ACCOUNTS_PAYABLE` | Verbindlichkeiten ggü. Lieferanten |
| `PROFIT` | Gewinn (kumuliert / spielspezifisch; exakte Definition im SAP-Kontext) |
| `SETUP_TIME_INVESTMENT` | getätigte Setup-Time-Investition (Kapitalbindung) |
| `DEBT_LOADING` | Schulden-/Hebelkennzahl (spielintern) |
| `CREDIT_RATING` | Bonität |
| `COMPANY_RISK_RATE_PCT` | unternehmensspezifischer Risikosatz (%) |
| `MARKET_RISK_RATE_PCT` | Marktrisikosatz (%) |
| **`COMPANY_VALUATION`** | **ausgewiesener Unternehmenswert** |
| `CURRENCY` | Währung |

**Wichtig für Agents:** Die **exakte mathematische Formel** von `COMPANY_VALUATION` aus den Einzelfeldern steht **nicht** in diesem Repository. Sie ergibt sich aus der **ERPsim-/SAP-Simulation** (Discounted-Cashflow-ähnliche Logik mit Risikosätzen ist plausibel, aber nicht hier belegt). Zuverlässig ist:

1. **Reihen `Company_Valuation` über die Zeit vergleichen** (Deltas pro Step).
2. **Parallel `Financial_Postings`** lesen (was fließt wann als Kosten/Erlös).
3. Bei Bedarf **Kurs-PDF/Job Aid** zur offiziellen Definition nachziehen.

---

## 2) Wirkungskette: Entscheidungen → Bilanz & P&L → Bewertung

Grober Kausalpfad (vereinfacht, für Planung und Agenten-Reasoning):

| Schicht | Beispiele | Typische Auswirkung auf Bewertungs-Treiber |
| :--- | :--- | :--- |
| **Absatz & Preis** | VK32, Listpreis vs. Markt, nicht unter Kosten verkaufen | `NET_VALUE`, `COST` → Marge → `PROFIT`; Zahlungsziel → `ACCOUNTS_RECEIVABLE` |
| **Werbung** | Marketing je Region | Nachfrage → Umsatz; **Kosten** sofort/laufend → `PROFIT` / Cash |
| **Produktion** | CO41, Losgrößen, Setup-Zeit | Deckung, Fehlmengen; **Opportunity Cost** bei Stockouts; Investitionen |
| **Einkauf** | ZME12, Lieferantenwahl V01/V11, V02/V12 | Einkaufspreis, PO-Fixkosten, CO₂e-Kosten (Preset 3) → `ACCOUNTS_PAYABLE`, Cash, Carbon-Posting |
| **Logistik** | Transfers, Lieferweg Zentrallager vs. Region | Transferkosten & CO₂e (siehe `marketInformation.md`) → Kostenposten |
| **Investitionen** | z. B. Setup Time Reduction, Capacity, Sustainability (ZFB50) | Sofortige Cash-/Bilanzwirkung, ggf. `SETUP_TIME_INVESTMENT`, spätere Kostensenkung / CO₂ |
| **Finanzierung** | Kredit, Tilgung | `BANK_LOAN`, `DEBT_LOADING`, `CREDIT_RATING`, Risikosätze |
| **Inventar** | Endbestand | laut Regeln mit **Kosten** bewertet → „toter“ Bestand kann Wert schmälern; Stockouts schmälern **Erlöspotenzial** |

---

## 3) Entscheidungen → erwartete Richtung auf Treiber (Heuristik)

**Legende:** `↑` tendenziell positiv für Valuation-Treiber / Wert, `↓` negativ, `?` kontextabhängig.

| Entscheidung / Maßnahme | Cash | Profit (kurz/fristig) | Forderungen / Working Capital | Risiko / Rating | Valuation (typisch) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Mehr verkaufen **mit guter Marge**, kein Stockout | `↑`/`?` | `↑` | `↑` AR | `?` | `↑` |
| **Unter Kosten** verkaufen (Regelbruch / schlecht) | `?` | `↓` | `?` | `?` | `↓` |
| Stockouts (keine Ware) | — | `↓` (entgangene Marge) | `?` | `?` | `↓` |
| Teure Werbung ohne Absatzhebel | `↓` | `↓` | `?` | `?` | `↓` |
| Werbung dort, wo hohe Nachfrage **und** Verfügbarkeit | `↓` | `↑` | `?` | `?` | `↑` |
| Günstigerer Einkauf (Material), gleiche Qualität | `↑` | `↑` | `?` | `?` | `↑` |
| PO mit hohen **Fixkosten**/CO₂e (Preset 3) | `↓` | `↓` | `?` | `?` | `↓` |
| Transfer, der **Unterdeckung** behebt + Marge deckt Fix | `↓` | `↑` | `?` | `?` | `↑` |
| Sinnlose Transfers (Kosten > Nutzen) | `↓` | `↓` | `?` | `?` | `↓` |
| Große Investition ohne kurzfristigen Return | `↓` | `?` | `?` | `?` | `↓`/`?` |
| Investition senkt CO₂e-Kosten messbar (Preset 3) | `↓` | `↑` (weniger Carbon-Cash) | `?` | `?` | `↑`/`?` |
| Mehr Fremdkapital / schlechtere Bonität | `↑` kurz | `?` | `?` | `↓` | `?`/`↓` |

Diese Tabelle ist **kein Modell des Simulators**, sondern eine **Entscheidungshilfe**. Im Zweifel immer **Zeitreihe in `Company_Valuation`** und **Postings** prüfen.

---

## 4) Preset 3 (Sustainability) – zusätzliche Hebel

Aus `marketInformation.md` (Kurs-Preset, nicht 1:1 durch Repo belegt):

| Hebel | Wirkung auf Bewertung (qualitativ) |
| :--- | :--- |
| CO₂e bei Transport, PO, Lagererweiterung | erhöht **Kosten** (über Financial Postings) → tendenziell `PROFIT` ↓, sofern nicht kompensiert |
| Fixkosten alle 5 Tage | drücken regelmäßig auf Profit/Cash |
| Kapazitätserweiterung / höhere Abschreibung | kann kurzfristig **Last** sein, mittelfristig mehr Absatz möglich |

Agents: **Live-Werte** aus `current_game_rules` + `Financial_Postings` haben Vorrang vor statischen Tabellen.

---

## 5) Praktisches Monitoring für Agents

| Aufgabe | Daten | Vorgehen |
| :--- | :--- | :--- |
| „Steigt oder fällt unser Wert?“ | `Company_Valuation` | Letzte Zeile vs. vorige; Delta `COMPANY_VALUATION` |
| „Was hat sich parallel verändert?“ | gleiche `SIM_ELAPSED_STEPS` | `PROFIT`, `BANK_CASH_ACCOUNT`, `DEBT_LOADING`, `CREDIT_RATING`, Risikosätze |
| „Welche Kosten erklären den Drop?“ | `Financial_Postings` | Filter nach Step/Periode, Summen nach `GL_ACCOUNT_NAME` (z. B. Carbon) |
| „Lohnt sich Aktion X?“ | vor/nach Aktion (mehrere Steps) | Gegenbewegung von Marge (Sales) und Kostenposten abwarten |

---

## 6) Verweise

| Dokument | Nutzen |
| :--- | :--- |
| `spielregeln.md` | Siegbedingung, Endbewertung Lager zu Kosten, Kernregeln |
| `session_handover_2026-04-27.md` | Winner criterion, OData-Überblick |
| `marketInformation.md` | Kosten-/CO₂e-/DC-Logik Preset 3 |
| `task.md` | KPI- und Agenten-Blueprint |
| `Docs/*.pdf` | Offizielle Detaildefinition Company Valuation (falls dort ausgeführt) |

---

## 7) Regeln für zukünftige Agents (Kurz)

1. **Zielmetrik:** Maximiere **End-`COMPANY_VALUATION`**, nicht nur einen einzelnen Step-Umsatz.  
2. **Evidenz:** Jede Empfehlung idealerweise mit **Delta in `Company_Valuation`** und **verknüpften Postings** stützen.  
3. **Keine erfundene Formel:** Wenn die exakte Gewichtung unbekannt ist, **explizit unsicher** bleiben und aus Zeitreihen lernen.  
4. **Konfliktauflösung:** `current_game_rules` und OData-Snapshots **schlagen** Markdown, wenn Werte abweichen.  
5. **Nachhaltigkeit:** CO₂e und Fixkosten als **echte Profit- und Cash-Treiber** mitdenken (Preset 3).

---

*Letzte inhaltliche Ausrichtung: Team-Repo + Beispiel-Spalten aus `company_valuation.csv`. Formel der Bewertung: bewusst nicht spezifiziert — bitte Kursmaterial ergänzen, falls verfügbar.*
