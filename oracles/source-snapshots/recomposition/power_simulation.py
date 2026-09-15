"""Frozen pre-call planning simulation for RQ2 v4.

This simulation intentionally uses the worst family-level SD observed in the
previous RQ2 channels and Bonferroni alpha/3 as a conservative lower bound for
Holm's three-contrast procedure. It never reads or tunes against v2 outcomes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from scipy.stats import t


RNG_SEED = 2026091302
REPLICATES = 200_000
HERE = Path(__file__).resolve().parent
FAMILIES = 24
WORST_PRIOR_FAMILY_SD = 0.1336306209562122
FAMILYWISE_ALPHA = 0.05
CONTRASTS = 3
EQUIVALENCE_MARGIN = 0.10


def simulate(true_effect: float, rng: np.random.Generator) -> dict:
    values = rng.normal(
        loc=true_effect,
        scale=WORST_PRIOR_FAMILY_SD,
        size=(REPLICATES, FAMILIES),
    )
    means = values.mean(axis=1)
    ses = values.std(axis=1, ddof=1) / np.sqrt(FAMILIES)
    df = FAMILIES - 1

    # Two-sided superiority at Bonferroni alpha/3, conservative for Holm.
    superior_critical = t.ppf(1 - FAMILYWISE_ALPHA / CONTRASTS / 2, df)
    lower_superior = means - superior_critical * ses
    positive = lower_superior > 0

    # TOST at one-sided Bonferroni alpha/3 -> 1-2*alpha/3 CI.
    equivalence_critical = t.ppf(1 - FAMILYWISE_ALPHA / CONTRASTS, df)
    lower_equivalence = means - equivalence_critical * ses
    upper_equivalence = means + equivalence_critical * ses
    equivalent = (
        (lower_equivalence > -EQUIVALENCE_MARGIN)
        & (upper_equivalence < EQUIVALENCE_MARGIN)
    )

    return {
        "true_effect": true_effect,
        "positive_power_bonferroni_lower_bound": float(positive.mean()),
        "equivalence_power_bonferroni_tost": float(equivalent.mean()),
        "mean_estimate": float(means.mean()),
        "mean_standard_error": float(ses.mean()),
    }


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)
    result = {
        "schema": "paper3.rq2.structure_preserving_recomposition.power_simulation.v1",
        "rng_seed": RNG_SEED,
        "replicates": REPLICATES,
        "families": FAMILIES,
        "interpretation_population": "minimum common two-model scenario families admitted to confirmation; scenario families are not claimed as independent safety mechanisms",
        "worst_prior_family_sd": WORST_PRIOR_FAMILY_SD,
        "familywise_alpha": FAMILYWISE_ALPHA,
        "confirmatory_contrasts": CONTRASTS,
        "planning_correction": "Bonferroni alpha/3; conservative lower bound for Holm",
        "equivalence_margin": [-EQUIVALENCE_MARGIN, EQUIVALENCE_MARGIN],
        "scenarios": [simulate(effect, rng) for effect in (0.0, 0.05, 0.10, 0.15)],
    }
    target = HERE / "POWER_SIMULATION_RESULT.json"
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
