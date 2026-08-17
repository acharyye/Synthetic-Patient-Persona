---
name: workflow
description: Baut breite Aufgaben als Graph statt als Kette — Fan-out über Subagenten mit Schema-Verträgen, Fan-in als einziger Schreiber von Tracker & OKF, Verifier vor der Synthese. Auslöser: "Workflow", "parallel prüfen/lesen/analysieren", oder ≥3 unabhängige gleichartige Einheiten (Dateien, Teilfragen, Quellen, Metriken, Module).
---

# workflow — Breite Aufgaben als Graph

Meta-Skill: definiert, WANN und WIE der Agent eine Aufgabe als Graph (Fan-out/Fan-in) statt als
Kette ausführt. Die Fach-Skills (`inbound-triage`, `analysis`, …) referenzieren diese Regeln.

## Wann Graph, wann Kette (Edge-Test)

1. Zerlege die Aufgabe in Einheiten. Frage je „und dann": **liest Schritt B den Output von A?**
   - Nein → keine Kante → unabhängig → parallelisierbar.
   - Ja → echte Kante → Reihenfolge bleibt.
2. **Graph ab ≥ 3 unabhängigen, gleichartigen Einheiten.** Darunter sequenziell arbeiten.
3. Der OKR-Kreislauf (CLAUDE.md §6) bleibt IMMER eine Kette. Der Graph lebt in Schritt 3 („Arbeiten").

> **Ausführungsform.** Die Bausteine sind werkzeug-neutral formuliert. In **Claude Code (CLI)** heißt das:
> Fan-out = mehrere Subagenten-Aufrufe **in EINEM Nachrichtenblock** (nur so laufen sie wirklich parallel),
> Kanten = Bash/Python-Schritte oder direkte Auswertung im Hauptlauf, Schema = im Subagent-Prompt
> vorgeschriebenes JSON, das der Hauptlauf beim Fan-in prüft. Im **Agent SDK** entsprechen dem
> `agent({schema})`, `parallel()` und `pipeline()`. Gleiche Regeln, andere Syntax.

## Die fünf Bausteine

1. **Node-Vertrag:** Jeder Subagent bekommt begrenzten Input (explizit im Prompt übergeben, nie „aus dem
   gemeinsamen Kontext angenommen") und liefert JSON nach vorgegebenem Schema. Der Hauptlauf **validiert
   beim Fan-in** und fordert bei Mismatch genau diesen einen Node neu an. Ein Node = ein Job.
2. **Fan-out:** alle Einheiten gleichzeitig starten; ein fehlgeschlagener Subagent wird zu „kein Ergebnis"
   und versenkt nicht den Batch → Ausfälle vor dem Fan-in herausfiltern und im Report als solche
   ausweisen. Fan-in-Logik muss fehlende Einträge tolerieren, nie den vollen Satz voraussetzen.
3. **Kanten sind Code:** Flatten/Dedupe/Filter/Sortieren zwischen Stufen ist deterministische Mechanik —
   im Hauptlauf erledigen (ggf. als kleines Skript), nicht delegieren. KEINEN Agenten für Plumbing
   spawnen; Agenten nur für Urteil (klassifizieren, bewerten, synthetisieren).
4. **Verifier vor Synthese:** Zentrale Behauptungen/Befunde durchlaufen vor der Synthese
   unabhängige Skeptiker mit verschiedenen Linsen (z. B. „Quelle hält", „Rechnung stimmt",
   „widerspricht internem Wissen?"). Überlebt eine Behauptung < 2/3, gilt sie als Hypothese,
   nicht als Befund. Verifier-Verdikte werden im Tracker-Task unter `validations` protokolliert.
5. **Single-Writer-Fan-in (PFLICHT):** Subagenten schreiben NIE `tracker_state.json`, NIE in
   `01_Documentation/okf/`, verschieben NIE Dateien. Alle Mutation passiert nach dem Fan-in im
   Haupt-Ablauf (→ Skill `okr-okf-sync` als Abschluss). Worktree-Isolation nur, wenn Subagenten
   wirklich parallel Projektdateien schreiben müssen.

## Effizienz-Hebel

- **Modell-Staffelung:** repetitive, eng begrenzte Nodes (extrahieren, klassifizieren) auf ein
  günstigeres Modell routen (in Claude Code: `model`-Parameter am Subagenten-Aufruf);
  Synthese/Adjudikation auf dem Session-Modell lassen. Vor großen Läufen `/model` prüfen.
- **Durchlaufen statt aufstauen:** Barriere („erst wenn ALLE fertig sind") nur, wenn eine Stufe wirklich
  alle Vorergebnisse zusammen braucht (Cross-Set-Dedupe, Early-Exit, Vergleich „gegen die anderen").
- **Zyklen nur konvergent** (Discovery unbekannter Größe): loop-until-dry mit K leeren Runden als
  Stopp; dedupe gegen ALLES Gesehene, nicht nur gegen Bestätigtes.
- **Gute Läufe speichern:** bewährte Orchestrierungs-Skripte nach `.claude/workflows/<name>`
  (versioniert, per Name wiederholbar). In der OKF unter `runbooks/` verlinken.

## Regeln (Template-Konform)

- Unklare Fälle im Fan-out werden GESAMMELT und am Ende in EINEM Block nachgefragt — nicht raten,
  aber auch nicht den Lauf mittendrin blockieren.
- Jede Zahl/Aussage im Endergebnis trägt Herkunft (Datei/Quelle/Query) — wie überall im Projekt.
- Kein Graph ohne Abschluss: Fan-in mündet in `okr-okf-sync` (Tracker + OKF + Datum).
