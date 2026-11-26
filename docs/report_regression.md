# Eval report: mock-naive / triage_v1.md (sha 0c6bd8ea4ccc)

- Cases: 20
- Overall score: **0.917**
- Valid JSON: 100%
- Backend errors: 0

| Field | Score |
|---|---|
| equipment_tag | 1.000 |
| equipment_type | 1.000 |
| discipline | 0.900 |
| priority | 0.800 |
| symptoms | 0.883 |

## Baseline comparison: REGRESSION
- overall: 0.997 -> 0.917
- discipline: 1.000 -> 0.900
- priority: 1.000 -> 0.800
- symptoms: 0.983 -> 0.883

Cases that got worse: wo-005 (0.93->0.60), wo-006 (1.00->0.80), wo-009 (1.00->0.80), wo-012 (1.00->0.80), wo-015 (1.00->0.80), wo-019 (1.00->0.80), wo-002 (1.00->0.93), wo-004 (1.00->0.93), wo-010 (1.00->0.93), wo-017 (1.00->0.93)

## Imperfect cases

| Case | Score | Weak fields |
|---|---|---|
| wo-002 | 0.93 | symptoms |
| wo-004 | 0.93 | symptoms |
| wo-005 | 0.60 | priority, symptoms |
| wo-006 | 0.80 | priority |
| wo-009 | 0.80 | discipline |
| wo-010 | 0.93 | symptoms |
| wo-012 | 0.80 | priority |
| wo-015 | 0.80 | priority |
| wo-017 | 0.93 | symptoms |
| wo-019 | 0.80 | discipline |
