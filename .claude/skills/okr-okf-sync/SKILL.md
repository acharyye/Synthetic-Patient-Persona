---
name: okr-okf-sync
description: Der Pflicht-Abschluss nach jeder Arbeit, die Ergebnisse oder Wissen verändert — Tracker (OKR-Grade, Task-Progress/Status/Stand) und OKF-Wissensbasis synchron aktualisieren, Datum setzen, Dead-Link-Check. Auslöser: "Tracker aktualisieren", "OKR pflegen", "abschließen/committen", oder automatisch am Ende einer abgeschlossenen Aufgabe.
---

# okr-okf-sync — Steuerung & Wissen synchron halten

Schließt den Arbeitskreislauf. **Keine abgeschlossene Arbeit ohne diesen Schritt.**

## Ablauf

1. **KR-Grade aktualisieren:** das zur Aufgabe gehörende KR in `tracker/tracker_state.json` (Array `okrs`)
   ehrlich neu graden (0.0 nicht begonnen · 0.3 angefangen · 0.7 gut/Stretch · 1.0 voll). Baseline nie
   nachträglich verfälschen; neue KRs nur nach Absprache.
2. **Task pflegen:** zugehörigen Task `progress`/`status`/`stand` + `achievements`/`validations` ergänzen;
   `deps`/`knowledge` korrekt halten (nicht `blocked`/`ready` manuell setzen — wird aus `deps` abgeleitet).
3. **`lastModified`** im Tracker-State auf heute setzen.
4. **OKF nachziehen:** geändertes/neues Wissen in `01_Documentation/okf/` festhalten — betroffene Datei(en)
   anpassen, `timestamp` hochsetzen; neues Konzept via `_TEMPLATE_concept.md` + in der Ordner-`index.md`
   verlinken. Eine Datei = ein Konzept, nur Fakten.
5. **Tracker-App neu bauen — PFLICHT:** `python3 tracker/build_tracker.py` ausführen. Das bettet den neuen
   State und die OKF-Dateien in `tracker.html` ein **und macht den Dead-Link-Check** (Exit-Code 1 + Liste
   bei toten Links). Ohne diesen Schritt zeigt die App einen veralteten Stand.
6. **Tote Links beheben,** falls das Skript welche meldet, und erneut laufen lassen — kein toter Link.
7. **Kurz-Report:** welches KR sich wie bewegt hat, welche OKF-Dateien berührt wurden. Ein erledigter Task,
   dessen KR-Grade unverändert bleibt, ist ein Warnsignal (falsch zugeordnet?) — dann Zuordnung prüfen.

## Hinweis Tracker-Datenfluss
`tracker_state.json` ist die **Quelle der Wahrheit**, der Browser-`localStorage` nur der Arbeitsstand.
Für KI-Updates das JSON pflegen (inkl. `lastModified` auf heute!) und `build_tracker.py` laufen lassen —
die App übernimmt den neueren Stand beim nächsten Öffnen automatisch und sichert den alten ins Backup.
Hat der Owner zwischenzeitlich **im Browser** gearbeitet: erst von ihm ein "↧ Export JSON" holen und
einarbeiten, sonst geht seine Arbeit im Backup unter. Nur **Daten** ändern, nie die Render-Logik.
