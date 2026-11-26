"""Model backends. All share the signature ``(prompt: str) -> str``.

- ``mock``: deterministic rule-based extractor, so the bench runs offline and in CI.
- ``mock-naive``: a deliberately weaker variant, to demonstrate regression detection.
- ``openai``: any OpenAI-compatible /v1/chat/completions endpoint (a hosted
  API or a local model server). Configured with environment
  variables only; nothing is hard-coded.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Callable

Backend = Callable[[str], str]

TYPE_BY_PREFIX = [
    ("PSV", "safety valve"), ("FV", "control valve"), ("AT", "analyzer"),
    ("TT", "transmitter"), ("PT", "transmitter"), ("FT", "transmitter"),
    ("LT", "transmitter"), ("P", "pump"), ("K", "compressor"), ("M", "motor"),
    ("E", "heat exchanger"), ("A", "agitator"),
]
DISCIPLINE = {"transmitter": "instrumentation", "analyzer": "instrumentation",
              "control valve": "instrumentation", "motor": "electrical"}
SYMPTOM_WORDS = {
    "leak": "leak", "vibration": "vibration", "trip": "trip", "frozen": "frozen reading",
    "sticking": "sticking", "oscillat": "oscillation", "hot": "overheating",
    "fouling": "fouling", "lifted": "premature lift", "drift": "drift",
    "noise": "noise", "noisy": "noise", "bearing": "bearing wear",
    "recalibration": "drift", "3.5 ma": "signal failure", "cavitat": "cavitation",
    "insulation": "insulation damage", "cover missing": "enclosure damage",
    "intermittent": "intermittent signal",
}
HIGH = ["urgent", "asap", "immediate", "safety device", "tripped", "stopped",
        "burn risk", "manual", "3.5 ma", "only spare"]
LOW = ["next opportunity", "turnaround", "trend it", "low priority"]


def _extract(text: str, naive: bool) -> dict:
    t = text.lower()
    tag_m = re.search(r"\b([A-Z]{1,3}-\d{3}[A-Z]?)\b", text)
    tag = tag_m.group(1) if tag_m else ""
    prefix = tag.split("-")[0] if tag else ""
    etype = next((v for p, v in TYPE_BY_PREFIX if prefix == p), "unknown")
    disc = DISCIPLINE.get(etype, "mechanical")
    if not naive and any(w in t for w in ["breaker", "feeder"]):
        disc = "electrical"
    prio = "medium"
    if any(w in t for w in HIGH):
        prio = "high"
    elif any(w in t for w in LOW) and not naive:
        prio = "low"
    symptoms = []
    for k, v in SYMPTOM_WORDS.items():
        if k in t and v not in symptoms:
            symptoms.append(v)
    if naive:
        symptoms = symptoms[:1]
    return {"equipment_tag": tag, "equipment_type": etype, "discipline": disc,
            "priority": prio, "symptoms": symptoms}


def mock(prompt: str) -> str:
    return json.dumps(_extract(prompt.split("Work request:")[-1], naive=False))


def mock_naive(prompt: str) -> str:
    return json.dumps(_extract(prompt.split("Work request:")[-1], naive=True))


def openai_compatible(prompt: str) -> str:
    base = os.environ["EVAL_BASE_URL"].rstrip("/")
    model = os.environ["EVAL_MODEL"]
    key = os.environ.get("EVAL_API_KEY", "")
    body = json.dumps({"model": model, "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body, headers={
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {key}"} if key else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]


REQUIRED_ENV = {"openai": ("EVAL_BASE_URL", "EVAL_MODEL")}


def missing_config(backend: str) -> list[str]:
    """Environment variables a backend needs that are not set."""
    return [v for v in REQUIRED_ENV.get(backend, ()) if not os.environ.get(v)]


BACKENDS: dict[str, Backend] = {
    "mock": mock, "mock-naive": mock_naive, "openai": openai_compatible,
}
