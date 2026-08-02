"""Validate LLM-generated Cypher before it touches the database.

An LLM writing queries against your graph is an injection surface, so this is
deny-by-default: a query must be a single read-only statement, over labels and
relationship types that exist in our schema, bounded by a LIMIT, with no
procedure calls and no parameters we did not bind ourselves.

Anything that fails is rejected outright and the retriever falls back to its
deterministic traversal. We never "repair" a suspicious query — a query we had
to fix is a query we did not understand.

Note on scope: this guards *our* pipeline, where the generated query is the only
untrusted input and the driver runs with full credentials. It is not a substitute
for a read-only database role, which you should also use in any real deployment.
"""
from __future__ import annotations

import re

from ..graph.schema import ALLOWED_LABELS, ALLOWED_REL_TYPES

MAX_QUERY_CHARS = 2000
MAX_LIMIT = 50

# Parameters the retriever binds. A query naming anything else is trying to read
# something we did not offer it.
ALLOWED_PARAMS = frozenset({"condition"})

# Write, DDL, admin and IO clauses. Matched as whole words on the query with
# string literals and comments already stripped.
_FORBIDDEN = (
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "FOREACH",
    "CALL", "LOAD", "USING", "ALTER", "GRANT", "DENY", "REVOKE", "START",
    "SHOW", "TERMINATE", "UNION", "COMMIT",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN) + r")\b", re.IGNORECASE)

# Labels and relationship types: an identifier introduced by ':', including
# alternations like [:TREATS|PALLIATES].
_TYPE_RE = re.compile(r":\s*([A-Za-z_]\w*(?:\s*\|\s*[A-Za-z_]\w*)*)")
_PARAM_RE = re.compile(r"\$([A-Za-z_]\w*)")
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\s*$", re.IGNORECASE)
# Variable-length patterns with no upper bound: [*], [*2..], [:REL*]
_UNBOUNDED_RE = re.compile(r"\*\s*(?:\d+\s*\.\.\s*)?\]")


class UnsafeCypher(ValueError):
    """The generated query was rejected. Carries why, for logging."""


def _strip_literals_and_comments(cypher: str) -> str:
    """Blank out string literals and comments so keyword scanning can't be
    fooled by a `// CREATE` comment or a "DELETE" inside a string, and so a
    literal containing ':' isn't mistaken for a label.
    """
    out: list[str] = []
    i, n = 0, len(cypher)
    while i < n:
        ch = cypher[i]
        if ch in "'\"":
            quote = ch
            i += 1
            while i < n and cypher[i] != quote:
                i += 2 if cypher[i] == "\\" else 1
            i += 1
            out.append('""')
        elif cypher.startswith("//", i):
            while i < n and cypher[i] != "\n":
                i += 1
        elif cypher.startswith("/*", i):
            end = cypher.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def validate_cypher(cypher: str, max_limit: int = MAX_LIMIT) -> str:
    """Return the query to execute, or raise UnsafeCypher.

    The only rewrite performed is appending a LIMIT when one is absent; a query
    that states its own oversized LIMIT is rejected rather than quietly capped.
    """
    if not cypher or not cypher.strip():
        raise UnsafeCypher("empty query")

    query = cypher.strip().rstrip(";").strip()

    if len(query) > MAX_QUERY_CHARS:
        raise UnsafeCypher(f"query too long ({len(query)} > {MAX_QUERY_CHARS} chars)")

    if "`" in query:
        raise UnsafeCypher("backtick-quoted identifiers are not allowed")

    if ";" in query:
        raise UnsafeCypher("multiple statements are not allowed")

    scannable = _strip_literals_and_comments(query)

    if forbidden := _FORBIDDEN_RE.search(scannable):
        raise UnsafeCypher(f"forbidden clause {forbidden.group(1).upper()!r}")

    upper = scannable.lstrip().upper()
    if not (upper.startswith("MATCH") or upper.startswith("OPTIONAL MATCH")):
        raise UnsafeCypher("query must start with MATCH")

    if "RETURN" not in scannable.upper():
        raise UnsafeCypher("query must RETURN something")

    if _UNBOUNDED_RE.search(scannable):
        raise UnsafeCypher("variable-length patterns must have an upper bound")

    for match in _TYPE_RE.finditer(scannable):
        for token in match.group(1).split("|"):
            name = token.strip()
            if name not in ALLOWED_LABELS and name not in ALLOWED_REL_TYPES:
                raise UnsafeCypher(f"unknown label or relationship type {name!r}")

    for match in _PARAM_RE.finditer(scannable):
        if match.group(1) not in ALLOWED_PARAMS:
            raise UnsafeCypher(f"unbound parameter ${match.group(1)}")

    if limit := _LIMIT_RE.search(scannable):
        if int(limit.group(1)) > max_limit:
            raise UnsafeCypher(f"LIMIT {limit.group(1)} exceeds maximum {max_limit}")
        return query

    return f"{query} LIMIT {max_limit}"
