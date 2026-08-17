---
name: gantt-roadmap
description: Erzeugt ein teilbares Gantt-/Roadmap-/Timeline-HTML aus tracker_state.json (Stages, Tasks, Abhängigkeiten, Progress) oder einer Aufgabenliste — im Projekt-Design, self-contained, für Übergaben/Deliverables. Auslöser: "Gantt", "Roadmap", "Zeitplan/Timeline visualisieren", "Projektplan als HTML".
---

# gantt-roadmap — Gantt/Roadmap als teilbares HTML

Der Tracker hat intern einen Gantt; **dieser Skill erzeugt ein eigenständiges, teilbares HTML** (für
Management/Übergabe) aus denselben Daten. Ablage in `04_Deliverables/`.

## Datenquelle
`tracker/tracker_state.json` → `stages[].tasks[]` mit `startWeek`/`endWeek`, `progress`, `status`,
`deps`, `title`. Alternativ eine vom Owner gelieferte Aufgabenliste.

## Ablauf
1. Daten laden (Stages + Tasks; Wochenraster `startWeek..endWeek`, `todayWeek` für „heute"-Linie).
2. Gantt rendern: Zeilen = Tasks (gruppiert je Stage), Balken = Zeitspanne, **Füllung = `progress`**,
   Farbe = `status` (Ampel gedämpft), **Abhängigkeitslinien aus `deps`**, „Heute"-Markierung.
3. Design: Tokens aus [`../html-deliverable/design-guidelines.html`](../html-deliverable/design-guidelines.html)
   (IBM Plex, Stahl-Akzent, flach, Light/Dark), self-contained (CSS/JS inline), responsive
   (breites Raster in `overflow-x:auto`).
4. Speichern nach `04_Deliverables/<name>_gantt.html`; kurz erklären, was drin ist.

## Regeln
- **Nur Daten visualisieren** — nichts erfinden; Progress/Status aus dem Tracker.
- `blocked`/`ready` aus `deps` ableiten (nicht manuell). Legende für Status/Progress mitliefern.
- Bei sehr vielen Tasks nach Stage/Status filterbar machen; horizontal scrollen statt Seite sprengen.
