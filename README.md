# Anonymous evidence and reproduction materials

This evaluates LLM-generated bimanual programs and their safeguards by aligning requested task structure, generated source, reached behavior, and requirement-level evidence.


## Start here

```bash
python3 -B environment/revalidate.py
python3 -B environment/privacy_scan.py
```

No API key, robot connection, external service, or third-party Python package is needed for these commands. See [REPRODUCE.md](REPRODUCE.md) for their exact checks and limits. Generated candidate programs are untrusted data: do not run them directly on a host or robot.

## What is included

| Directory | Contents |
|---|---|
| `final-build/` | Current anonymous paper PDF, TeX source, four paper figures, bibliography, and conference class |
| `datasets/` | Assigned program indexes, original reviewer channels, separate adjudication, task design and split records |
| `contracts-and-trajectories/` | Task specifications, graphs where available, recorded execution and finite geometry evidence; resolved source/trace index for the recomposition study |
| `oracles/` | Historical measurement implementations, adjudication facts, and their scope |
| `results/final-revalidation/` | Frozen study summaries and the portable offline check report |
| `hardware-evidence/` | Finite offline support results, explicitly distinguished from hardware experiments |
| `llm-generation/` | Frozen prompts, assignment manifests, model settings, stored model text and extracted code |
| `baselines/` | Stored source-judge decisions, guard traces, and original method analysis; never ground truth |
| `environment/` | Standard-library-only portable reanalysis entry point and environment notes |
| `correction-ledger.md` | Which labels and definitions changed, what remained frozen, and which results supersede historical summaries |

## Study identities

| Study | Assigned objects | Role |
|---|---:|---|
| `main384` | 384 natural programs, 16 families | Defect spectrum and safeguard comparisons; original dual review plus post-hoc third review |
| `factorial320` | 320 natural programs | 256 factorial and 64 structural-OOD programs; structure, exposure, and direct execution-dependent outcomes are separate |
| `coherent96` | 96 first answers | 24 contexts in six settings, two models, BASE/EXPLICIT; 6,144 assigned schedule records, including retained invalid-source records |
| `recomposition360` | 360 composed programs | 90 qualifying model-output slots, four compositions and 16 schedules each; 5,760 traces; exploratory structure-preserving supplement |
| `rq4-supporting-cohorts` | 120 judgments per prospective reviewer and 48 legacy adjudicated triads | Narrow descriptive observation/branching counts cited in RQ4; channels and cohorts are not pooled as independent confirmation |

These counts have different sampling units and must not be added to estimate one natural-program error rate. Recomposition outputs are controlled constructions, not 360 independent natural answers. Review channels and schedules are not independent experimental replications.

## Read results correctly

The main384 adjudication reports 248 UNSAFE, 72 SAFE, and 64 UNKNOWN under the finite safety/protocol endpoint. SAFE and task completion are distinct: 69 are both safe and task-complete. Original reviewer labels are retained, not overwritten.

The coherent96 total-failure interaction is 68.75 percentage points under BASE and 1.5625 under EXPLICIT; their difference is 67.1875 points, with the frozen 24-context bootstrap interval [60.9375, 73.4375]. Total failure includes non-execution and invalid interfaces; this is not a 67.19-point reduction in physical accidents. The human 41/48 paired susceptibility change is a different statistic.

The tested profiles do not support a universal capability-to-safety ordering or universal shallow-to-deep error migration. The structure-preserving supplement's zero observed additional direct risk is not an equivalence or general safety result.

The RQ4 supporting cohorts reproduce 9/60 versus 19/60 for Reviewer1, 8/60 versus 18/60 for Reviewer2 on the same prospective programs, and 9/48 versus 13/48 in the legacy adjudicated cohort. These are descriptive observation/branching counts, not direct physical--temporal endpoints or independent replications.

## Anonymity, provenance, and publication status

Reviewer names are replaced consistently. Account credentials, transport receipts, original return ZIPs, personal correspondence, host paths, and private transfer records are excluded. Exported JSON is normalized and personal metadata is removed; source-era hashes embedded in records describe originals, while `MANIFEST.sha256.json` describes the exported bytes. Source-line and event identities are retained. Some historical cross-references deliberately remain archival pointers, not runnable paths.

The manuscript is anonymous; cited authors and third-party copyright notices are not erased. No license for third-party assets is invented. A public code/data license and the hosting service remain for the authors to choose before publication. See [RELEASE_STATUS.md](RELEASE_STATUS.md). Public release reveals the included unpublished tasks and model outputs; local preparation is not consent to upload them.
