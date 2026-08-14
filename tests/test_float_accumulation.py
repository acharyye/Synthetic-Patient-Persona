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
import importlib
import pkgutil
import re
import sys
from pathlib import Path
from typing import get_args, get_origin

import pytest
from pydantic import BaseModel

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


def _model_registry() -> dict[str, type[BaseModel]]:
    """Every pydantic model reachable under `spp`, by class name."""
    package = importlib.import_module("spp")
    for info in pkgutil.walk_packages(package.__path__, prefix="spp."):
        try:
            importlib.import_module(info.name)
        except Exception:  # optional backends need not import to be introspected
            continue

    registry: dict[str, type[BaseModel]] = {}
    for module in list(sys.modules.values()):
        if not getattr(module, "__name__", "").startswith("spp"):
            continue
        for name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                registry.setdefault(obj.__name__, obj)
    return registry


def _annotation_is_integer(annotation: object) -> bool:
    """int, or a container of ints — dict[str, int], list[int]."""
    if annotation is int:
        return True
    args = get_args(annotation)
    if get_origin(annotation) in (dict, list, tuple) and args:
        return _annotation_is_integer(args[-1])
    return False


def _markers() -> list[tuple[Path, int, str]]:
    out = []
    for path in _source_files():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if MARKER in line:
                out.append((path, number, line.split(MARKER, 1)[1].strip()))
    return out


def test_int_sum_markers_resolve_to_int_typed_schema_fields() -> None:
    """A marker must name the declaration it depends on, and be checked against it.

    The guard above proves the operand types were *stated*. It cannot prove the
    statement is true — so a field migrating from int to float would turn a
    marker into a lie the guard believes. Full type inference is a real project;
    schema introspection is not. Naming `Model.field` and resolving it through
    pydantic means the annotation changing is exactly when this breaks.

    Same move as reading tolerances from the pack rather than transcribing them:
    check the assertion against the declaration it is about.

    Markers that genuinely cannot name a schema field stay trusted-by-review —
    that is the honest boundary — but they are enumerated here rather than
    remembered, and the split is printed so the guard's reach is visible.
    """
    registry = _model_registry()
    verified: list[str] = []
    by_review: list[str] = []
    broken: list[str] = []

    for path, number, target in _markers():
        where = f"{path.name}:{number}"
        if not re.fullmatch(r"[A-Z]\w*\.\w+", target):
            by_review.append(f"{where}: {target}")
            continue

        class_name, field_name = target.split(".")
        model = registry.get(class_name)
        if model is None:
            broken.append(f"{where}: no pydantic model named {class_name!r}")
            continue
        field = model.model_fields.get(field_name)
        if field is None:
            broken.append(f"{where}: {class_name} has no field {field_name!r}")
            continue
        if not _annotation_is_integer(field.annotation):
            broken.append(
                f"{where}: {target} is annotated {field.annotation!r}, not int — "
                "this sum is now float accumulation and must use math.fsum"
            )
            continue
        verified.append(f"{where}: {target}")

    print(
        f"\nint-sum markers: {len(verified)} verified against schema, "
        f"{len(by_review)} trusted-by-review"
    )
    for entry in by_review:
        print(f"  trusted-by-review  {entry}")

    assert not broken, "markers that no longer match their declaration:\n  " + "\n  ".join(broken)
    # The boundary is allowed to exist, not to grow silently.
    assert len(by_review) <= 2, (
        f"{len(by_review)} unverifiable markers; every new one widens what this "
        "guard cannot prove:\n  " + "\n  ".join(by_review)
    )


def test_marker_verification_can_actually_fail() -> None:
    """The resolver must reject a float field, not merely accept int ones."""
    assert _annotation_is_integer(int)
    assert _annotation_is_integer(dict[str, int])
    assert _annotation_is_integer(list[int])
    assert not _annotation_is_integer(float)
    assert not _annotation_is_integer(dict[str, float])

    registry = _model_registry()
    assert "CaseResult" in registry, "registry must actually find models"


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
