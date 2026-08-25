# Narration evidence bundle — v0.5 (prompt v4, the segmentation lever)

## THE VERDICT IS A CONJUNCTION. Both clauses, never one.

**The lever worked and the floor was missed.**

A reader who takes away "v4 failed" has been misinformed exactly as badly as one
who takes away "v4 passed."

**The lever worked.** The displacement barrier broke. State and graph citation
coexisted on the same run —  0.4419 → 0.50 **while**
 0.4615 → 0.5897. That conjunction is what nineteen sessions
were chasing: either number alone is buyable by sacrificing the other, which is
precisely why it was pre-registered as a conjunction, and it landed as one.
Compounds fell ( 0.567 → 0.30, 
1.8 → 2.23, two real compounds in 34 blind-read segments), so the falsification
condition was not met. Nothing structural was spent: validity 1.0, parse 0.0,
retry 0.0, quarantine 0.

**The floor was missed.** Gold-semantics coverage on the audited slice reads
**0.556 against a floor of 0.6** — 10 apt-citing of 18 coverable, from blind
labels. The slice is symptom-heavy and burden-absent, and that caveat **sized**
the miss; it does not excuse it. The headline stays a miss.

**What stands between 0.556 and the floor is F3, not expressiveness.** Identical
claim shapes are intermittently grounded: *"I take metformin, empagliflozin and
semaglutide"* cites nothing while the four-drug segment cites all four; one
methotrexate segment cites, another does not. The uncited-coverable population is
not a claim type the schema cannot express — it is the same claim type,
sometimes grounded and sometimes not.

---

# Narration evidence bundle — v0.5

Recorded 2026-08-25T12:30:23+00:00 against **qwen2.5:7b-instruct@845dbda0ea48ed749ca**, prompt v4.

| | |
|---|---|
| battery cases | 30 |
| accepted takes | 30 |
| quarantined | 0 |
| compliance rate | 1.0 |
| canary sensitive | True |
| pass bars met | True |
| ledger schema | v1 |
| environment | python=3.13.0 numpy=2.5.2 lock=24f055e496ea3a5b |

## Read in this order

1. `canary.json` — **first**. If the instrument could not detect a degraded
   configuration, nothing else here is evidence.
2. `takes/` — 5 raw takes, chosen by seed rather than picked. No
   aggregate catches degeneracy; only reading does.
3. `quarantine.json` — every rejected response, with its reason.
4. `compliance.json` — aggregates and the pre-registered pass-bar verdicts.

## Caveat

Compliance measured against a fixed battery under a pre-registered set of pass bars. This is evidence about one (prompt, model, sampling) configuration, not a validation of the model in general.
