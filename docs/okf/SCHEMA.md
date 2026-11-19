---
type: Meta
title: OKF-Schema & Konventionen
description: Regeln für Frontmatter, Dateien und Verlinkung in dieser Wissensbasis.
timestamp: 2026-08-17T00:00:00Z
---

# OKF-Schema & Konventionen

**Open Knowledge Format (OKF)** = eine Wissensbasis aus vielen kleinen Markdown-Dateien, jede mit
**YAML-Frontmatter** und einem **Konzept**. Maschinen- *und* menschenlesbar.

## Grundregeln

1. **Eine Datei = ein Konzept.** Lieber viele kleine, klar benannte Dateien als wenige große.
2. **Dateiname** = kebab-case, sprechend: `trip-match-rate.md`, `databricks-zugang.md`.
3. **Frontmatter ist Pflicht** (siehe unten). Mindestens `type`.
4. **Querverweise relativ** als Markdown-Links: `[Trip-Match](../concepts/trip-match-rate.md)`. **Keine toten Links.**
5. **Jede Ordner-`index.md`** listet die Konzepte ihres Ordners (Tabelle Datei → Kurzbeschreibung).
6. **Nur Fakten** aus Quelle/Live — nichts erfinden. Bei Änderung `timestamp` aktualisieren.

## Frontmatter-Felder

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `type` | **ja** | Art des Konzepts: `Concept`, `Glossary`, `Runbook`, `Architecture`, `Decision`, `Reference`, `Index`, `Meta` |
| `title` | empfohlen | Lesbarer Titel |
| `description` | empfohlen | Ein Satz — wird zur Relevanz-Einschätzung genutzt |
| `tags` | optional | Liste für Suche/Gruppierung |
| `resource` | optional | URL/Pfad zur Quelle (System, Repo, Dashboard) |
| `timestamp` | empfohlen | Letzte Aktualisierung `YYYY-MM-DDT00:00:00Z` |

## Body-Konventionen

- Beginne mit `# <Titel>` und einem 1–2-Satz-Abriss.
- Strukturiere mit `##`-Abschnitten; nutze Tabellen für Felder/Werte.
- Am Ende ein **„Verwandt:"**-Block mit relativen Links zu zusammenhängenden Konzepten.
- Halte fest **warum** etwas so ist, nicht nur was — gerade in `decisions/`.

## Neues Konzept anlegen

1. `_TEMPLATE_concept.md` kopieren in den passenden Ordner, sinnvoll benennen.
2. Frontmatter + Body ausfüllen.
3. In der Ordner-`index.md` verlinken.
4. Relevante Querverweise aus/zu anderen Konzepten setzen.
