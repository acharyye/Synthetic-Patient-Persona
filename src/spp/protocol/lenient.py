"""Lenient parsing for the live rule editor.

`parse_criterion` is strict on purpose: a malformed criterion in a *protocol* must
fail loudly, because a typo that silently screens out a cohort is the worst
possible failure for this tool. But a half-typed criterion in an *editor* is not
a malformed protocol — it is a person mid-keystroke, and treating it as an error
makes the preview blank on every character.

So this is a second front-end over the same parser, never a second parser:

  * every criterion is classified valid / invalid, with the error's location
  * the valid subset is returned as a usable AST, so the preview keeps working
  * the caller is told the result is `stale` and why

The editor draws a squiggle; the preview keeps showing the last valid numbers
with a "rule has errors" marker rather than going blank. Strictness is unchanged
where it matters — `screen()` still refuses to evaluate anything it cannot parse.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .eligibility import Criterion, CriterionError, parse_criterion


class CriterionDiagnostic(BaseModel):
    """One criterion's parse status, addressed for an editor gutter."""

    index: int
    text: str
    kind: str = Field(description="inclusion | exclusion")
    ok: bool
    message: str = ""
    # Character offset within `text` where the problem starts, best effort.
    column: int | None = None

    @property
    def is_blank(self) -> bool:
        return not self.text.strip()


class LenientParse(BaseModel):
    """Parse result usable while the text is still being typed."""

    diagnostics: list[CriterionDiagnostic] = Field(default_factory=list)
    valid_inclusion: list[str] = Field(default_factory=list)
    valid_exclusion: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(d.ok for d in self.diagnostics)

    @property
    def errors(self) -> list[CriterionDiagnostic]:
        return [d for d in self.diagnostics if not d.ok]

    @property
    def has_usable_subset(self) -> bool:
        return bool(self.valid_inclusion or self.valid_exclusion)

    def stale_reason(self) -> str:
        """What the preview badge should say. Empty when everything parses."""
        if self.ok:
            return ""
        count = len(self.errors)
        usable = len(self.valid_inclusion) + len(self.valid_exclusion)
        subject = "1 rule has" if count == 1 else f"{count} rules have"
        return (
            f"{subject} errors — showing results for the {usable} that parse. "
            f"First problem: {self.errors[0].message}"
        )


def _locate(text: str, message: str) -> int | None:
    """Best-effort column for the squiggle.

    Deliberately crude: the parser is regex-based and has no token positions, so
    this points at the operator or the end of the text rather than pretending to
    a precision it does not have.
    """
    for operator in ("<=", ">=", "!=", "==", " in ", "<", ">", "="):
        position = text.find(operator)
        if position >= 0:
            return position
    return len(text.rstrip()) if text.strip() else 0


def parse_lenient(
    inclusion: list[str] | None = None,
    exclusion: list[str] | None = None,
) -> LenientParse:
    """Classify every criterion, returning the valid subset as usable rules.

    Blank lines are skipped silently — an empty row in an editor is not an error.
    """
    result = LenientParse()
    index = 0

    for kind, criteria in (("inclusion", inclusion or []), ("exclusion", exclusion or [])):
        for text in criteria:
            if not text.strip():
                index += 1
                continue
            try:
                parse_criterion(text)
            except CriterionError as exc:
                result.diagnostics.append(CriterionDiagnostic(
                    index=index, text=text, kind=kind, ok=False,
                    message=str(exc), column=_locate(text, str(exc)),
                ))
            else:
                result.diagnostics.append(CriterionDiagnostic(
                    index=index, text=text, kind=kind, ok=True,
                ))
                target = (
                    result.valid_inclusion if kind == "inclusion"
                    else result.valid_exclusion
                )
                target.append(text)
            index += 1

    return result


def parse_partial(texts: list[str]) -> tuple[list[Criterion], list[CriterionDiagnostic]]:
    """Lower-level helper: the parsed subset plus diagnostics for the rest."""
    parsed: list[Criterion] = []
    problems: list[CriterionDiagnostic] = []
    for index, text in enumerate(texts):
        if not text.strip():
            continue
        try:
            parsed.append(parse_criterion(text))
        except CriterionError as exc:
            problems.append(CriterionDiagnostic(
                index=index, text=text, kind="inclusion", ok=False,
                message=str(exc), column=_locate(text, str(exc)),
            ))
    return parsed, problems
