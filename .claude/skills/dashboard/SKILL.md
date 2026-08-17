---
name: dashboard
description: Baut ein INTERAKTIVES analytisches HTML-Dashboard (KPI-Kacheln + mehrere Charts + Filter/Tabs), self-contained, im Projekt-Design — die interaktive Stufe über den statischen HTML-Bericht hinaus. Auslöser: "Dashboard bauen", "interaktive Auswertung/Übersicht", "Analyse-Oberfläche mit Filtern".
---

# dashboard — Interaktives Analyse-HTML

Für explorative Übersichten: **KPI-Kacheln + Diagramme + Filter/Tabs** in EINER teilbaren HTML-Datei.
Ablage in `04_Deliverables/`. Abgrenzung: `html-deliverable` = statischer Bericht; **`dashboard` = interaktiv**.

## Aufbau
1. **Kopf** (Titel/Scope) · **KPI-Reihe** (Kacheln, Ampel gedämpft) · **Chart-Bereich** (via Skill `charts`) ·
   **Filter/Tabs** (Zeitraum/Kategorie/Segment) mit reinem JS (kein Framework).
2. **Daten** eingebettet als JSON im HTML (aus `data-query`/`02_Analysis`), keine Live-Requests → self-contained.
3. **Design:** Tokens aus [`../html-deliverable/design-guidelines.html`](../html-deliverable/design-guidelines.html)
   (IBM Plex, Stahl-Akzent, flach, Light/Dark), responsive (Grid, `overflow-x:auto` für breite Elemente).

## Regeln
- **Self-contained:** CSS/JS/Daten inline, Bilder als `data:`-URI, keine externen CDNs.
- **Robuste Charts:** eigenes SVG/first-party bevorzugt; ECharts nur mit Fallback und den Gotchas aus `charts`.
- **Nur echte Daten** (Herkunft nennen); klare Leerzustände statt Platzhalter-Zahlen.
- Erkenntnisse/Definitionen danach in OKF nachtragen (`okr-okf-sync`).
