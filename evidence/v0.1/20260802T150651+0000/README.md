# Narration evidence bundle — v0.1

Recorded 2026-08-02T15:06:51+00:00 against **qwen2.5:7b-instruct@845dbda0ea48ed749ca**, prompt v1.

| | |
|---|---|
| battery cases | 30 |
| accepted takes | 25 |
| quarantined | 5 |
| compliance rate | 0.8333 |
| canary sensitive | True |
| pass bars met | True |
| ledger schema | v1 |

## Read in this order

1. `canary.json` — **first**. If the instrument could not detect a degraded
   configuration, nothing else here is evidence.
2. `takes/` — 5 raw takes, chosen by seed rather than picked. No
   aggregate catches degeneracy; only reading does.
3. `quarantine.json` — every rejected response, with its reason.
4. `compliance.json` — aggregates and the pre-registered pass-bar verdicts.

## Caveat

Compliance measured against a fixed battery under a pre-registered set of pass bars. This is evidence about one (prompt, model, sampling) configuration, not a validation of the model in general.
