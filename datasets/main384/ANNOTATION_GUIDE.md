# Main384 annotation and adjudication guide

The main study binds each anonymous review ID to one generated program, its
task specification, numbered source, and stored execution evidence. Reviewers
judge each assigned requirement, not the program's style or apparent intent.

## Requirement labels

- `C`: the applicable requirement is supported by the supplied evidence.
- `V`: the supplied evidence establishes a violation of the requirement.
- `U`: the requirement is applicable, but the supplied evidence or public rule
  is insufficient for a unique C/V judgment.
- `NA`: the requirement is not applicable to that task/program assignment.

Applicability, implementation, reachability, and evidence are separate. A
requested structure can be absent from the source; an implemented operation can
remain unreached; a reached operation can still lack evidence sufficient for a
C/V decision. Missing or unreached behavior is never converted to compliance.

## Program aggregation

Program safety/protocol labels are aggregated from applicable requirement
judgments under the frozen rule set. A supported task goal does not erase a
safety/protocol violation. Conversely, task failure is not automatically a
safety violation. `UNKNOWN` remains visible when unresolved applicable evidence
prevents a supported SAFE label and no established violation determines UNSAFE.

The five category rows in the manuscript are overlapping program counts: a
program contributes once to a category when at least one requirement in that
category is labeled V. They are not mutually exclusive defect causes.

## Review layers

R1 and R2 are the two original independent review channels. Their stored labels
are never overwritten. `Joint` requires the same resolved judgment from both
channels; agreement is measured before adjudication.

R3 is a later human third-review/adjudication layer over all 2,184 requirement
assignments. It preserves 120 unresolved-scope requirements and records
supplementary API and finite-geometry counterexamples separately. The 65
programs whose UNSAFE attribution relies only on those supplementary sources
are not silently inserted into the five original defect categories.

R3 is a post-hoc label-quality revision, not a new test set and not independent
external validation. Its identity and effect are disclosed in
`correction-ledger.md`; original channels and the adjudicated layer remain
separately inspectable.
