"""Optional Groq layer (SPEC FR-5.4, §12.3). Used only when GROQ_API_KEY is set on the server.

What is sent: the question, column names (or aliases) with their types, and, for explanations, the already
computed answer. Never sent: rows, cell values of sensitive columns, file names, the API key to the browser.
The model can only choose an allowlisted operation; its output is validated like any other request.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ...config import settings
from .ops import OPERATIONS

log = logging.getLogger("datadoctor.ai")
URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_S = 20.0


class ProviderError(Exception):
    """Any failure of the AI provider. The caller falls back to the local interpreter and says so."""


def _chat(messages: list[dict[str, str]], json_mode: bool, transport: httpx.BaseTransport | None = None) -> str:
    body: dict[str, Any] = {"model": settings.groq_model, "messages": messages, "temperature": 0, "max_tokens": 500}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        with httpx.Client(timeout=TIMEOUT_S, transport=transport) as client:
            res = client.post(URL, json=body, headers={"Authorization": f"Bearer {settings.groq_api_key}"})
        if res.status_code != 200:
            raise ProviderError(f"provider returned HTTP {res.status_code}")
        return res.json()["choices"][0]["message"]["content"]
    except ProviderError:
        raise
    except Exception as e:  # timeouts, network, malformed body. Never log the key or the payload.
        log.warning("AI provider call failed: %s", type(e).__name__)
        raise ProviderError(type(e).__name__) from None


def _schema_text() -> str:
    lines = []
    for name, spec in OPERATIONS.items():
        props = spec["model"].model_json_schema().get("properties", {})
        keys = ", ".join(k for k in props if k != "filters")
        lines.append(f"- {name}({keys})")
    return "\n".join(lines)


def choose_operation(
    question: str, columns: list[dict[str, str]], transport: httpx.BaseTransport | None = None
) -> tuple[str | None, dict[str, Any]]:
    """Ask the model to map a question to {operation, params}. Returns (None, {}) when it declines."""
    system = (
        "You map a question about a table to ONE operation from a fixed list. Reply with JSON only: "
        '{"operation": <name or null>, "params": {...}}. Use null when no operation fits. Use only the listed column '
        "names, exactly as written. Never calculate or invent values. agg is one of count,sum,avg,min,max,median,"
        "distinct; grain is one of day,week,month,quarter,year.\nOperations:\n" + _schema_text()
    )
    user = json.dumps({"question": question[:500], "columns": columns}, ensure_ascii=False)
    raw = _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True, transport=transport
    )
    try:
        data = json.loads(raw)
        op, params = data.get("operation"), data.get("params") or {}
        if op is not None and not isinstance(op, str):
            raise ValueError
        if not isinstance(params, dict):
            raise ValueError
        return op, params
    except Exception:
        raise ProviderError("invalid JSON from provider") from None


def explain(
    question: str, answer_text: str, table: dict[str, Any] | None, transport: httpx.BaseTransport | None = None
) -> str:
    """Ask for a short plain-language explanation of an ALREADY computed answer."""
    system = (
        "Explain the computed result below in at most three short sentences for a non-technical reader. Use ONLY the "
        "numbers, dates and names that appear in it, written exactly as given. Do not add figures, causes, forecasts "
        "or advice that the result does not contain."
    )
    payload = {"question": question[:500], "computed_result": answer_text, "table": table}
    return _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        json_mode=False,
        transport=transport,
    ).strip()
