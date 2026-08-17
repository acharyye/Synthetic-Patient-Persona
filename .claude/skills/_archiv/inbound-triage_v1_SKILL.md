---
name: inbound-triage
description: Verarbeitet neue Dokumente im Ordner 00_Inbound — liest & extrahiert jedes (PDF/PPTX/Word/Excel/CSV/Markdown/Bilder), klassifiziert nach Typ/Thema/Relevanz/OKR-Bezug, sortiert es in den richtigen Projektordner, verlinkt es in der OKF-Wissensbasis und archiviert das Original. Auslöser: "sortiere den Eingang", "Inbound verarbeiten", "neue Dokumente einsortieren", oder wenn in 00_Inbound Dateien liegen.
---

# inbound-triage — Eingang lesen, verstehen, einsortieren

Der Kern-Workflow: **Alles landet zuerst in `00_Inbound/`. Dieser Skill macht daraus geordnetes Wissen.**

## Ablauf

1. **Inventar:** `00_Inbound/` auflisten (ohne `_archiv/`). Je Datei Typ erkennen.
2. **Lesen/Extrahieren** je nach Format:
   - **PDF** → `pdf`-Skill (Text/Tabellen), bei Scans OCR.
   - **PPTX** → `pptx`-Skill (Folientext/Notizen).
   - **Word (.docx)** → `docx`-Skill.
   - **Excel/CSV** → `xlsx`-Skill bzw. direkt lesen; Struktur/Spalten erfassen.
   - **Markdown/Text** → direkt lesen.
   - **Bild/Screenshot** → visuell lesen; Kerninhalt beschreiben.
3. **Klassifizieren** je Dokument: **Typ** (Referenz-Doku / Analyse-Input / Präsentation / Rohdaten /
   Sonstiges), **Thema**, **Relevanz** (hoch/mittel/niedrig), **OKR-Bezug** (welches KR, falls erkennbar),
   **3–5-Zeilen-Extrakt** (worum geht's, warum relevant).
4. **Einsortieren** (Zielordner nach Typ):
   - Referenz-/Fachdoku → `01_Documentation/` (+ Kurz-Steckbrief in `01_Documentation/okf/references/`)
   - Analyse-Input → `02_Analysis/`
   - Präsentation → `03_Presentations/`
   - Rohdaten/Export → `05_Data/`
   Datei in den Zielordner legen; **Original nach `00_Inbound/_archiv/`** (nichts geht verloren).
5. **In OKF verlinken:** je relevantem Dokument ein Referenz-Konzept in `01_Documentation/okf/references/`
   anlegen/aktualisieren (`_TEMPLATE_concept.md` als Basis, Frontmatter `type: reference`), in dessen
   `index.md` verlinken. Wichtige Fakten daraus in das passende Konzept (`concepts/`, `architecture/`,
   `glossary/`) übernehmen — **nur Fakten aus der Quelle**.
6. **OKR-Abgleich:** wenn ein Dokument ein KR bewegt/nahelegt, im Tracker vermerken (Task/Notiz) bzw.
   ein neues KR **vorschlagen** (nicht still erfinden).
7. **Report als Tabelle:** Datei → Typ → Zielordner → OKF-Verweis → OKR-Bezug. Unklare Fälle explizit
   markieren und **nachfragen** statt raten.

## Regeln
- **Bei Unsicherheit fragen**, nicht raten (Klassifikation, Zielordner).
- **Additiv:** Originale werden verschoben (nach `_archiv`), nicht gelöscht. Kein Überschreiben.
- **Nur Fakten** aus der Quelle in die OKF — nichts erfinden, Herkunft nennen.
- Sensible/große Rohdaten: nur Steckbrief in OKF, Datei nicht versionieren.
