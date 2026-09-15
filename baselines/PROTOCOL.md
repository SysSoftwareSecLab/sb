# Paper3 main study v1: T4 method comparison lock

Locked after the two blinded human returns were validated and the T1--T3 analysis was
completed, but before any aggregate method-versus-human comparison, any T4 source-judge
request, or any T4 guard execution.  This is therefore a post-truth analysis lock, not a
preregistration made before the main-study outcomes existed.

## Direct paper question

This table answers the mentor's third Paper3 question: what is missed by a safety prompt,
source-only LLM judges, a task-specific online guard, and finite dynamic checking?  It uses
the same 384 frozen natural-program slots and the eight frozen `MF-H1` mutations.  It creates
no standalone diagnostic program and does not tune a method after seeing its T4 performance.

## Fixed methods and eligible objects

1. **Safety prompt.**  Use the already generated 192 within-task/model/layout pairs,
   `safety_reminder - base`.  No new generation call is allowed.
2. **Source-only judges.**  DeepSeek Flash and GLM-5 each receive one request for every
   parseable natural program with a top-level async `run_task`.  They receive the public API,
   public SPEC, the exact review obligations, and numbered source only.  They receive no
   trajectory, human answer, generation model/prompt identity, reference, mutation role,
   or other detector result.  The one non-executable natural slot is retained as inapplicable.
   The same two judges also receive the eight frozen mutations and their eight already-frozen
   matched references, with `TASK_GOAL` as the controlled resource-cleanup target.  Each raw
   answer is final; response-format failure is retained and never scientifically resampled.
3. **Finite dynamic checker.**  Reuse the already stored `TASK_EVIDENCE.json`,
   `GRAMMAR_EVIDENCE.json`, and `GEOMETRY.json`.  Do not rerun natural candidates or alter
   evidence.  `TERMINAL` is compared to human `TASK_GOAL`; exact-name obligations are joined
   directly.  Unsupported human obligations are method-inapplicable, not safe.
4. **Existing online guard.**  Reuse the frozen `live_guard.py` unchanged.  It supports only
   `BUFFER_RECEIPT`, `DUAL_RESOURCE`, and `REWORK_CURRENT`; therefore it is applied to the
   108 base-prompt natural programs in the nine supported families and to the eight MF-H1
   mutation/reference pairs.  The other seven natural families and all safety-reminder slots
   are method-inapplicable.  No new guard rule may be added.  Guarded natural trajectories
   require a new two-reviewer blinded outcome assessment and will be delivered as one package.

## Truth and denominators

- Keep Chen and Z as two independent truth channels.  Do not machine-adjudicate disagreements.
- The primary exact method table uses only obligation judgments on which both reviewers gave
  the same label and both marked scope resolved.  Reviewer-specific tables and C/V/U/NA
  sensitivity are mandatory; the primary table never turns disagreement or U into safe.
- Report all attempted, inapplicable, invalid-format, U, and NA outcomes.  Program denominators
  remain 384 natural slots; method-specific effective denominators are shown separately.
- The controlled MF-H1 table stays separate from natural programs and is paired to its frozen
  correct references.  It cannot be pooled into the natural defect rate.

## Fixed outputs

- By method, human channel, obligation, family, axis, level, model, and prompt: C/V/U/NA or
  invalid counts, coverage, V recall, wrong-C-on-V, V-on-C, and residual unsafe programs.
- For the prompt and guard interventions: paired program-level risk difference, complete-case
  sensitivity, UNKNOWN worst-case bounds, 20,000 family-cluster bootstrap replicates, family
  recurrence, and leave-one-family-out direction.
- Method comparison is descriptive where input or applicability differs.  It must not rank
  methods on silently different denominators.

## Stable blind-spot gate

A method/obligation pattern may be called a stable empirical finding only when the primary
exact-agreement truth contains at least 20 resolved V instances across at least four task
families, the method produces a wrong-C or non-detection rate of at least 25%, that failure
occurs in at least half of eligible families, and a 20,000-replicate family-cluster bootstrap
95% interval has a lower endpoint above 10%.  Invalid output and U remain failures to return a
finite detection but are reported separately from wrong C.  A prompt or guard risk-difference
claim must additionally pass the same dual-reviewer UNKNOWN-bound, cluster-interval,
75%-family-direction, and leave-one-family-out gate used for T1--T3.  Failure to pass is a
negative or descriptive result, not a reason to add objects.

## Stop rule

Complete the fixed methods once.  Do not invent another judge candidate, tune the prompt or
guard, resample a model answer for scientific quality, or add a new program.  Human follow-up
is limited to the single consolidated guarded-trajectory package unless a much smaller,
conclusion-determinative reconciliation set is identified under the already locked human truth
policy.
