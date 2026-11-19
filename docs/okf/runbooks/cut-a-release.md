---
type: Runbook
title: Cut a release
description: Bump the one version, rewrite RELEASE.md, tag — and freeze the notes with the tag rather than growing them afterwards.
resource: ../../../RELEASE.md
tags: [runbook, release, versioning, evidence]
timestamp: 2026-08-24T00:00:00Z
---

# Cut a release

Observed procedure, as v0.1, v0.2 and v0.3 were actually cut. A release is **one commit** that bumps
the version and rewrites the notes, followed by a tag.

## The version has exactly one source

`pyproject.toml` `[project] version`. `spp.__version__` *resolves* it — installed metadata first,
then pyproject, then the honest `"unknown"` — so there is nothing else to edit. This was not always
true: the version was hardcoded in `__init__.py` **and** `api/main.py`, so pyproject said 0.3.0 while
`GET /openapi.json` reported 0.1.0. A stamp that lies, in a project whose argument is honest stamps.
Do not reintroduce a second copy.

## Before tagging

| Check | Command |
|---|---|
| Full suite, all three surfaces | `pytest` · `cd ui && npm test` · `npx playwright test` |
| Interpreter matrix | `.github/workflows/tests.yml` — 3.11 / 3.12 / 3.13 on every push |
| Lock rendering not stale | `uv lock && scripts/sync_deps.sh` — CI fails if `requirements.txt` drifts |
| Tracker current | grades honest, `lastModified` today, then `python3 tracker/build_tracker.py` |
| OKF current | affected concepts updated in the same work step, no dead links |

Adding a dependency is always: edit `[project.dependencies]` → `uv lock` → `scripts/sync_deps.sh`.
`requirements.txt` is a **rendering** of the lock, never edited by hand.

## The notes

`RELEASE.md` is **rewritten**, not appended — it holds the current release only; older notes live
frozen on their tags. It carries, in this order: what the release is and why it is a release rather
than a patch set, what the construction is, what is pinned, and a **"Still open"** section that names
the things that did not get fixed.

That last section is load-bearing. v0.3 shipped saying prompt v2 had not been re-recorded, that
`synthea_loader` was still the open build-order item, and that `cumulative_burden_weight` ships frozen
at zero and unidentifiable. A release note that only lists wins is a marketing document.

## Tag, and leave it alone

```bash
git tag -a v0.4 -m "v0.4 — <the one-line arc>"
```

**Notes that grow after the fact are a small dishonesty** in a project whose product is provenance.
If the story changed, that is a new release, not an amended tag — which is exactly why v0.3 was cut on
its own terms instead of being folded into v0.2.

## Evidence bundles are the release's baseline

A release that changed the model, the prompt version or the sampling needs a
[recorded battery](record-a-battery.md) and its [adjudication](adjudicate-a-bundle.md) archived under
`evidence/<release>/`. The bundle is what the *next* model or prompt bump gets diffed against, so it
is committed even when it records a miss — v0.4's bundle is committed reading `OVER-CORRECTION`, with
a `NOTE.md` stating what it cannot reproduce about itself.

---
Related: [Record a battery](record-a-battery.md), [Adjudicate a bundle](adjudicate-a-bundle.md), [Environment tiers](../decisions/environment-tiers.md)
