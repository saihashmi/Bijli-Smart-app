"""Natural-language layer on top of computed results.

Rule: the AI never produces analytical results. It receives only facts computed by
`analysis.py` / `cleaning.py` and may interpret them. Every sentence it returns is checked:
any number that does not appear in the computed facts is treated as invented and the
sentence is dropped. Without a GROQ_API_KEY, the deterministic facts are returned as-is.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import settings

NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")
# Small integers are allowed in prose ("3 steps", "24 hours", "one in 2") without being facts.
SAFE_SMALL_INTS = set(range(0, 25)) | {30, 31, 48, 50, 60, 100}

SYSTEM_PROMPT = """You are an energy analyst for the Bijli Smart app, which helps people save electricity.
You are given FACTS that were computed from the user's uploaded meter or bill data.

Strict rules:
- Use ONLY the numbers that appear in FACTS. Never calculate, estimate, round differently or invent figures.
- If a point needs a number that is not in FACTS, make the point without a number.
- Refer to facts by their id in "fact_ids".
- Practical tips (e.g. shifting appliance use out of peak hours, checking for faulty appliances on anomaly days)
  are welcome, but must not state savings amounts unless those amounts are in FACTS.
- Plain, friendly English. No markdown.

Return JSON only:
{"summary": "2-3 sentences", "insights": [{"title": "...", "explanation": "...", "fact_ids": ["..."]}],
 "recommendations": [{"action": "...", "why": "...", "fact_ids": ["..."]}]}"""

CLEANING_PROMPT = """You are a data-quality assistant for the Bijli Smart electricity app.
You are given a PROFILE of an uploaded file and a list of ALLOWED_ACTIONS, each with counts computed by the app.

Strict rules:
- You may only refer to actions by their exact id from ALLOWED_ACTIONS. Do not propose any other action.
- Use only numbers that appear in the PROFILE or ALLOWED_ACTIONS. Never invent counts.
- Explain why each action matters for electricity analysis and whether you would apply it.
- Plain English. No markdown.

Return JSON only:
{"overview": "1-2 sentences", "actions": [{"id": "<allowed id>", "advice": "...", "apply": true}]}"""


# ---------- number verification ----------

def _num_variants(x: float) -> set[str]:
    out = set()
    for d in (0, 1, 2, 3):
        v = round(x, d)
        out.add(f"{v:.{d}f}")
        out.add(f"{v:,.{d}f}")
        if d and float(v).is_integer():
            out.add(f"{int(v)}")
    out.add(str(abs(int(x))) if float(x).is_integer() else str(x))
    return {s.lstrip("+-") for s in out}


def _collect_numbers(obj: Any, acc: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, str):
        for m in NUM_RE.findall(obj):
            try:
                acc.add(float(m.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numbers(v, acc)


def allowed_tokens(source: Any) -> set[str]:
    nums: set[float] = set()
    _collect_numbers(source, nums)
    tokens: set[str] = set()
    for n in nums:
        tokens |= _num_variants(n)
        tokens |= _num_variants(abs(n))
    return tokens


def unverified_numbers(text: str, tokens: set[str]) -> list[str]:
    bad = []
    for raw in NUM_RE.findall(text):
        tok = raw.lstrip("+-")
        plain = tok.replace(",", "")
        if tok in tokens or plain in tokens:
            continue
        try:
            val = float(plain)
        except ValueError:
            continue
        if val.is_integer() and int(val) in SAFE_SMALL_INTS:
            continue
        # Dates like 2024-03-05 are split into parts by the regex; allow any year-like/date token present in source.
        if plain in tokens:
            continue
        bad.append(raw)
    return bad


def _strip_dates(text: str) -> str:
    # ISO dates / months come from the facts verbatim; the checker treats them separately.
    return re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b", " ", text)


def _date_tokens(source: Any) -> set[str]:
    blob = json.dumps(source, default=str)
    return set(re.findall(r"\b\d{4}-\d{2}(?:-\d{2})?\b", blob))


def verify_text(text: str, tokens: set[str], dates: set[str]) -> tuple[bool, list[str]]:
    used_dates = set(re.findall(r"\b\d{4}-\d{2}(?:-\d{2})?\b", text))
    bad = [d for d in used_dates if d not in dates]
    bad += unverified_numbers(_strip_dates(text), tokens)
    return (not bad), bad


# ---------- deterministic fallback ----------

def rule_based(analysis: dict[str, Any]) -> dict[str, Any]:
    facts = analysis.get("facts", [])
    order = {"warning": 0, "positive": 1, "info": 2}
    ranked = sorted([f for f in facts if f["category"] != "saving"], key=lambda f: order.get(f["severity"], 3))
    return {
        "source": "rules",
        "summary": " ".join(f["text"] for f in facts if f["id"] in ("total", "avg_daily", "trend")),
        "insights": [{"title": f["category"].title(), "explanation": f["text"], "fact_ids": [f["id"]],
                      "severity": f["severity"]} for f in ranked],
        "recommendations": [{"action": f["text"].split(":")[0], "why": f["text"], "fact_ids": [f["id"]]}
                            for f in facts if f["category"] == "saving"],
        "removed": [],
        "facts": facts,
    }


# ---------- Groq ----------

class AIError(RuntimeError):
    pass


def _chat(system: str, user_payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.ai_enabled:
        raise AIError("AI is not configured (set GROQ_API_KEY).")
    try:
        resp = httpx.post(
            f"{settings.groq_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user_payload, default=str)},
                ],
            },
            timeout=settings.groq_timeout_s,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except httpx.HTTPStatusError as e:
        raise AIError(f"Groq API returned {e.response.status_code}.") from e
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
        raise AIError(f"AI request failed: {e}") from e


def _filter_items(items: Any, fields: list[str], tokens: set[str], dates: set[str],
                  valid_ids: set[str], id_field: str, removed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(f, "")) for f in fields)
        ok, bad = verify_text(text, tokens, dates)
        if not ok:
            removed.append({"text": text.strip(), "reason": f"Contains figures not in the computed results: {', '.join(bad)}"})
            continue
        ids = item.get(id_field)
        if isinstance(ids, list):
            item[id_field] = [i for i in ids if i in valid_ids]
        elif isinstance(ids, str):
            if ids not in valid_ids:
                removed.append({"text": text.strip(), "reason": f"Refers to unknown id '{ids}'."})
                continue
        kept.append({k: item.get(k) for k in fields + [id_field] + (["apply"] if "apply" in item else [])})
    return kept


def ai_insights(analysis: dict[str, Any]) -> dict[str, Any]:
    facts = analysis.get("facts", [])
    payload = {"FACTS": [{"id": f["id"], "text": f["text"], "values": f["values"]} for f in facts],
               "currency": analysis.get("summary", {}).get("currency")}
    raw = _chat(SYSTEM_PROMPT, payload)
    tokens = allowed_tokens(payload)
    dates = _date_tokens(payload)
    ids = {f["id"] for f in facts}
    removed: list[dict[str, Any]] = []

    summary = str(raw.get("summary", ""))
    ok, bad = verify_text(summary, tokens, dates)
    if not ok:
        removed.append({"text": summary, "reason": f"Contains figures not in the computed results: {', '.join(bad)}"})
        summary = rule_based(analysis)["summary"]

    insights = _filter_items(raw.get("insights"), ["title", "explanation"], tokens, dates, ids, "fact_ids", removed)
    sev = {f["id"]: f["severity"] for f in facts}
    for i in insights:
        i["severity"] = next((sev[x] for x in i.get("fact_ids") or [] if x in sev), "info")
    recs = _filter_items(raw.get("recommendations"), ["action", "why"], tokens, dates, ids, "fact_ids", removed)
    return {"source": "groq", "model": settings.groq_model, "summary": summary, "insights": insights,
            "recommendations": recs, "removed": removed, "facts": facts}


def insights(analysis: dict[str, Any], use_ai: bool = True) -> dict[str, Any]:
    if analysis.get("empty"):
        return {"source": "rules", "summary": analysis.get("message", ""), "insights": [], "recommendations": [],
                "removed": [], "facts": []}
    if use_ai and settings.ai_enabled:
        try:
            return ai_insights(analysis)
        except AIError as e:
            out = rule_based(analysis)
            out["ai_error"] = str(e)
            return out
    return rule_based(analysis)


def cleaning_advice(prof: dict[str, Any]) -> dict[str, Any]:
    suggestions = prof.get("suggestions", [])
    deterministic = {
        "source": "rules",
        "overview": f"{len(suggestions)} possible cleaning step(s) found in {prof.get('rows')} rows."
        if suggestions else "No data-quality problems were detected.",
        "actions": [{"id": s["id"], "advice": s["reason"], "apply": s["recommended"]} for s in suggestions],
        "removed": [],
    }
    if not settings.ai_enabled or not suggestions:
        return deterministic
    payload = {
        "PROFILE": {k: prof[k] for k in ("rows", "columns_count", "empty_rows", "duplicate_rows")}
        | {"columns": [{k: c.get(k) for k in ("name", "role", "kind", "missing", "unparseable", "negatives")}
                       for c in prof.get("columns", [])]},
        "ALLOWED_ACTIONS": [{k: s[k] for k in ("id", "title", "affected_rows", "reason", "recommended")} for s in suggestions],
    }
    try:
        raw = _chat(CLEANING_PROMPT, payload)
    except AIError as e:
        deterministic["ai_error"] = str(e)
        return deterministic
    tokens, dates = allowed_tokens(payload), _date_tokens(payload)
    removed: list[dict[str, Any]] = []
    overview = str(raw.get("overview", ""))
    ok, bad = verify_text(overview, tokens, dates)
    if not ok:
        removed.append({"text": overview, "reason": f"Contains figures not in the profile: {', '.join(bad)}"})
        overview = deterministic["overview"]
    actions = _filter_items(raw.get("actions"), ["advice"], tokens, dates, {s["id"] for s in suggestions}, "id", removed)
    # Make sure every allowed action is still represented with its computed reason.
    seen = {a["id"] for a in actions}
    for s in suggestions:
        if s["id"] not in seen:
            actions.append({"id": s["id"], "advice": s["reason"], "apply": s["recommended"]})
    for a in actions:
        a["apply"] = bool(a.get("apply", False))
    return {"source": "groq", "model": settings.groq_model, "overview": overview, "actions": actions, "removed": removed}
