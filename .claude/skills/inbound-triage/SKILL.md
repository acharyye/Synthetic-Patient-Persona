---
name: inbound-triage
description: Verarbeitet neue Dokumente im Ordner 00_Inbound als Graph — Fan-out (1 Subagent pro Datei liest, extrahiert, klassifiziert nach Schema), Fan-in (dedupliziert, sortiert ein, verlinkt in OKF, archiviert, OKR-Abgleich). Auslöser: "sortiere den Eingang", "Inbound verarbeiten", oder wenn in 00_Inbound Dateien liegen.
---

# inbound-triage — Eingang als Fan-out/Fan-in verarbeiten

**Topologie: Diamond.** Split (Inventar) → parallele Arbeit (1 Node/Datei) → Merge (Single-Writer).
Regeln aus Skill `workflow` gelten (insb. Single-Writer-Fan-in, Schema-Verträge).

## Phase 1 — Split (Code, kein Agent)
`00_Inbound/` auflisten (ohne `_archiv/`). Bei < 3 Dateien: sequenziell wie früher arbeiten
(Edge-Test aus Skill `workflow`). Sonst weiter mit Phase 2.

## Phase 2 — Fan-out (1 Subagent pro Datei, parallel)
Jeder Subagent bekommt GENAU EINE Datei und liefert nach diesem Schema (Pflicht, validiert):

    { datei, typ: "referenz|analyse-input|praesentation|rohdaten|sonstiges",
      thema, relevanz: "hoch|mittel|niedrig", okrBezug (KR-Id oder null),
      extrakt (3–5 Zeilen), zielordner, unklar: bool, unklarGrund }

Lese-Mechanik je Format wie bisher: PDF→pdf-Skill (Scans: OCR), PPTX→pptx-Skill, DOCX→docx-Skill,
Excel/CSV→xlsx-Skill/direkt, MD/Text→direkt, Bild→visuell. Extraktions-/Klassifikations-Nodes
dürfen auf ein günstigeres Modell geroutet werden (Skill `workflow`, Modell-Staffelung).
Fehlgeschlagene Nodes vor dem Fan-in herausfiltern; die Dateien im Abschlussreport als
„nicht lesbar" ausweisen (nicht stillschweigend weglassen).

## Phase 3 — Fan-in (Kanten = Code, Mutation = Single-Writer)
1. **Code:** Ergebnisse einsammeln, gegen bestehende `okf/references/` deduplizieren,
   nach Relevanz sortieren, `unklar`-Fälle beiseitelegen.
2. **Ein Agent (Session-Modell):** OKR-Abgleich über den GESAMTEN Satz — bewegt/nahelegt etwas
   ein KR? Neues KR nur VORSCHLAGEN, nicht anlegen.
3. **Single-Writer (Haupt-Ablauf):** Dateien in Zielordner legen, Originale →
   `00_Inbound/_archiv/`, je relevantem Dokument Referenz-Konzept in `okf/references/`
   (via `_TEMPLATE_concept.md`, `type: reference`) + `index.md`-Link. Wichtige Fakten in
   passende Konzepte übernehmen — nur Fakten aus der Quelle.
4. **Report als Tabelle:** Datei → Typ → Zielordner → OKF-Verweis → OKR-Bezug → Status.
   `unklar`-Fälle GESAMMELT in einem Block nachfragen — nicht raten.
5. **Abschluss:** Skill `okr-okf-sync` (Tracker-Task, Datum, Dead-Link-Check).

## Regeln
- Additiv: Originale nach `_archiv`, nichts löschen/überschreiben.
- Subagenten sind read-only auf OKF/Tracker (Single-Writer-Regel, Skill `workflow`).
- Sensible/große Rohdaten: nur Steckbrief in OKF, Datei nicht versionieren.
