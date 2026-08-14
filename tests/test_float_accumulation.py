"""Bare `sum()` over floats may not enter the simulation core.

CPython 3.12 switched `sum()` over floats to Neumaier compensated summation.
Same inputs, same order, different result: 110.88000000000005 on 3.11 against
110.88 on 3.12+. That surfaced once as a golden diff with no code change and
identical draws, which is the cheap version of the failure. The expensive
version is a state-feeding aggregate crossing a threshold and flipping a
persona, making a CRN-paired flip table disagree with itself across
environments.

The project's promise is that simulation state is a function of seeds and
declared assumptions. An accumulation algorithm the interpreter owns, and can
change in a minor release, is an undeclared assumption. So:

    float accumulation in core code uses math.fsum, or explicit fixed-arity
    addition (a + b + c)

Fixed arity is fine and is why `simulation/hazard.py` was already correct —
pairwise addition is deterministic across versions. It is variadic `sum()`
whose algorithm the interpreter owns.

This is a boundary test, the same species as `TestPureCore` (no LLM on the CI
path): it makes the rule mechanical rather than remembered. Integer counting is
exempt because integer addition is exact — `sum(1 for ...)` is recognised
automatically, and any other genuinely-integer accumulation carries an explicit
`# int-sum:` marker naming what is being counted. The marker is the point: it
forces the author to state that the operands are integers, in the diff, where a
reviewer sees it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1] / "src" / "spp"

MARKER = "# int-sum:"

RULE = (
    "float accumulation in core code must use math.fsum (or explicit a + b + c). "
    "If these operands are integers, append a `{marker} why` comment on the "
    "`sum(` line to say so."
).format(marker=MARKER)


def _source_files() -> list[Path]:
    return sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts)


def _is_integer_count(node: ast.Call) -> bool:
    """`sum(1 for ...)` and friends — an elt that is literally an int."""
    if not node.args:
        return False
    arg = node.args[0]
    if isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
        elt = arg.elt
        return isinstance(elt, ast.Constant) and isinstance(elt.value, int)
    return False


def _bare_sum_calls(tree: ast.AST) -> list[ast.Call]:
    out = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sum"
        ):
            out.append(node)
    return out


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: p.name)
def test_no_unmarked_bare_sum(path: Path) -> None:
    lines = path.read_text().splitlines()
    tree = ast.parse("\n".join(lines), filename=str(path))

    offenders = []
    for call in _bare_sum_calls(tree):
        if _is_integer_count(call):
            continue
        line = lines[call.lineno - 1]
        if MARKER in line:
            continue
        offenders.append(f"{path.relative_to(CORE.parents[1])}:{call.lineno}: {line.strip()}")

    assert not offenders, (
        f"{len(offenders)} bare sum() call(s) with unstated operand types.\n"
        + "\n".join(offenders)
        + f"\n\n{RULE}"
    )


def test_the_guard_can_actually_fail(tmp_path: Path) -> None:
    """An assertion that cannot fail is not an assertion.

    Same reasoning as the narration canary and TestGateCanActuallyFail: the
    guard above passes trivially if the AST walk is wrong, so prove it fires on
    a float sum and stays quiet on a counted one.
    """
    tree = ast.parse("total = sum(p.severity for p in items)\n")
    calls = _bare_sum_calls(tree)
    assert len(calls) == 1
    assert not _is_integer_count(calls[0])

    counted = ast.parse("n = sum(1 for p in items if p.ok)\n")
    assert _is_integer_count(_bare_sum_calls(counted)[0])

    assert not _bare_sum_calls(ast.parse("total = math.fsum(xs)\n"))
