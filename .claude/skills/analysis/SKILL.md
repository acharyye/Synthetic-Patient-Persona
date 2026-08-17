---
name: analysis
description: Kritische, quellenbelegte Analyse als Graph — Frage in Teilfragen splitten, intern (OKF/Daten) und für Lücken extern parallel recherchieren, jede zentrale Behauptung durch unabhängige Skeptiker-Nodes verifizieren, dann synthetisieren. Auslöser: "analysiere", "kritische Analyse", "prüfe/verstehe X", "Root-Cause", oder ein Dokument/Datensatz, der eingeordnet werden soll.
---

# analysis — Kritische Analyse als verifizierter Graph

**Topologie: Diamond mit Verifier-Schicht.** Kennzeichnung bleibt Pflicht:
**[intern]** · **[extern]** · **[Standard/Norm]** · **[Hypothese]**.
Regeln aus Skill `workflow` gelten (Schema-Verträge, Single-Writer, Verifier).

## Phase 1 — Split
Frage schärfen und in **3–6 Teilfragen** zerlegen (ein Agent). Jede Teilfrage = ein Node-Auftrag
mit begrenztem Scope. Bei < 3 Teilfragen oder trivialem Umfang: sequenziell arbeiten.

## Phase 2 — Fan-out intern zuerst
Pro Teilfrage ein Subagent, der NUR intern arbeitet: `01_Documentation/okf/` + `02_Analysis` +
`05_Data`. Rückgabe-Schema:

    { teilfrage, befunde: [{ aussage, herkunft, kategorie: "intern|hypothese" }],
      luecken: [string] }

## Phase 3 — Fan-out extern (nur Lücken)
Kanten-Code sammelt die `luecken` über alle Teilfragen, dedupliziert sie. Pro Lücke ein
Recherche-Subagent (WebSearch/WebFetch, belastbare Quellen: Normen/Hersteller/Fachliteratur),
Rückgabe mit Zitat/Link im selben Schema (`kategorie: "extern"`). Widersprüche werden markiert,
nicht gemittelt.

## Phase 4 — Verifier (das Herzstück)
Jede ZENTRALE Behauptung (Auswahl per Kanten-Code: alles, was die Synthese tragen soll) läuft
durch **3 unabhängige Skeptiker-Nodes** mit verschiedenen Linsen:
- **Quelle hält:** stützt die genannte Herkunft die Aussage wirklich?
- **Rechnung stimmt:** Zahlen/Umrechnungen/Codes aktiv nachrechnen, nicht aus dem Kopf.
- **Konsistenz:** widerspricht die Aussage internem Wissen (OKF) oder anderen Befunden?

Verdikt-Schema: `{ aussage, real: bool, begruendung }`. **Überlebt < 2/3 → Hypothese,**
nicht Befund. Verdikte werden protokolliert (→ Tracker-Task `validations`).

## Phase 5 — Synthese + Ablage (Single-Writer)
1. EIN Synthese-Agent (Session-Modell) schreibt den Befund: priorisiert, klar getrennt
   gesichert vs. Hypothese vs. offen; intern/extern ausgewiesen; Quellenliste.
2. Ablage: Analyse-MD in `02_Analysis/` (bzw. `04_Deliverables/` bei Übergabe).
3. Neue Erkenntnisse in OKF nachtragen, Tracker aktualisieren → Skill `okr-okf-sync`.
   Verifier-Verdikte als `validations`-Einträge am Task.
4. **Nächste Schritte:** was würde Hypothesen bestätigen/entkräften; welche Daten fehlen.

## Prinzipien (unverändert)
- Erst klein validieren, dann skalieren (neue Datenquellen an 1–2 Fällen prüfen).
- Keine erfundenen Zahlen — jede Kennzahl aus Quelle/Live, Herkunft nennen.
- Ehrlich über Unsicherheit; Hypothesen als solche kennzeichnen.
