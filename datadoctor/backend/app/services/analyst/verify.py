"""Checks an AI-written explanation against the computed result (SPEC FR-5.6).

Every number, date and quoted label in the explanation must already appear in the verified material (the local
template answer, the result table and the notes). If anything else appears, the explanation is rejected.
"""

from __future__ import annotations

import re
from typing import Any

NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?")
QUOTED = re.compile(r"[“\"]([^”\"]{1,80})[”\"]")
DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\b\d{4}-Q[1-4]\b")
WORD_NUMBERS = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million|"
    r"billion|half|double|twice|triple|quarter|third|dozen)\b",
    re.I,
)


def _norm(token: str) -> str:
    t = token.replace(",", "").rstrip("%")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def _material(answer: dict[str, Any]) -> str:
    parts = [answer.get("answer", ""), " ".join(answer.get("notes") or [])]
    table = answer.get("table")
    if table:
        parts.append(" ".join(table["columns"]))
        parts += [" ".join(str(c) for c in row) for row in table["rows"]]
    return "\n".join(parts)


def verify(explanation: str, answer: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (accepted, reason for rejection)."""
    text = explanation.strip()
    if not text:
        return False, "empty explanation"
    if len(text) > 1200:
        return False, "explanation too long"
    source = _material(answer)
    dates_ok = set(DATE.findall(source))
    for d in DATE.findall(text):
        if d not in dates_ok:
            return False, f"date not in the result: {d}"
    stripped_source, stripped_text = DATE.sub(" ", source), DATE.sub(" ", text)
    allowed = {_norm(n) for n in NUMBER.findall(stripped_source)}
    for n in NUMBER.findall(stripped_text):
        if _norm(n) not in allowed:
            return False, f"number not in the result: {n}"
    if WORD_NUMBERS.search(text) and not all(w.lower() in source.lower() for w in WORD_NUMBERS.findall(text)):
        return False, "quantity written in words that is not in the result"
    labels = {q.casefold() for q in QUOTED.findall(source)}
    cells = {str(c).casefold() for row in (answer.get("table") or {}).get("rows", []) for c in row}
    for q in QUOTED.findall(text):
        if q.casefold() not in labels and q.casefold() not in cells:
            return False, f"label not in the result: {q}"
    return True, None
