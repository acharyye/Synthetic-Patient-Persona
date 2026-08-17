---
name: analysis
description: Kritische, quellenbelegte Analyse eines Themas, Dokuments oder Datensatzes. Intern zuerst (OKF + eigene Daten), dann extern (Web) für Lücken, mit gegenprüfen (adversarial), dann Befund + offene Punkte + nächste Schritte. Auslöser: "analysiere", "kritische Analyse", "prüfe/verstehe X", "was sagt uns Y", "Root-Cause", oder ein Dokument/Datensatz, der eingeordnet werden soll.
---

# analysis — Kritische Analyse (intern zuerst, dann extern, dann gegenprüfen)

Erzeugt belastbare Erkenntnisse statt schneller Vermutungen. Jede Aussage kennzeichnen:
**[intern]** (unsere Daten/OKF) · **[extern]** (belegte Quelle) · **[Standard/Norm]** · **[Hypothese]**.

## Ablauf

1. **Frage schärfen:** Was genau ist zu klären? In 3–6 Teilfragen zerlegen.
2. **Intern zuerst:** `01_Documentation/okf/` + vorhandene Daten/Analysen (`02_Analysis`, `05_Data`) prüfen.
   Was wissen wir schon belastbar? Adressen/Begriffe/Metriken auflösen.
3. **Extern nur für Lücken:** was intern fehlt, gezielt recherchieren (WebSearch/WebFetch) — belastbare
   Quellen (Normen/Hersteller/Fachliteratur), **mit Zitat/Link**. Widersprüche auflösen, nicht mitteln.
4. **Gegenprüfen (adversarial):** zentrale Behauptungen aktiv zu widerlegen versuchen; nur was standhält,
   als bestätigt führen. Rechenwerte (Codes, Umrechnungen) verifizieren, nicht aus dem Kopf behaupten.
5. **Synthese:** Befund priorisiert; **klar getrennt**: gesichert vs. Hypothese vs. offen. Was intern belegt,
   was extern, was noch zu bestätigen ist.
6. **Ergebnis ablegen:** Analyse-MD in `02_Analysis/` (oder `04_Deliverables/` bei Übergabe), mit Quellenliste.
   Neue Erkenntnisse in `01_Documentation/okf/` nachtragen; Tracker/OKR aktualisieren (Skill `okr-okf-sync`).
7. **Nächste Schritte:** was würde die Hypothesen bestätigen/entkräften; welche Daten/Reads fehlen.

## Prinzipien
- **Erst klein validieren, dann skalieren** (bei neuen Datenquellen an 1–2 Fällen prüfen, nicht auf
  "SUCCESS"-Status allein verlassen).
- **Keine erfundenen Zahlen** — jede Kennzahl aus Quelle/Live, Herkunft nennen.
- **Ehrlich über Unsicherheit:** Hypothesen als solche kennzeichnen; nicht extern Belegbares markieren.
