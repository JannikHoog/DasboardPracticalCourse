# Markt- und Supply-Chain-Informationen (Preset 3 – Manufacturing Sustainability)

Quelle: `Docs/2023-24_Preset3_Manuf_Sustainability_EN.pdf` (Stand laut bereitgestellten Slides/Screenshots).  
Zur schnellen Prüfung und Anpassung in kleinen Tabellen zusammengefasst.

---

## Vertriebskanäle (Kunden / DC)

| DC | Segment (Kurz) | Packgrößen | Bestellmuster (ca.) | Zahlungsziel | Preissensitivität | Werbesensitivität | Marktgröße (ca., pro Team / Woche = 5 Tage) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 10 | Hypermarkets | nur **1 kg** | 3 Produkte gleichzeitig | 20 Tage | sehr hoch | niedrig | ca. **90.000 €** |
| 12 | Grocery chains | **500 g + 1 kg** | 4 Produkte gleichzeitig | 10–20 Tage | hoch | mittel | ca. **360.000 €** |
| 14 | Independent grocers | nur **500 g** | 1 Produkt gleichzeitig | 1–20 Tage | mittel | hoch | ca. **135.000 €** |

---

## Filialstruktur nach Region (Anzahl Outlets)

| Region | Hypermarkets | Grocery stores | Independent grocers |
| :--- | ---: | ---: | ---: |
| West | 3 | 17 | 40 |
| North | 2 | 19 | 45 |
| South | 7 | 23 | 38 |
| **Total** | **12** | **59** | **123** |

---

## Regionale Lagerorte (Deutschland)

| Storage Location (Bezeichnung) | Region |
| :--- | :--- |
| Storage Location North | North |
| Storage Location West | West |
| Storage Location South | South |

---

## Fertigprodukte (SKU-Muster)

| Produkt | 500 g Code | 1 kg Code |
| :--- | :--- | :--- |
| Nut | `*-F01` | `*-F11` |
| Blueberry | `*-F02` | `*-F12` |
| Strawberry | `*-F03` | `*-F13` |
| Raisin | `*-F04` | `*-F14` |
| Original | `*-F05` | `*-F15` |
| Mixed | `*-F06` | `*-F16` |

*(Präfix z. B. `JJ-` je nach Team im Spiel.)*

---

## Einkaufbare Ressourcen (Rohstoffe & Verpackung)

Diese Materialien werden über **ZME12** bei den genannten Lieferanten beschafft (siehe Abschnitt Lieferanten).  
Codes sind teamrelativ: z. B. `JJ-R01` … `JJ-P04`.

### Rohstoffe (Food) – `R01` … `R06`

| Code | Bezeichnung (engl. Slide) | Typ |
| :--- | :--- | :--- |
| `*-R01` | Nuts | Rohstoff |
| `*-R02` | Blueberries | Rohstoff |
| `*-R03` | Strawberries | Rohstoff |
| `*-R04` | Raisins | Rohstoff |
| `*-R05` | Wheat | Rohstoff |
| `*-R06` | Oats | Rohstoff |

| Beschaffung | Lieferanten |
| :--- | :--- |
| Alle R01–R06 | **V01** oder **V11** |

### Verpackung (Packaging) – `P01` … `P04`

| Code | Bezeichnung (engl. Slide) | Typ |
| :--- | :--- | :--- |
| `*-P01` | Large Boxes | Verpackung |
| `*-P02` | Large Bags | Verpackung |
| `*-P03` | Small Boxes | Verpackung |
| `*-P04` | Small Bags | Verpackung |

| Beschaffung | Lieferanten |
| :--- | :--- |
| Alle P01–P04 | **V02** oder **V12** |

---

## Lieferanten – Rohstoffe (Food)

| Lieferant | Name (Slide) | Lead time | Zahlungsziel | Materialien (Kurz) |
| :--- | :--- | :--- | :--- | :--- |
| V01 | FoodBroker Inc. | 2–3 Tage | 20 Tage | R01–R06 (Nuts, Blueberries, Strawberries, Raisins, Wheat, Oats) |
| V11 | Fruits Haven | 1–4 Tage | 20 Tage | gleiche R01–R06 |

| Materialtyp | Lieferanten | Transaktion (Slide) |
| :--- | :--- | :--- |
| Food raw materials | **V01** oder **V11** | ZME12 |

---

## Lieferanten – Verpackung (Packaging)

| Lieferant | Name (Slide) | Lead time | Zahlungsziel | Materialien (Kurz) |
| :--- | :--- | :--- | :--- | :--- |
| V02 | Continental Printing Co. | 2–3 Tage | 20 Tage | P01–P04 (Large/Small Boxes & Bags) |
| V12 | Timber Prints Inc. | 1–4 Tage | 20 Tage | gleiche P01–P04 |

| Materialtyp | Lieferanten | Transaktion (Slide) |
| :--- | :--- | :--- |
| Packaging | **V02** oder **V12** | ZME12 |

**Hinweis (Slide):** Preise unterscheiden sich je Material und Lieferant; es gibt weitere Unterschiede zwischen den Lieferanten (nicht nur Preis).

---

## Logistik – Kosten (€, aus Netzwerk-Slide)

| Route / Vorgang | Bezugsgröße | Kosten |
| :--- | :--- | :--- |
| Supplier **V01** → Main Warehouse | pro PO | **0 €** |
| Supplier **V11** → Main Warehouse | pro PO | **1.000 €** |
| Supplier **V02** → Main Warehouse | pro PO | **0 €** |
| Supplier **V12** → Main Warehouse | pro PO | **2.000 €** |
| Main Warehouse → Regional Locations (North / West / South) | pro **regional transfer** | **500 €** |
| Main Warehouse → Kunden (DC 10, 12, 14) | pro **Einheit** | **0,05 €** |
| Regional Locations → Kunden (DC 10, 12, 14) | pro Einheit | **0 €** (keine Versandkosten laut Slide) |

---

## Logistik – CO₂e (kg, aus CO₂e-Slide)

| Route / Vorgang | Bezugsgröße | CO₂e |
| :--- | :--- | :--- |
| Supplier **V01** & **V11** → Main Warehouse | pro PO | **10.000 kg** (je nach Zuordnung pro Lieferant; Slide nennt beide 10.000) |
| Supplier **V02** → Main Warehouse | pro PO | **6.000 kg** |
| Supplier **V12** → Main Warehouse | pro PO | **15.000 kg** |
| Main Warehouse → Regional Locations | pro **Transfer** | **750 kg** |
| Main Warehouse → Kunden (DC 10, 12, 14) | pro **Einheit** | **0,25 kg** |
| Regional Locations → Kunden | pro **Sales Order** | **200 kg** |

---

## Main Warehouse – täglicher Overhead (CO₂e)

| Kategorie | kg CO₂e / Tag |
| :--- | ---: |
| Purchased Energy | 500 |
| Other Overhead | 400 |

---

## Main Warehouse – Lagerkapazität und Kosten bei Erweiterung

*Zusätzliche Kapazität: Abrechnung automatisch (Slide-Fußnote).*

| Produkttyp | aktuelle Kapazität | Kosten pro Tag (je **+50.000** Einheiten*) | CO₂e-Kosten pro Tag (je **+50.000** Einheiten*) |
| :--- | :--- | :--- | :--- |
| Finished products (Kisten) | 250.000 Boxen | **500 €** | **2.500 kg** CO₂e/Tag |
| Raw materials | 250.000 kg | **1.000 €** | **5.000 kg** CO₂e/Tag |
| Packaging (Tüten & Boxen) | 750.000 Einheiten | **100 €** | **1.500 kg** CO₂e/Tag |

\*Begriff laut Slide: „additional 50,000 units“ / „billed automatically“.

---

## Fixkosten (alle 5 Tage, automatisch)

| Kostenart | Betrag (€ / 5 Tage) |
| :--- | ---: |
| Labor | 20.000 |
| Manufacturing overhead | 15.000 |
| S, G & A | 40.000 |
| Depreciation (building) | 1.250 |
| Depreciation (equipment) | 50.000 |

**Fußnote (Slide):** Zusätzliche Kapazität kann die Abschreibungen auf Equipment erhöhen.

---

## Implikationen fürs Dashboard / Entscheidungen (Kurz)

| Thema | Konsequenz |
| :--- | :--- |
| DC 10 vs 14 | unterschiedliche Packgrößen und Werbe-/Preissensitivität → Sortiment & Messaging pro Kanal, nicht regionaler Listenpreis |
| Region vs DC | Region = geografische Nachfrage/Lager; DC = Kanaltyp → Marketing/Transfer vs. Pricing getrennt denken |
| Direktlieferung Zentrallager | günstig €/Stück aus Regionssicht, aber CO₂e pro Stück aus Zentrallager; Region → Kunde hat CO₂e pro Sales Order |
| Lieferantenwahl | PO-Fixkosten und CO₂e pro Lieferant stark unterschiedlich → nicht nur Stückpreis |

---

*Bei Abweichung zu eurem Live-Spiel (OData `current_game_rules`) gelten die **im System hinterlegten Werte**; diese Datei dokumentiert die **offiziellen Preset-3-Slide-Werte** zur Orientierung.*
