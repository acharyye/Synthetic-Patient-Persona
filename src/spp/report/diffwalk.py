"""Structural leaf-walking and artifact diffing.

Extracted from the throwaway used to verify the persona-id migration showed
*only* ids. It already knew how to walk an arbitrary artifact and report which
leaves moved, so the Cohort Studio's diff view reuses it rather than growing a
second comparison implementation — two comparators would eventually disagree
about what "changed" means.

Generic on purpose: it takes JSON-shaped data and returns paths, so it works for
cohorts, run artifacts and golden files alike.
"""
from __future__ import annotations

from typing import Any, Iterator

from pydantic import BaseModel, Field


def walk_leaves(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Yield (dotted-path, value) for every scalar leaf."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk_leaves(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk_leaves(value, f"{path}[{index}]")
    else:
        yield path, node


class LeafChange(BaseModel):
    path: str
    before: Any = None
    after: Any = None
    kind: str = Field(description="changed | added | removed")

    @property
    def numeric_delta(self) -> float | None:
        if isinstance(self.before, (int, float)) and isinstance(self.after, (int, float)):
            if not isinstance(self.before, bool) and not isinstance(self.after, bool):
                return round(float(self.after) - float(self.before), 6)
        return None


class ArtifactDiff(BaseModel):
    changes: list[LeafChange] = Field(default_factory=list)
    unchanged: int = 0

    @property
    def changed(self) -> int:
        return len(self.changes)

    def paths(self) -> list[str]:
        return [change.path for change in self.changes]

    def only_touches(self, *prefixes: str) -> bool:
        """True when every change sits under one of `prefixes`.

        The question the id migration needed answered: did *only* the thing I
        meant to change actually change?
        """
        return all(
            any(prefix in change.path for prefix in prefixes)
            for change in self.changes
        )


def diff_artifacts(before: Any, after: Any) -> ArtifactDiff:
    """Leaf-level diff of two JSON-shaped artifacts."""
    left = dict(walk_leaves(before))
    right = dict(walk_leaves(after))

    changes: list[LeafChange] = []
    unchanged = 0

    for path in sorted(set(left) | set(right)):
        if path not in right:
            changes.append(LeafChange(path=path, before=left[path], kind="removed"))
        elif path not in left:
            changes.append(LeafChange(path=path, after=right[path], kind="added"))
        elif left[path] != right[path]:
            changes.append(LeafChange(
                path=path, before=left[path], after=right[path], kind="changed"))
        else:
            unchanged += 1

    return ArtifactDiff(changes=changes, unchanged=unchanged)
