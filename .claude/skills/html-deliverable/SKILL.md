---
name: html-deliverable
description: Erzeugt ein auslieferbares HTML-Artefakt (Bericht, Backlog, Dashboard, Übergabe-Seite) im Projekt-/Tracker-Design — flach, IBM Plex Sans, self-contained, theme-aware (Light/Dark), responsive. Auslöser: "HTML-Bericht/Seite/Backlog/Dashboard bauen", "als HTML aufbereiten", "Übergabe-Seite", "Design-Guidelines".
---

# html-deliverable — HTML im Tracker-Design

Baut eine **eigenständige, teilbare HTML-Datei** (eine Datei, keine externen Abhängigkeiten) im konsistenten
Projekt-Look. Ablage in `04_Deliverables/`.

> **Verbindliche Design-Referenz:** [`design-guidelines.html`](design-guidelines.html) (liegt neben dieser
> SKILL.md). **Zuerst ansehen** — sie zeigt alle Tokens (Farben/Typografie/Radien), Komponenten (Kacheln,
> Tabellen, Chips, Ampel) und Light/Dark 1:1 aus dem Tracker. Nimm sie als **Startpunkt/Kopiervorlage** für
> Kopf, CSS-Variablen und Komponenten — nicht bei Null anfangen.

## Design-Tokens (verbindlich)
- **Schrift:** IBM Plex Sans (System-Fallback `system-ui, sans-serif`), **nur Gewichte 400/500** (kein 300/700).
- **Farben (Light):** Text `#202124` · Sekundär `#5F6368` · Linien `#E6E8EB` · Hintergrund `#F4F5F7` ·
  Kachel `#FFFFFF` · Akzent (Stahl) `#3C4A5A`.
- **Ampel (gedämpft):** Grün `#2E7D32` · Gelb `#C9A227` · Orange `#E08600` · Rot `#C0392B`.
- **Radien:** Kacheln 12px · Controls 10px · Bars 8px. **Schatten** einheitlich `0 1px 2px rgba(0,0,0,.05)`.
- **Flach** — kein Glassmorphism, keine Verläufe als Deko. Solide Kacheln auf ruhigem Hintergrund.

## Regeln
- **Self-contained:** CSS/JS inline, Bilder als `data:`-URI. Keine externen CDNs/Fonts/Requests.
- **Theme-aware:** Light + Dark via `@media (prefers-color-scheme: dark)` (Dark: bg `#1B1A18`, Fläche `#232220`,
  Text `#ECEAE6`, Linien `#383530`, Akzent `#9DB2C9`). Farben als CSS-Variablen, in beiden Modi definiert.
- **Responsive:** relative Einheiten, Flex/Grid, `max-width:100%` auf Bilder; breite Tabellen/Diagramme in
  `overflow-x:auto` — die Seite selbst scrollt nie horizontal.
- **Konsistenz:** Titel/KPI-Kacheln/Tabellen/Chips im selben System wie der Tracker
  (`../tracker/tracker.html`) und die Design-Guidelines des Projekts.

## Ablauf
1. Inhalt/Struktur aus Quelle (Analyse/OKF) festlegen — was ist die Kernaussage, wer liest es?
2. HTML mit den Tokens oben schreiben (Kopf, Kacheln/Tabellen, ruhige Ampel nur für Status).
3. In `04_Deliverables/<name>.html` speichern; kurz erklären, was drin ist.
4. Erkenntnisse/Struktur in OKF nachtragen (Skill `okr-okf-sync`).
