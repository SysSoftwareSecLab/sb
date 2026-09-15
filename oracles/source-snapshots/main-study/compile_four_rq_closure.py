#!/usr/bin/env python3
"""Compile a hard-gated four-RQ/contribution closure audit from frozen outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RUN = ROOT / "05_formal/main_natural_384_v1"
OUT = RUN / "analysis"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rq1 = read(OUT / "RQ1_DEFECT_SPECTRUM.json")
    rq2 = read(OUT / "RQ2_HOLDOUT_ANALYSIS.json")
    rq3 = read(RUN / "methods/analysis/STABLE_FINDINGS_REGISTRY.json")
    rq4 = read(OUT / "RQ4_GROUPED_ERROR_MIGRATION.json")
    design = read(HERE / "DESIGN_VALIDATION.json")
    grammar = read(HERE / "TASK_GRAMMAR.json")
    mutation = read(HERE / "MUTATION_HOLDOUT_QUALIFICATION.json")

    rq1_ok = (
        rq1["status"] == "RQ1_SPECTRUM_IDENTIFIED_WITH_DUAL_REVIEWER_UNCERTAINTY"
        and rq1["program_outcomes"]["four_consensus_categories"]["DEFINITE_UNSAFE"] == 204
        and rq1["paper_level_findings"][0]["families_with_definite_unsafe_n"] == 16
    )
    rq2_ok = (
        rq2["status"] == "RQ2_HOLDOUT_GENERALIZATION_FAILURE_IDENTIFIED_AXIS_AMPLIFICATION_NOT_SUPPORTED"
        and all(item["admission"]["admitted_as_recurrent_holdout_failure"] for item in rq2["absolute_holdout_failures"])
        and not any(item["admission"]["admitted"] for item in rq2["paired_amplification_tests"].values())
    )
    rq3_ok = rq3["paper_level_count"] >= 3 and rq3["status"].startswith("PAPER_LEVEL_STABLE_FINDINGS_FROZEN")
    rq4_ok = (
        rq4["status"] == "RQ4_GROUPED_ERROR_MIGRATION_COMPLETE_SECONDARY"
        and rq4["design"]["pairs"] == 128
        and rq4["new_model_calls"] == 0
        and rq4["new_human_labels"] == 0
    )
    design_ok = (
        design["status"] == "PASS_READY_TO_FREEZE"
        and len(grammar["primitives"]) == 9
        and len(grammar["combinators"]) == 7
        and design["holdout_types"] == 4
        and mutation["natural_data"] is False
        and rq3["paper_level_count"] >= 3
    )

    audit = {
        "schema": "paper3.four_rq_closure_audit.v1",
        "status": "READY_FOR_FULL_MANUSCRIPT_DRAFTING_WITH_FROZEN_CLAIM_BOUNDARIES" if all((rq1_ok, rq2_ok, rq3_ok, rq4_ok, design_ok)) else "NOT_READY_FOR_FULL_MANUSCRIPT_DRAFTING",
        "mentor_questions": {
            "RQ1_NATURAL_DEFECTS": {
                "closed": rq1_ok,
                "evidence_level": "PAPER_LEVEL_DUAL_REVIEWER_DESCRIPTIVE",
                "answer": "Natural unsafe outcomes are widespread: 204/384 are UNSAFE under both reviewers across 16/16 families. Composition structure and event/dependency/protocol form the invariant dominant tier; four obligations form the robust cross-family top-five intersection.",
                "boundary": "Do not pool reviewer channels or force a single top category; TASK_GOAL is separate.",
                "source": "RQ1_DEFECT_SPECTRUM.json",
            },
            "RQ2_COMPOSITION_CONCURRENCY_DEPENDENCY": {
                "closed": rq2_ok,
                "evidence_level": "PAPER_LEVEL_DESCRIPTIVE_ON_PRE_FROZEN_TRUE_HOLDOUTS",
                "answer": "Genuine held-out attribute/control-flow compositions fail recurrently (joint lower bounds 56/96 and 41/48), while concurrency, distance, nestedness, and layout do not show a stable monotone amplification effect.",
                "boundary": "Claim a discontinuity at unseen composition, not that every added complexity dimension increases risk.",
                "source": "RQ2_HOLDOUT_ANALYSIS.json",
            },
            "RQ3_GUARD_METHOD_BLIND_SPOTS": {
                "closed": rq3_ok,
                "evidence_level": "FROZEN_STABLE_MAIN_FINDINGS",
                "answer": f"{rq3['paper_level_count']} non-duplicated cross-family method blind spots are admitted; prompt and guard improvements do not pass the frozen stability gates.",
                "boundary": "Do not double-count method replications or claim the guard lowers safety risk.",
                "source": "../methods/analysis/STABLE_FINDINGS_REGISTRY.json",
            },
            "RQ4_CAPABILITY_ERROR_MIGRATION": {
                "closed": rq4_ok,
                "evidence_level": "FROZEN_PROGRAM_LEVEL_NULL_PLUS_POST_HOC_GROUPED_MECHANISM",
                "answer": "Higher capability does not yield a stable change in overall UNSAFE risk. Grouped migration shows simultaneous disappearance, persistence, and emergence: API/contract failures decline in total, while semantic categories such as observation/branching can increase.",
                "boundary": "The grouped matrix is secondary and cannot support a causal 'errors become hidden' law without prospective replication.",
                "source": "RQ4_GROUPED_ERROR_MIGRATION.json",
            },
        },
        "mentor_contributions": {
            "TASK_COMPOSITION_GRAMMAR": {"closed": len(grammar["primitives"]) == 9 and len(grammar["combinators"]) == 7, "evidence": "9 primitives, 7 combinators, executable semantics"},
            "NATURAL_MUTATION_SEPARATION": {"closed": mutation["natural_data"] is False, "evidence": "384 natural programs and MF-H1 mutation/reference objects have separate identities and denominators"},
            "TRUE_COMPOSITIONAL_HOLDOUTS": {"closed": design["holdout_types"] == 4, "evidence": "attribute combination, control flow, layout, and mutation-family holdouts"},
            "STABLE_EMPIRICAL_FINDINGS": {"closed": rq3["paper_level_count"] >= 3, "evidence": f"{rq3['paper_level_count']} paper-counted stable phenomena"},
        },
        "resource_decision": {
            "new_programs_now": False,
            "new_model_calls_now": False,
            "new_human_review_now": False,
            "reason": "Every mentor question now has a defensible answer from frozen data. New data would target stronger future causal claims, not repair a missing current-paper answer.",
        },
        "writing_gate": {
            "open": all((rq1_ok, rq2_ok, rq3_ok, rq4_ok, design_ok)),
            "allowed": [
                "Draft the full manuscript around the frozen claim hierarchy and explicit evidence levels.",
                "Build tables/figures directly from authoritative JSON/CSV/workbook sources.",
                "Perform citation-backed related-work positioning without changing empirical claims.",
            ],
            "forbidden": [
                "Turn the RQ4 grouped taxonomy into a confirmatory causal claim.",
                "Claim monotone concurrency/distance/layout amplification from RQ2.",
                "Open new RQ3 micro-probes or tune methods to improve results.",
                "Pool reviewer disagreements into a single truth rate.",
            ],
        },
        "input_hashes": {
            "rq1": sha(OUT / "RQ1_DEFECT_SPECTRUM.json"),
            "rq2": sha(OUT / "RQ2_HOLDOUT_ANALYSIS.json"),
            "rq3": sha(RUN / "methods/analysis/STABLE_FINDINGS_REGISTRY.json"),
            "rq4": sha(OUT / "RQ4_GROUPED_ERROR_MIGRATION.json"),
            "design": sha(HERE / "DESIGN_VALIDATION.json"),
            "grammar": sha(HERE / "TASK_GRAMMAR.json"),
            "mutation": sha(HERE / "MUTATION_HOLDOUT_QUALIFICATION.json"),
        },
    }
    write_json = OUT / "FOUR_RQ_CLOSURE_AUDIT.json"
    write_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Paper3 four-RQ closure audit",
        "",
        f"Status: **{audit['status']}**",
        "",
        "The gate is based on frozen empirical outputs, not manuscript polish. ‘Closed’ means a defensible answer exists with an explicit claim boundary; it does not mean every hypothesis is positive or confirmatory.",
        "",
        "| Mentor question | Closed | Evidence level | Defensible answer | Boundary |",
        "|---|---|---|---|---|",
    ]
    for name, item in audit["mentor_questions"].items():
        lines.append(f"| {name} | {item['closed']} | {item['evidence_level']} | {item['answer']} | {item['boundary']} |")
    lines += ["", "## Contribution gate", "", "| Contribution | Closed | Evidence |", "|---|---|---|"]
    for name, item in audit["mentor_contributions"].items():
        lines.append(f"| {name} | {item['closed']} | {item['evidence']} |")
    lines += [
        "",
        "## Resource decision",
        "",
        "No new program generation, model call, human review, or RQ3 probe is required before manuscript drafting. A future prospectively frozen RQ4 replication is optional only if the paper wishes to make the stronger causal claim that capability shifts errors from visible API failures to hidden semantic failures.",
        "",
    ]
    (OUT / "FOUR_RQ_CLOSURE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
