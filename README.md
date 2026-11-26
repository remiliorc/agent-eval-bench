# agent-eval-bench

A minimal, **stdlib-only** harness to evaluate LLM agents against golden sets and
**block regressions in CI**: when a prompt or model change makes the agent worse,
the build fails.

The sample task is maintenance work-request triage. Free-text requests are turned
into structured JSON (equipment tag, type, discipline, priority, symptoms). All 20
cases are invented for this repo.

## Features

- **Golden sets in JSONL**: one case per line, easy to review in a pull request.
- **Per-field scorers**: `exact`, `set_f1` (one-to-one list matching, tolerant to wording), `numeric` (relative tolerance).
- **Robust parsing**: extracts JSON from fenced or chatty model output. Invalid JSON, or a failed backend call, counts as 0 without aborting the run.
- **Prompt versioning**: every run records a short SHA-256 fingerprint of the prompt template (first 12 hex characters). Baseline comparisons warn when the prompt or case set changed.
- **Baseline comparison**: flags overall and per-field drops above a tolerance, missing cases, and the cases that got worse. Exits with code 1 so CI fails.
- **Exit codes**: 0 = OK, 1 = regression against the baseline, 2 = configuration error (missing `EVAL_BASE_URL` / `EVAL_MODEL`) or every backend call failed.
- **Pluggable backends**:
  - `mock`: deterministic rule-based extractor, runs offline.
  - `mock-naive`: a weaker variant used to demonstrate regression detection.
  - `openai`: any OpenAI-compatible endpoint (a hosted API or a local model server), configured only through environment variables.

## Quick start

```bash
pip install -e ".[dev]"
pytest -q

# run against the committed baseline: passes with exit code 0
agent-eval --backend mock --baseline baselines/mock_triage_v1.json

# simulate a bad change: the gate fails with exit code 1
agent-eval --backend mock-naive --baseline baselines/mock_triage_v1.json

# save a baseline of your own (new file, the committed one is left as is)
agent-eval --backend mock --save-baseline baselines/my_baseline.json
```

Against a real model:

```bash
export EVAL_BASE_URL=http://localhost:8080/v1    # e.g. a local model server
export EVAL_MODEL=<model-name>
export EVAL_API_KEY=                              # if the endpoint needs one
agent-eval --backend openai --report docs/report_llm.md
```

## Sample output

The regression demo ([`docs/report_regression.md`](docs/report_regression.md)) compares
`mock-naive` against the `mock` baseline:

| Field | Baseline | Candidate |
|---|---|---|
| overall | 0.997 | 0.917 |
| discipline | 1.000 | 0.900 |
| priority | 1.000 | 0.800 |
| symptoms | 0.983 | 0.883 |

Result: **REGRESSION**, exit code 1.

> The `mock` backend's rules were written against these same cases, so its high score
> only shows that the pipeline works. It is not a benchmark result. To measure a
> real model, use the `openai` backend.

## Using it in CI

The included workflow runs the unit tests plus a regression gate on every push.
To gate a real model, point the workflow at your endpoint with repository secrets
and commit the baseline you accept.

## Extending

- New task: add a JSONL file under `cases/`, a prompt under `prompts/`, and a field → scorer map.
- New scorer: add a function `(pred, gold) -> float in [0, 1]` to `SCORERS`.
- LLM-as-judge: wrap a backend call as a scorer. Keep it out of the default CI path, because it is non-deterministic.

## License

MIT
