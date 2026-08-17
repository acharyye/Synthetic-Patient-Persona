---
name: office-docs
description: Formelle Office-Dokumente (Word .docx, Excel .xlsx, PDF) im Projekt-Stil erstellen/lesen — dünner Wrapper um die globalen docx/xlsx/pdf-Skills mit Konventionen für Ablage, Design und Herkunft. Auslöser: "Word-Dokument/Bericht/Memo/Brief", "Excel-Auswertung/Tabelle", "PDF erstellen/lesen/zusammenfassen".
---

# office-docs — Office-Dokumente im Projekt-Stil

**Nicht die Mechanik neu erfinden** — die globalen Skills nutzen:
- **Word (.docx)** → globaler `docx`-Skill · **Excel/CSV (.xlsx)** → globaler `xlsx`-Skill ·
  **PDF** (lesen/erstellen/mergen/OCR) → globaler `pdf`-Skill · **PowerPoint** → eigener `pptx-deliverable`.

Dieser Skill ergänzt nur **Konventionen** darüber:

## Konventionen
- **Design:** dieselbe Sprache wie die HTML-Deliverables — IBM Plex/klar, gedämpfte Ampel, Stahl-Akzent
  `#3C4A5A`, flach, viel Weißraum. Kopf: Titel · Datum · Owner.
- **Struktur (Bericht/Memo):** Management-Summary → Kontext → Befund (mit Beleg) → Bewertung → Empfehlung →
  Anhang/Quellen. Wenig Text, klare Hierarchie.
- **Inhalt aus Quelle:** speist sich aus `02_Analysis/` + `01_Documentation/okf/`; **keine erfundenen Zahlen**,
  Kennzahlen mit Herkunft; Hypothesen kennzeichnen.
- **Ablage:**
  - Bericht/Memo/Brief (docx/pdf) → `04_Deliverables/`
  - Datenauswertung/Arbeitsmappe (xlsx) → `05_Data/` (Ergebnis) bzw. `02_Analysis/` (Analyse)
  - Präsentation → `03_Presentations/` (Skill `pptx-deliverable`)
- **Sensibles/Großes** nicht versionieren; nur Steckbrief in OKF.

## Ablauf
1. Format + Zielgruppe klären. 2. Inhalt aus Analyse/OKF ziehen. 3. Mit dem passenden globalen Skill erzeugen,
Konventionen oben anwenden. 4. Am richtigen Ort ablegen. 5. Verweis/Erkenntnis in OKF nachtragen (`okr-okf-sync`).
