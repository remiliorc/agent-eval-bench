import json
from pathlib import Path

import pytest

from agent_eval_bench.runner import DEFAULT_FIELDS, RunConfig, compare, load_cases, main, run
from agent_eval_bench.scorers import exact, numeric, parse_json, set_f1

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases/work_orders.jsonl"
PROMPT = ROOT / "prompts/triage_v1.md"


def test_parse_json_handles_fences_and_garbage():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json("no json here") is None
    assert parse_json("{broken") is None
    assert parse_json('Sure! {"a": 1} and also {"b": 2}') == {"a": 1}
    assert parse_json('{bad} then {"ok": true}') == {"ok": True}


def test_scorers():
    assert exact(" Pump ", "pump") == 1.0
    assert set_f1(["seal leak"], ["leak"]) == 1.0
    assert set_f1(["leak", "noise"], ["leak"]) == pytest.approx(2 / 3, abs=0.01)
    assert set_f1([], ["leak"]) == 0.0
    assert set_f1(["e"], ["leak"]) == 0.0
    # one catch-all item cannot match several gold items
    assert set_f1(["leak vibration trip overheating noise"], ["trip", "vibration"]) \
        == pytest.approx(2 / 3)
    assert exact(None, "none") == 0.0
    assert numeric(0.01)(100.5, 100) == 1.0 and numeric(0.001)(101, 100) == 0.0


def test_cases_are_well_formed():
    cases = load_cases(CASES)
    assert len(cases) >= 20
    for c in cases:
        assert set(c["expected"]) == set(DEFAULT_FIELDS)


def test_mock_scores_high_and_is_deterministic():
    a = run(RunConfig(CASES, PROMPT, "mock", DEFAULT_FIELDS))
    b = run(RunConfig(CASES, PROMPT, "mock", DEFAULT_FIELDS))
    assert a["score"] == b["score"] >= 0.9
    assert a["json_valid_rate"] == 1.0


def test_regression_is_detected(tmp_path):
    base = run(RunConfig(CASES, PROMPT, "mock", DEFAULT_FIELDS))
    worse = run(RunConfig(CASES, PROMPT, "mock-naive", DEFAULT_FIELDS))
    cmp = compare(worse, base)
    assert cmp["regression"] and "priority" in cmp["drops"]
    bl = tmp_path / "b.json"
    bl.write_text(json.dumps(base))
    assert main(["--cases", str(CASES), "--prompt", str(PROMPT),
                 "--backend", "mock-naive", "--baseline", str(bl)]) == 1
    assert main(["--cases", str(CASES), "--prompt", str(PROMPT),
                 "--backend", "mock", "--baseline", str(bl)]) == 0


def test_backend_error_does_not_abort(monkeypatch):
    from agent_eval_bench import backends
    def boom(prompt):
        raise ConnectionError("down")
    monkeypatch.setitem(backends.BACKENDS, "boom", boom)
    import agent_eval_bench.runner as r
    monkeypatch.setitem(r.BACKENDS, "boom", boom)
    rep = run(RunConfig(CASES, PROMPT, "boom", DEFAULT_FIELDS))
    assert rep["errors"] == rep["n"] and rep["score"] == 0.0


def test_missing_cases_are_a_regression(tmp_path):
    base = run(RunConfig(CASES, PROMPT, "mock", DEFAULT_FIELDS))
    lines = CASES.read_text().splitlines()[:10]
    small = tmp_path / "work_orders.jsonl"
    small.write_text("\n".join(lines))
    cur = run(RunConfig(small, PROMPT, "mock", DEFAULT_FIELDS))
    cmp = compare(cur, base)
    assert cmp["regression"] and len(cmp["missing"]) == 10


def test_all_backend_errors_exit_2(monkeypatch):
    import agent_eval_bench.runner as r
    def boom(prompt):
        raise ConnectionError("down")
    monkeypatch.setitem(r.BACKENDS, "mock", boom)
    assert main(["--cases", str(CASES), "--prompt", str(PROMPT), "--backend", "mock"]) == 2


def test_openai_backend_fails_fast_without_config(monkeypatch, capsys):
    for v in ("EVAL_BASE_URL", "EVAL_MODEL"):
        monkeypatch.delenv(v, raising=False)
    assert main(["--cases", str(CASES), "--prompt", str(PROMPT),
                 "--backend", "openai"]) == 2
    assert "EVAL_BASE_URL" in capsys.readouterr().err
