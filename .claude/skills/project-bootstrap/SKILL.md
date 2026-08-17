---
name: project-bootstrap
description: Beim ERSTEN Start eines neuen Projekts aus diesem Template. Legt die saubere Ordnerstruktur an, erzeugt CLAUDE.md aus der Vorlage, befüllt das OKF-Grundgerüst und einen ersten OKR-Entwurf — und triggert die Inbound-Sortierung, wenn schon Dokumente da sind. Auslöser: "neues Projekt starten", "Projekt einrichten", "Bootstrap", "aufsetzen", oder eine leere/frische Kopie dieses Templates.
---

# project-bootstrap — Neues Projekt sauber aufsetzen

Ziel: aus der Template-Kopie ein arbeitsfähiges Projekt machen — Struktur, oberste Arbeitsregel,
Wissens-/Steuerungs-Grundgerüst — und den Eingang direkt verarbeiten.

## Ablauf

1. **Projekt-Eckdaten klären** (kurz fragen, falls unbekannt): Projektname, Owner, 1-Satz-Ziel/Scope.
2. **Ordnerstruktur sicherstellen** (anlegen, falls fehlt):
   `00_Inbound/_archiv`, `01_Documentation` (mit `okf/`), `02_Analysis`, `03_Presentations`,
   `04_Deliverables`, `05_Data`, `tracker/`, `.claude/skills/`.
3. **CLAUDE.md erzeugen:** `00_AGENT_INSTRUCTIONS.md` → `CLAUDE.md` in die Projektwurzel kopieren und **alle
   `<PLATZHALTER>`** (Projektname/Owner/Datum) füllen. (Nicht das Template-Original überschreiben — kopieren.)
   Für Cursor/Windsurf/Aider stattdessen bzw. zusätzlich als `AGENTS.md`.
   ⚠️ **Nicht** `INSTRUCTIONS_for_LLM.md` kopieren — das ist nur ein Wegweiser-Stub, keine Arbeitsregel.
4. **OKF-Grundgerüst:** `01_Documentation/okf/index.md` mit Projekt-Steckbrief (Zweck, Scope, Kernbegriffe)
   füllen. 2–3 zentrale Begriffe ins `glossary/` (je `_TEMPLATE_concept.md` kopieren + in `index.md` verlinken).
5. **Eingang verarbeiten:** Liegt etwas in `00_Inbound/`, den Skill **`inbound-triage`** ausführen
   (einsortieren + OKF-Erstbefüllung). Die Inbound-Inhalte sind die beste Quelle für Schritt 6.
6. **OKR-Entwurf:** aus Ziel + Inbound-Inhalten **3–5 Objectives mit je 2–5 Key Results** vorschlagen
   (Outcomes, keine To-dos) und nach Freigabe in `tracker/tracker_state.json` schreiben. Grading-Start 0.0.
7. **Kurz-Report:** was angelegt/befüllt wurde, welche OKRs vorgeschlagen sind, und der Standard-Ablauf
   ab jetzt (`CLAUDE.md` §6 / `PROCESS.md` §D).

## Regeln
- **Additiv & vorsichtig:** nichts Bestehendes überschreiben/löschen ohne Rückfrage.
- KRs sind **Ergebnisse, keine Aufgaben**. Lieber wenige, gute KRs.
- Wenn OneDrive/kein Git: keine destruktiven Moves ohne Freigabe (siehe `PROCESS.md`).
