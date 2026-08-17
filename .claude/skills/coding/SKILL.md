---
name: coding
description: Konventionen für sauberes, lauffähiges, additives Coding im Projekt — vollständige Artefakte statt loser Fragmente, im Stil des umgebenden Codes, mit Validierung. Auslöser: "Skript/Code/Notebook/Funktion schreiben", "implementieren", "Query/Pipeline bauen", "refactoren".
---

# coding — Sauber, lauffähig, additiv

Leitplanken, damit Code konsistent, nachvollziehbar und sicher entsteht.

## Grundregeln
- **Vollständig & lauffähig:** komplette, direkt einsetzbare Artefakte (ganze Zelle/Datei/Funktion), keine
  losen Snippets. Abhängigkeiten/Imports nennen.
- **Stil des Umfelds:** Namensgebung, Struktur, Kommentar-Dichte an den vorhandenen Code anpassen — nicht den
  eigenen Stil aufzwingen. Erst umliegenden Code lesen.
- **Additiv vor destruktiv:** neue Dateien/Funktionen bevorzugen; Umbenennen/Verschieben/Löschen nur nach
  Freigabe (besonders ohne Git/Undo, z. B. auf OneDrive-Ablagen).
- **Validieren:** kompilieren/linten/testen bzw. an einem kleinen Fall prüfen, bevor „fertig" gemeldet wird.
  Fehlschläge ehrlich nennen (mit Ausgabe), nicht schönfärben.
- **Keine Secrets** im Code/Repo; Zugänge über lokale Config. Keine erfundenen Werte.

## Ablauf
1. Kontext lesen (umliegender Code, Konventionen, betroffene Dateien).
2. Umsetzen (vollständig, im Stil, additiv).
3. Prüfen (Compile/Test/kleiner Lauf) und Ergebnis belegen.
4. Ergebnis ablegen (`02_Analysis`/Projektcode); Wissen/Änderungen in OKF nachtragen (`okr-okf-sync`).

## Ablage
Analyse-/Hilfsskripte → `02_Analysis/`. Projektspezifischer Produktivcode in dessen eigenem Ordner
(dann projektspezifische Konventionen in `01_Documentation/okf/runbooks/` festhalten).
