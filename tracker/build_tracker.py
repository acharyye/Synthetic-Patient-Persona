#!/usr/bin/env python3
"""
build_tracker.py — regeneriert die eingebetteten Daten in tracker.html.

Die Tracker-App ist eine einzelne, self-contained HTML-Datei ohne Build und ohne
Server. Damit sie trotzdem den aktuellen Stand zeigt, werden drei JSON-Bloecke
IN die HTML eingebettet und von diesem Skript neu geschrieben:

  #tracker-state-data   <- tracker/tracker_state.json   (Seed fuer OKRs/Stages/Tasks)
  #okf-graph-data       <- 01_Documentation/okf/**.md    (Knoten + Kanten des Wissens-Graphen)
  #okf-docs-data        <- 01_Documentation/okf/**.md    (Markdown fuer den Dokumente-Browser)

Aufruf (aus dem Projekt heraus, Pfad egal):

    python3 tracker/build_tracker.py

Immer laufen lassen, wenn sich `tracker_state.json` oder etwas in `okf/` geaendert
hat — sonst zeigt die App einen veralteten Stand. Das Skript ist idempotent und
aendert ausschliesslich die drei Datenbloecke, nie die Render-Logik.

Keine Abhaengigkeiten (nur Python-Standardbibliothek).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# tracker/build_tracker.py -> Projektwurzel ist der Elternordner von tracker/
ROOT = Path(__file__).resolve().parent.parent

# Die Wissensbasis liegt je nach Projekt-Layout an einer von mehreren Stellen:
# frische Template-Kopien nutzen `01_Documentation/okf`, bestehende Repos mit
# eigenem `docs/` nutzen `docs/okf`. Erster Treffer gewinnt; existiert keiner,
# bleibt der Template-Standard fuer die Fehlermeldung stehen.
OKF_CANDIDATES = (
    ROOT / "01_Documentation" / "okf",
    ROOT / "docs" / "okf",
    ROOT / "okf",
)
OKF_DIR = next((p for p in OKF_CANDIDATES if p.is_dir()), OKF_CANDIDATES[0])
TRACKER_HTML = ROOT / "tracker" / "tracker.html"
STATE_JSON = ROOT / "tracker" / "tracker_state.json"

# Markdown-Link auf eine .md-Datei: [Titel](pfad.md) — Anker/Query werden abgeschnitten.
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+\.md)(?:#[^)\s]*)?\s*\)")
# Frontmatter-Feld auf oberster Ebene: `key: value`
FM_FIELD = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
# Code-Fences (``` … ```) und Inline-Code (`…`)
CODE_FENCE = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    """Entfernt Code-Bloecke und Inline-Code.

    Links darin sind Beispiele (z. B. `[Trip-Match](../concepts/trip-match-rate.md)`
    in SCHEMA.md), keine echten Verweise — sie duerfen weder Kanten erzeugen noch
    als tote Links gemeldet werden.
    """
    return INLINE_CODE.sub("", CODE_FENCE.sub("", text))


def parse_frontmatter(text: str) -> dict[str, str]:
    """Liest den YAML-Frontmatter-Block flach aus (nur `key: value`, keine Listen).

    Bewusst minimal statt PyYAML — die Wissensbasis nutzt laut SCHEMA.md nur
    flache Felder, und das Template soll abhaengigkeitsfrei bleiben.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        m = FM_FIELD.match(line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip("\"'")
    return fields


def collect_docs() -> list[dict]:
    """Alle OKF-Markdown-Dateien als sortierte Dokument-Records."""
    docs = []
    for path in sorted(OKF_DIR.rglob("*.md")):
        rel = path.relative_to(OKF_DIR).as_posix()
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        parent = path.parent.relative_to(OKF_DIR).as_posix()
        docs.append({
            "id": rel,
            "folder": "root" if parent == "." else parent,
            "title": fm.get("title") or path.stem,
            "type": fm.get("type") or "Concept",
            "md": text,
        })
    return docs


def build_graph(docs: list[dict]) -> tuple[dict, list[tuple[str, str]]]:
    """Baut Knoten + gerichtete Kanten; meldet tote Links separat zurueck."""
    index = {d["id"]: i for i, d in enumerate(docs)}
    edges: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    dead: list[tuple[str, str]] = []

    for doc in docs:
        src_dir = (OKF_DIR / doc["id"]).parent
        for m in MD_LINK.finditer(strip_code(doc["md"])):
            target = m.group(1)
            # Platzhalter aus den Vorlagen (`<ordner>/<datei>.md`) ignorieren
            if "<" in target or target.startswith(("http://", "https://")):
                continue
            resolved = (src_dir / target).resolve()
            try:
                rel = resolved.relative_to(OKF_DIR.resolve()).as_posix()
            except ValueError:
                # Link zeigt aus der Wissensbasis heraus — kein Graph-Knoten,
                # aber pruefen, ob das Ziel ueberhaupt existiert.
                if not resolved.exists():
                    dead.append((doc["id"], target))
                continue
            if rel not in index:
                dead.append((doc["id"], target))
                continue
            pair = (index[doc["id"]], index[rel])
            if pair[0] != pair[1] and pair not in seen:
                seen.add(pair)
                edges.append([pair[0], pair[1]])

    nodes = [{"id": d["id"], "title": d["title"], "type": d["type"], "folder": d["folder"]} for d in docs]
    graph = {"meta": {"nodes": len(nodes), "edges": len(edges)}, "nodes": nodes, "edges": edges}
    return graph, dead


def embed(payload) -> str:
    """JSON fuer die Einbettung in ein <script>-Tag serialisieren.

    `<` wird escaped, damit weder `</script>` noch `<!--` den Parser vorzeitig
    beenden koennen — sonst zerlegt ein Markdown-Body mit HTML die Seite.
    """
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


def replace_block(html: str, block_id: str, payload) -> str:
    """Ersetzt den Inhalt von <script type="application/json" id="..."> in place."""
    pattern = re.compile(
        r'(<script type="application/json" id="%s">).*?(</script>)' % re.escape(block_id),
        re.S,
    )
    if not pattern.search(html):
        raise SystemExit(f"FEHLER: Block #{block_id} nicht in tracker.html gefunden.")
    return pattern.sub(lambda m: m.group(1) + embed(payload) + m.group(2), html, count=1)


def main() -> int:
    if not OKF_DIR.is_dir():
        raise SystemExit(f"FEHLER: OKF-Ordner nicht gefunden: {OKF_DIR}")
    if not TRACKER_HTML.is_file():
        raise SystemExit(f"FEHLER: tracker.html nicht gefunden: {TRACKER_HTML}")

    docs = collect_docs()
    graph, dead = build_graph(docs)

    try:
        state = json.loads(STATE_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"FEHLER: {STATE_JSON} fehlt.")
    except json.JSONDecodeError as e:
        raise SystemExit(f"FEHLER: {STATE_JSON} ist kein gueltiges JSON — {e}")

    html = TRACKER_HTML.read_text(encoding="utf-8")
    html = replace_block(html, "tracker-state-data", state)
    html = replace_block(html, "okf-graph-data", graph)
    html = replace_block(html, "okf-docs-data", docs)
    TRACKER_HTML.write_text(html, encoding="utf-8")

    print(f"OK  tracker.html aktualisiert")
    print(f"    State    : {len(state.get('stages', []))} Stages, "
          f"{sum(len(s.get('tasks', [])) for s in state.get('stages', []))} Tasks, "
          f"{len(state.get('okrs', []))} Objectives, lastModified={state.get('lastModified')}")
    print(f"    OKF      : {graph['meta']['nodes']} Konzepte, {graph['meta']['edges']} Verweise")

    if dead:
        print(f"\nWARNUNG: {len(dead)} toter Link in der Wissensbasis (SCHEMA.md Regel 4):")
        for src, target in dead:
            print(f"    {src} -> {target}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
