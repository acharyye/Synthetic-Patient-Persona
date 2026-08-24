# Narration evidence bundle — v0.4

Recorded 2026-08-23T17:01:52+00:00 against **qwen2.5:7b-instruct@845dbda0ea48ed749ca**, prompt v3.

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
5. `adjudication.json` — **last**. The arms registered before the run,
   read against what happened. Meeting the verdict first would colour the
   reading of everything above it.

## Caveat

Compliance measured against a fixed battery under a pre-registered set of pass bars. This is evidence about one (prompt, model, sampling) configuration, not a validation of the model in general.
