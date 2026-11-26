"""Field-level scorers. Each returns a float in [0, 1]."""

from __future__ import annotations

import json
import re
from typing import Any, Callable


_DECODER = json.JSONDecoder()


def parse_json(text: str) -> dict | None:
    """Return the first JSON object found in a model response.

    Scans every '{' and tries ``raw_decode`` from there, so code fences, chatty
    preambles and several objects in one reply are all handled."""
    if isinstance(text, dict):
        return text
    text = text or ""
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = _DECODER.raw_decode(text, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v).strip().lower())


def exact(pred: Any, gold: Any) -> float:
    if pred is None or gold is None:
        return float(pred is None and gold is None)
    return float(_norm(pred) == _norm(gold))


def set_f1(pred: Any, gold: Any) -> float:
    """F1 over lowercase items with one-to-one matching.

    Two items are compatible when the words of one are a subset of the words of
    the other (so 'seal leak' matches 'leak', but a fragment such as 'e' does
    not match 'leak'). Each predicted item can match at most one gold item, so
    a single catch-all string cannot score several gold items at once."""
    p = [_norm(x) for x in (pred or [])] if isinstance(pred, list) else []
    g = [_norm(x) for x in (gold or [])]
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    words = lambda x: set(re.findall(r"[a-z0-9]+", x))
    def match(a: str, b: str) -> bool:
        wa, wb = words(a), words(b)
        return bool(wa) and bool(wb) and (wa <= wb or wb <= wa)
    # maximum bipartite matching (Kuhn's algorithm; lists are short)
    owner: dict[int, int] = {}

    def assign(i: int, seen: set[int]) -> bool:
        for j, b in enumerate(g):
            if j not in seen and match(p[i], b):
                seen.add(j)
                if j not in owner or assign(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    tp = sum(assign(i, set()) for i in range(len(p)))
    precision, recall = tp / len(p), tp / len(g)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def numeric(tol: float = 0.01) -> Callable[[Any, Any], float]:
    def score(pred: Any, gold: Any) -> float:
        try:
            p, g = float(pred), float(gold)
        except (TypeError, ValueError):
            return 0.0
        return float(abs(p - g) <= tol * max(1.0, abs(g)))
    return score


SCORERS: dict[str, Callable[[Any, Any], float]] = {
    "exact": exact,
    "set_f1": set_f1,
    "numeric": numeric(),
}
