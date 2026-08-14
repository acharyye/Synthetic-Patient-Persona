# Narration evidence bundle — v0.3

Recorded 2026-08-14T20:04:47+00:00 against **qwen2.5:7b-instruct@845dbda0ea48ed749ca**, prompt v2.

| | |
|---|---|
| battery cases | 30 |
| accepted takes | 30 |
| quarantined | 0 |
| compliance rate | 1.0 |
| canary sensitive | None |
| pass bars met | True |
| ledger schema | v1 |
| environment | python=3.13.0 numpy=2.5.2 lock=0c9031359dfa45f4 |

## Read in this order

1. `canary.json` — **first**. If the instrument could not detect a degraded
   configuration, nothing else here is evidence.
2. `takes/` — 5 raw takes, chosen by seed rather than picked. No
   aggregate catches degeneracy; only reading does.
3. `quarantine.json` — every rejected response, with its reason.
4. `compliance.json` — aggregates and the pre-registered pass-bar verdicts.

## Caveat on this bundle's 100% compliance

Quarantine 0 and compliance 1.000 are real, and they are **schema conformance**,
not full grounding. Part of what v1 quarantined did not disappear — it moved
inside the `feeling` label, where the citation gate cannot see it. The model is
behaving correctly against the schema: the bus segment genuinely has nothing
citable, because the schema cannot express personal circumstance.

So quote the compliance number with its companion. The expressiveness gap is
measured separately by `factual_fraction_by_tag`, which fell 0.933 → 0.443 on
mitigation for exactly that reason. The diagnostic with no bar did its job; do
not let eight green bars talk over it.

## Caveat

Compliance measured against a fixed battery under a pre-registered set of pass bars. This is evidence about one (prompt, model, sampling) configuration, not a validation of the model in general.

## Readings — pre-registered before this run

Comparability boundary: v0.1 and v0.3 share **weights, model digest, sampling
config, battery and pass bars**, and differ in exactly one declared variable —
the prompt. That is a paired design at the configuration level, and it is what
licenses every v1→v2 delta below. The same discipline as CRN pairing in the
simulation, applied to evidence bundles.

### 1. Double-citation at source — PASSED

**0 of 30** raw responses contain an inline `[F###]` marker, checked in the
cassette before the renderer touches anything. v1 had 7 of 25. The renderer's
stripping stays as defence in depth; it now has nothing to strip. The defect is
dead at its cause, not masked.

### 2. Model recall's second reading — MARGIN CLOSED

**0.525** against a 0.5 bar, on the full battery, up from v1's exactly-on-the-bar
0.500. Two independent readings above the bar with identical weights. The
boundary-pass asterisk comes off.

### 3. Friction hypothesis — SUPPORTED BUT CONFOUNDED

Quarantine **5/30 → 0/30**, retries **6.7% → 0%**. The double-contract's cost
looks real. But see finding 4: some of that drop is the model reclassifying
segments as `feeling`, which exempts them from the citation requirement. The
two causes are not separable from this run, so the honest claim is "consistent
with the friction hypothesis", not "measured".

### 4. Reading the takes — A NEW FINDING THE BARS DID NOT CATCH

All eight bars passed. `factual_fraction_by_tag`, a **diagnostic with no bar**,
moved sharply in the direction it was written to detect:

| question type | v1 | v2 |
|---|---|---|
| mitigation | 0.933 | **0.443** |
| burden | 0.667 | **0.400** |
| ae | 1.000 | 0.933 |
| proc | 1.000 | 0.900 |
| sym | 0.000 | 0.000 |
| tx | 1.000 | 1.000 |

`pass_bars.json` predicted this shape exactly: *"kind-dodging — asserting content
while labelling it `feeling` to skip citing — would show up here as an
anomalously low fraction on fact-seeking questions."*

Reading the takes complicates the simple story. The `feeling` segments mostly
**still carry fact_ids** (the `sym` take is one `feeling` segment citing five
facts), so this is not the model shirking citation work. The segments that carry
no ids are circumstantial: *"I rely on public transport, and sometimes buses
don't run when they're supposed to. Also, I have to take time off work, but that
costs money."* Those are claims about the persona's own simulated
circumstances — and there is no citable fact id for them. **That is the
state-citation gap, and it is the same class as v1's five quarantine entries.**

So: the quarantine class did not survive as quarantine, it survived as
reclassification. Removing the double contract fixed what it could; the residue
is structural and needs B012-class ids making simulated circumstances citable.

### 5. Position concentration — MOVED, WRONG WAY

Top-2 share **23.6% → 29.1%** (161 → 134 cited positions). It did not flatten.
Concentration is therefore a retrieval-ordering property rather than a prompt
artefact, which makes the seeded fact-order permutation in the prompt builder —
built, still off by default — the relevant knob, not further prompt wording.

### Canary notes

`truncate_context` scoring model-recall **0.90, above baseline's 0.52**, is not
an anomaly and not a broken canary. Truncation shrinks `expected ∩ retrieved`,
so the model-level denominator collapses and the ratio inflates. Detection of
that configuration rests on **system recall** (0.52 → 0.22) and the
position-concentration diagnostic, which is precisely why recall is split in
two. A reader who sees a degraded config outscore baseline and doubts the
instrument should read this paragraph first.

`unconstrained_ids` at **0.51 against baseline 0.52** is the quietly important
one: with the fact-id enum removed, the model still barely fabricates. The
constraint's value is therefore **guarantee, not correction** — it converts
"happens not to hallucinate citations" into "cannot". The control condition for
that claim is now measured rather than asserted.

### A structural note

Stale takes were never reachable: `prompt_version` is inside the prompt
fingerprint, so a prompt bump changes every key. Fingerprint keying, the
fact-id enum, and `require_compatible` are one idea applied three times — make
the invalid state unrepresentable rather than detected.
