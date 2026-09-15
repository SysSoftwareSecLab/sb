# Offline reproduction

From the repository root, with Python 3.10 or later:

```bash
python3 -B environment/revalidate.py
```

The command has no network operations, no external dependencies, and never imports or executes generated candidate programs. It writes only `results/final-revalidation/LOCAL_REVALIDATION.json`. It checks:

1. The release manifest (when present), assigned program counts, stored answer availability, and review-to-program links.
2. Original main384 reviewer counts; final adjudicated program counts and their disjoint safety bases; SAFE versus task-complete counts.
3. All three methods' original/common/adjudicated resolved-C/V confusion counts against stored scoring rows, separately for each obligation. This checks aggregation, not the independent correctness of every input judgment.
4. Every factorial320 channel's 256 factorial cell counts for direct P, structure, and exposure, recomputed from `BOUND_LONGFORM.csv` where supplied.
5. The coherent96 four-cell failure counts, 24 context effects, 67.1875-point interaction reduction, and the exact seeded 10,000-draw context-cluster bootstrap interval, from the 6,144 assigned rows.
6. Recomposition's 5,760 final scoring rows, 360 program-condition objects, exposure and direct-P states, and the existence of every bound composed-source/trace file.
7. Every value in manuscript Table I: original R1/R2 program outcomes, joint resolved outcomes, R3 outcomes, and the five overlapping category counts under all four label channels.
8. Every value in manuscript Tables III and IV from the supplied capability and direct-P/exposure rows.
9. The narrow RQ4 supporting-cohort counts (9/60 versus 19/60; 8/60 versus 18/60; and 9/48 versus 13/48), without pooling reviewer channels or cohorts.
10. The presence and sealed hashes of the four manuscript figures, their evidence-source map, and the numerical payload printed in Figures 3 and 4.

For the conservative project-identity scan:

```bash
python3 -B environment/privacy_scan.py
```

This checks the export for project-local names, host paths, transport/device
markers, legacy reviewer-channel identifiers, embedded Git history, and contact
emails in the manuscript build. It deliberately does not erase author names in
public citations or third-party notices in the conference class. Automated
token scanning reduces accidental disclosure; it cannot prove anonymity by
itself.

The original detailed reports and source snapshots are supplied so readers can inspect the definitions and secondary analyses. The portable check does **not** independently re-run every significance test, recover human review, or replay all programs. Preserving a result file is not the same as independently validating its inputs.

## Manuscript build

`final-build/paper.pdf` is the current anonymous eight-page submission candidate. Its source consists of `main.tex`, `references.tex`, `ieeeconf.cls`, and the four PNG files under `figures/`. `figures/FIGURE_PROVENANCE.json` binds those images to their paper role and evidence sources. The source uses standard TeX packages. The verified build used Tectonic; with those packages already available:

```bash
cd final-build
tectonic main.tex
```

An empty TeX cache may require downloading public packages. This release's default offline command does not build the PDF or access the network. No repository URL has been inserted yet; do not replace that absence with a fictitious URL.

## Re-execution versus reanalysis

Historical oracle and runner sources under `oracles/source-snapshots/` retain their original import/layout assumptions. They are inspection materials, **not advertised as a portable one-command replay**. A clean-container runner, pinned execution dependencies, and full end-to-end replay remain release-hardening work. Do not run arbitrary model code or historical collection scripts to compensate for missing tooling.

Exact prompts and model settings are retained, but a future API call samples a new answer from a potentially changed hosted model; it is not bit-for-bit reproduction of the stored experiment. API collection is disabled in this package, no credentials are included, and no new calls were made to prepare it.

Human labels can be inspected and their statistics recalculated. Another reader independently assigning labels would be a new review, not a computation this script can perform.
