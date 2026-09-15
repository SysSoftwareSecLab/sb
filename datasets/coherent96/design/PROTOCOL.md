# RQ2 Coherent-Pair Prospective Confirmation v1

## Scientific purpose

This is the untouched confirmation of the cross-model mechanism selected by the
development-only tournament: two individually current observations need not form
one coherent authorization snapshot.  It tests the mentor's RQ2 question about
how concurrent execution and longer exposure windows change failures.  It does
not treat the development tournament as evidence.

## Frozen design

- 24 new semantic families, four in each of six task strata.
- DeepSeek Flash and GLM-5, first response only.
- Two prompt arms per family and model:
  - `BASE`: the coherent-pair contract and API are stated, but no repair recipe is
    supplied.
  - `EXPLICIT`: the same task plus a finite stable-collection recipe.
- Maximum 96 calls (`24 x 2 x 2`).
- Stage 1 sends ten `BASE` calls: five families paired across both models.
- Continue with the remaining 86 only when at least 6/10 programs are mechanism
  positive, each model contributes at least one positive, and at least three of
  five families contribute a positive.  Otherwise stop for futility.
- After a Stage-1 pass, calls are operationally batched in tens but there is no
  further outcome-contingent stopping.

## Runtime and endpoints

Each generated policy is replayed under a 2x2 schedule:

- serial vs concurrent peer activity;
- short vs long exposure window.

There are 16 deterministic schedules per cell.  Risk opportunity is 0 in both
serial cells, 1/4 in concurrent-short, and 1 in concurrent-long.  The protected
action is correct (`C`) only if it runs exactly once with two active receipts for
the required resources and both receipts match the runtime's current coordination
generation.  An unsafe action is `V`; no valid completion is `NE`; generation or
interface failure is `S0`.  The primary endpoint is `F = V union NE union S0`.

The formal interface exposes, before any model call, the read-only receipt fields
`state_id`, `active`, `coordination_generation`, and alias `version`.  Boolean
tests, equality comparisons, assignments, and finite `if` branches are supported.
Imports, helper definitions, loops, sleeps, and exception handling are forbidden.

## Frozen analysis

For each program and endpoint `Y`:

`I_Y = Y(concurrent,long) - Y(concurrent,short) - Y(serial,long) + Y(serial,short)`.

Primary confirmation uses `BASE` only.  Model-paired family effects are the unit
of cluster bootstrap (10,000 resamples; fixed seed).  Strong machine support
requires all of:

1. lower bound of the 95% family-cluster bootstrap CI for mean `I_F` is above 0;
2. mean `I_F` is positive for each model;
3. at least five of six task strata have positive mean `I_F`;
4. reference policies and causal boundary checks pass before calls;
5. no one stratum contributes more than half of the positive family effect.

The pre-registered mitigation contrast is paired within family and model:
`D_F = I_F(BASE) - I_F(EXPLICIT)`.  It supports mitigation when its family-cluster
95% CI lower bound is above 0 and both model-specific means are positive.  `V`,
`NE`, and `S0` decompositions are secondary and cannot replace the primary `F`
test.

## Boundaries

- The development tasks `XDEV-03` and `XDEV-04` are excluded.
- Prompts, runtime, schedules, slots, stage gate, and analysis are hash-frozen
  before any external call.
- Failed or invalid first responses are retained; there is no repair or resample.
- Human semantic review, if the machine gate passes, is prepared once as one
  cross-machine package after all calls.  It is confirmatory quality control, not
  an outcome-dependent relabeling exercise.

