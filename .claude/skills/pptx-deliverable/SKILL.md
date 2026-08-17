---
name: pptx-deliverable
description: Erzeugt eine PowerPoint-Präsentation (.pptx) im Projekt-/Tracker-Design für Stakeholder/Management. Baut auf dem pptx-Skill auf, aber mit den Design-Tokens und der Story-Struktur des Projekts. Auslöser: "Präsentation/Folien/Deck bauen", "PPT für das Meeting", "Management-Storyboard".
---

# pptx-deliverable — Präsentation im Projekt-Design

Erzeugt einen Foliensatz (.pptx) für Übergabe/Management. Nutzt für die technische Erzeugung den
**`pptx`-Skill** (python-pptx), setzt aber **unsere Tokens und Story-Struktur** darüber. Ablage in
`03_Presentations/`.

## Design-Tokens (verbindlich)
- **Schrift:** IBM Plex Sans (Fallback Calibri/Arial), Überschriften Gewicht 500, Fließtext 400.
- **Farben:** Text `#202124` · Sekundär `#5F6368` · Akzent (Stahl) `#3C4A5A` · Flächen weiß/`#F4F5F7`.
- **Ampel (gedämpft):** Grün `#2E7D32` · Gelb `#C9A227` · Orange `#E08600` · Rot `#C0392B`.
- **Flach & ruhig:** viel Weißraum, klare Hierarchie, keine 3D-/Schlagschatten-Deko, dezente Trennlinien.

## Story-Struktur (Default, anpassbar)
1. **Titel** (Thema · Datum · Owner). 2. **Management-Summary** (3–5 Kernaussagen).
3. **Kontext/Ausgangslage.** 4. **Befund/Analyse** (je Kernpunkt eine Folie, Evidenz nennen).
5. **Bewertung/Auswirkung.** 6. **Empfehlung & nächste Schritte.** 7. **Anhang** (Details/Quellen).

## Regeln
- **Inhalt aus Quelle:** speist sich aus `02_Analysis/` + `01_Documentation/okf/` — keine erfundenen Zahlen,
  Kennzahlen mit Herkunft. Was Hypothese ist, als solche kennzeichnen.
- **Konsistent** mit den HTML-Deliverables (gleiche Tokens) und dem Tracker-Look.
- **Wenig Text pro Folie** (Kernaussage + Beleg), Details in den Anhang.
- Erstellung über den `pptx`-Skill (Templates/Layouts, Notizen); danach Erkenntnisse/Verweis in OKF
  nachtragen (Skill `okr-okf-sync`).
