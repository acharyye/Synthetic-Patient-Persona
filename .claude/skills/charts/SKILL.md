---
name: charts
description: Erzeugt Diagramme (Donut, Bar, Line, Heatmap, Sankey, Graph, Gauge) im Projekt-Design — bevorzugt eigenes SVG oder first-party (Plotly/Altair/ECharts), mit den hart gelernten ECharts-Gotchas. Auslöser: "Diagramm/Chart/Visualisierung bauen", "Donut/Balken/Heatmap/Sankey", "Daten visualisieren".
---

# charts — Diagramme im Design-System

Konsistente, robuste Visualisierungen. **Farben immer aus den Design-Tokens**
([`../html-deliverable/design-guidelines.html`](../html-deliverable/design-guidelines.html)); Statusfarben nur
funktional (Ampel gedämpft), kategoriale Reihen aus einer festen Palette.

## Reihenfolge der Mittel (robust → riskant)
1. **Eigenes SVG** (Donut/Bar/Gauge) — kein Build, kein Component-Risiko, voll themebar. Für einfache Charts erste Wahl.
2. **First-party** `st.plotly_chart`/`st.altair_chart`/`st.bar_chart` (in Streamlit) — sicher.
3. **ECharts** (`streamlit-echarts`) — mächtig (Heatmap/Sankey/Graph/Gauge), aber **bidirektionale
   Custom-Component** → nur wenn nötig, immer mit **Fallback** auf SVG/first-party.

## ⚠️ Gelernte ECharts-Gotchas (unbedingt beachten)
- **`markLine` ODER `visualMap` auf einer Linien-Serie crasht** streamlit-echarts
  („Cannot read properties of undefined (reading 'coord')"). **Lösung:** Schwellwert-Linie als **eigene flache
  Serie** (`data=[ref]*n`, gestrichelt, `endLabel`); „über/unter Schwelle"-Farbe per **per-point `itemStyle`**
  im Datenobjekt — **nicht** `visualMap`.
- **3-Ring-Gauge** = drei **separate** Gauge-Serien mit verschiedenen `radius` (nicht eine Serie mit 3 Daten).
- **Heatmap** mit zwei Farbskalen (gut/schlecht): Farbe **explizit je Zelle** via `itemStyle` setzen (nicht
  ein globales visualMap), Text mittig, Textfarbe nach Hintergrund.
- Nach Component-Änderungen Browser hart/Inkognito neu laden (JS-Cache). Keine externen CDNs in Deliverables.

## Ablauf
1. Chart-Typ passend zur Aussage wählen (Donut=Anteile, Bar=Vergleich, Line=Zeit, Heatmap=Matrix, Sankey=Fluss, Graph=Beziehungen).
2. Mit Tokens/Fonts (IBM Plex, `backgroundColor:transparent`) rendern; Legende/Achsen ruhig.
3. In ein Deliverable (`04_Deliverables`) oder Analyse (`02_Analysis`) einbetten; Datenherkunft nennen.
