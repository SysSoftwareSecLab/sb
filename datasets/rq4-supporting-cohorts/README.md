# RQ4 supporting cohorts

These rows support the narrow descriptive counts reported near RQ4 in the
manuscript. They do not define the main benchmark labels and are not pooled
with the main384 or factorial320 denominators.

`prospective_reviewer1.csv` and `prospective_reviewer2.csv` contain the same
120 category-F judgments: 60 paired tasks for each of GLM-4.7 and GLM-5,
reviewed through two separate channels. A row records one program-level
observation/branching judgment. The channels evaluate the same programs and
are therefore not independent replications.

`legacy_final_truth.csv` contains 48 adjudicated legacy triads. The manuscript
uses only the GLM-4.7 and GLM-5 counts from this file. DeepSeek Flash remains
in the export so the stored triad is inspectable; it is not used to create a
scalar capability ordering.

Run the standard-library-only check from the repository root:

```bash
python3 -B oracles/source-snapshots/rq4-supporting-cohorts/analyze.py
```

The expected supporting counts are 9/60 versus 19/60 for Reviewer1,
8/60 versus 18/60 for Reviewer2, and 9/48 versus 13/48 for the legacy
adjudication. They are descriptive category-F counts, not direct
physical--temporal migration endpoints.
