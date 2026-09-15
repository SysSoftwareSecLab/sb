"""Planning sensitivity for the fixed 22-family amendment main description set."""
from __future__ import annotations

import json
import os
from pathlib import Path
import numpy as np
from scipy.stats import t


HERE = Path(__file__).resolve().parent
SEED = 2026091406
REPLICATES = 200_000
N = 22
SD = 0.1336306209562122
ALPHA = 0.05
K = 3
MARGIN = 0.10


def main() -> None:
    rng = np.random.default_rng(SEED)
    rows = []
    for effect in (0.0, 0.05, 0.10, 0.15):
        values = rng.normal(effect, SD, size=(REPLICATES, N))
        means = values.mean(axis=1)
        ses = values.std(axis=1, ddof=1) / np.sqrt(N)
        positive = means - t.ppf(1 - ALPHA / K / 2, N - 1) * ses > 0
        equivalent = (
            (means - t.ppf(1 - ALPHA / K, N - 1) * ses > -MARGIN)
            & (means + t.ppf(1 - ALPHA / K, N - 1) * ses < MARGIN)
        )
        rows.append({
            "true_effect": effect,
            "positive_power_bonferroni_lower_bound": float(positive.mean()),
            "equivalence_power_bonferroni_tost": float(equivalent.mean()),
            "mean_standard_error": float(ses.mean()),
        })
    result = {
        "schema": "paper3.rq2.v4_amendment.power_22_family.v1",
        "families": N, "replicates": REPLICATES, "rng_seed": SEED,
        "worst_prior_family_sd": SD, "familywise_alpha": ALPHA,
        "contrasts": K, "equivalence_margin": [-MARGIN, MARGIN],
        "partially_outcome_exposed_no_equivalence_claim": True,
        "scenarios": rows,
    }
    target = HERE / "POWER_22_FAMILY.json"
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
