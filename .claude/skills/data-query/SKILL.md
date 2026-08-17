---
name: data-query
description: Sichere, read-only Datenabfragen (SQL/Warehouse/Datenbank/CSV/Excel) für Analytics — erst klein validieren, dann skalieren; Ergebnisse mit Herkunft dokumentieren und in die Wissensbasis nachtragen. Auslöser: "abfragen", "SQL", "wie viele/welche … in den Daten", "Datenbank/Warehouse prüfen", "Kennzahl aus den Daten".
---

# data-query — Daten sicher abfragen & belegen

Liefert belastbare Zahlen aus der Datenquelle — **read-only**, nachvollziehbar, dokumentiert.

## Prinzipien (wichtig)
- **Read-only.** Keine schreibenden/verändernden Statements ohne ausdrückliche Freigabe (kein DROP/DELETE/
  UPDATE/INSERT/overwrite). Zugangsdaten/Secrets nie im Klartext ablegen oder ausgeben.
- **Erst klein validieren, dann skalieren.** Neue Quelle/Query zuerst an 1–2 Fällen prüfen (Schema, Beispiel-
  zeilen, Plausibilität) — **nicht** allein auf einen „SUCCESS"-Status vertrauen.
- **Keine erfundenen Zahlen.** Jede Kennzahl aus einer echten Abfrage; **Herkunft nennen** (Tabelle/Query/Datei).
- **Schema statt raten.** Bei Unklarheit über Tabellen/Spalten zuerst `DESCRIBE`/`information_schema` bzw.
  Spaltenköpfe prüfen, dann abfragen.

## Ablauf
1. **Zielgröße** klar fassen (welche Kennzahl/Frage, welche Granularität).
2. **Schema/Quelle prüfen** (Tabellen/Spalten/Typen; bei Dateien: Header/Struktur).
3. **Klein testen** (LIMIT, Beispielzeilen, Grenzfälle) → Plausibilität checken.
4. **Voll abfragen**, Ergebnis prüfen (Nullen, Duplikate, Fan-out durch Joins vermeiden).
5. **Dokumentieren:** Befund + Query + Herkunft in `02_Analysis/` (oder direkt in eine Analyse); relevante
   Fakten/Definitionen in `01_Documentation/okf/` nachtragen (Skill `okr-okf-sync`).

## Hinweise
- Zugangs-/Verbindungsdetails gehören in `01_Documentation/okf/runbooks/` (ohne Secrets) — Token/Passwörter in
  eine lokale Config (z. B. `~/.config`), nicht ins Repo.
- Große/sensible Rohexporte nach `05_Data/`, nicht versionieren; nur Steckbrief in OKF.
