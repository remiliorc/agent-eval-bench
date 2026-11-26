"""Run a golden set through a backend, score it, compare with a baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .backends import BACKENDS, missing_config
from .scorers import SCORERS, parse_json

DEFAULT_FIELDS = {
    "equipment_tag": "exact", "equipment_type": "exact",
    "discipline": "exact", "priority": "exact", "symptoms": "set_f1",
}


@dataclass
class RunConfig:
    cases: Path
    prompt: Path
    backend: str
    fields: dict


def load_cases(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: {e}") from e
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return rows


def run(cfg: RunConfig) -> dict:
    template = cfg.prompt.read_text()
    prompt_hash = hashlib.sha256(template.encode()).hexdigest()[:12]
    model = BACKENDS[cfg.backend]
    results = []
    for case in load_cases(cfg.cases):
        t0 = time.perf_counter()
        error = None
        try:
            raw = model(template.replace("{input}", case["input"]))
        except Exception as e:  # one failing call must not abort the run
            raw, error = "", f"{type(e).__name__}: {e}"
        latency = time.perf_counter() - t0
        pred = parse_json(raw)
        fields = {}
        for name, scorer in cfg.fields.items():
            fields[name] = (SCORERS[scorer](pred.get(name), case["expected"].get(name))
                            if pred is not None else 0.0)
        results.append({
            "id": case["id"], "valid_json": pred is not None,
            "score": round(statistics.mean(fields.values()), 4),
            "fields": fields, "latency_s": round(latency, 4),
            "prediction": pred, "error": error,
        })
    per_field = {f: round(statistics.mean(r["fields"][f] for r in results), 4)
                 for f in cfg.fields}
    return {
        "backend": cfg.backend, "prompt": cfg.prompt.name,
        "prompt_sha256": prompt_hash, "cases": cfg.cases.name,
        "n": len(results),
        "score": round(statistics.mean(r["score"] for r in results), 4),
        "json_valid_rate": round(sum(r["valid_json"] for r in results) / len(results), 4),
        "errors": sum(r["error"] is not None for r in results),
        "per_field": per_field,
        "results": results,
    }


def compare(current: dict, baseline: dict, tolerance: float = 0.02) -> dict:
    """Flag a regression if the overall or any field score drops more than ``tolerance``."""
    drops = {}
    if baseline["score"] - current["score"] > tolerance:
        drops["overall"] = (baseline["score"], current["score"])
    for f, b in baseline["per_field"].items():
        c = current["per_field"].get(f, 0.0)
        if b - c > tolerance:
            drops[f] = (b, c)
    base_by_id = {r["id"]: r["score"] for r in baseline["results"]}
    cur_ids = {r["id"] for r in current["results"]}
    missing = sorted(set(base_by_id) - cur_ids)
    warnings = []
    if missing:
        drops["missing_cases"] = (len(base_by_id), len(cur_ids))
    if baseline.get("prompt_sha256") != current.get("prompt_sha256"):
        warnings.append("prompt changed since baseline")
    if baseline.get("cases") != current.get("cases") or set(base_by_id) != cur_ids:
        warnings.append("case set differs from baseline")
    worse = sorted(
        [(r["id"], base_by_id[r["id"]], r["score"]) for r in current["results"]
         if r["id"] in base_by_id and base_by_id[r["id"]] - r["score"] > 1e-9],
        key=lambda x: x[2] - x[1])
    return {"regression": bool(drops), "drops": drops, "worse_cases": worse,
            "missing": missing, "warnings": warnings}


def to_markdown(report: dict, cmp: dict | None = None) -> str:
    lines = [f"# Eval report: {report['backend']} / {report['prompt']} "
             f"(sha {report['prompt_sha256']})", "",
             f"- Cases: {report['n']}",
             f"- Overall score: **{report['score']:.3f}**",
             f"- Valid JSON: {report['json_valid_rate']:.0%}",
             f"- Backend errors: {report.get('errors', 0)}", "",
             "| Field | Score |", "|---|---|"]
    lines += [f"| {k} | {v:.3f} |" for k, v in report["per_field"].items()]
    if cmp:
        lines += ["", f"## Baseline comparison: "
                  f"{'REGRESSION' if cmp['regression'] else 'OK'}"]
        for w in cmp.get("warnings", []):
            lines.append(f"- warning: {w}")
        for k, (b, c) in cmp["drops"].items():
            lines.append(f"- {k}: {b:.3f} -> {c:.3f}" if k != "missing_cases"
                         else f"- missing cases: baseline {b}, current {c}")
        if cmp["worse_cases"]:
            lines.append("")
            lines.append("Cases that got worse: " + ", ".join(
                f"{i} ({b:.2f}->{c:.2f})" for i, b, c in cmp["worse_cases"][:10]))
    failing = [r for r in report["results"] if r["score"] < 1.0]
    if failing:
        lines += ["", "## Imperfect cases", "", "| Case | Score | Weak fields |",
                  "|---|---|---|"]
        for r in failing:
            weak = ", ".join(f for f, s in r["fields"].items() if s < 1.0)
            lines.append(f"| {r['id']} | {r['score']:.2f} | {weak} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a golden-set evaluation")
    ap.add_argument("--cases", type=Path, default=Path("cases/work_orders.jsonl"))
    ap.add_argument("--prompt", type=Path, default=Path("prompts/triage_v1.md"))
    ap.add_argument("--backend", choices=sorted(BACKENDS), default="mock")
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--save-baseline", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--tolerance", type=float, default=0.02)
    a = ap.parse_args(argv)

    missing = missing_config(a.backend)
    if missing:
        print(f"backend {a.backend!r} needs: {', '.join(missing)}", file=sys.stderr)
        return 2
    rep = run(RunConfig(a.cases, a.prompt, a.backend, DEFAULT_FIELDS))
    cmp = None
    if a.baseline:
        cmp = compare(rep, json.loads(a.baseline.read_text()), a.tolerance)
    if a.save_baseline:
        a.save_baseline.write_text(json.dumps(rep, indent=2))
    md = to_markdown(rep, cmp)
    if a.report:
        a.report.write_text(md)
    print(md)
    if rep["errors"] == rep["n"]:
        print("every backend call failed: check the endpoint configuration",
              file=sys.stderr)
        return 2
    return 1 if cmp and cmp["regression"] else 0


if __name__ == "__main__":
    sys.exit(main())
