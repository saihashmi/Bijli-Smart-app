"""The Groq client: request shape, key handling and failure mapping (HTTP is mocked; no network)."""

import json

import httpx
import pytest

from app.services.analyst import provider


def _transport(handler):
    return httpx.MockTransport(handler)


def test_choose_operation_sends_schema_not_data_and_parses_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        content = json.dumps({"operation": "aggregate", "params": {"measure": "Amount", "agg": "sum"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    op, params = provider.choose_operation(
        "total amount?", [{"name": "Amount", "type": "number"}], transport=_transport(handler)
    )
    assert (op, params) == ("aggregate", {"measure": "Amount", "agg": "sum"})
    assert seen["auth"].startswith("Bearer ")
    assert seen["body"]["temperature"] == 0 and seen["body"]["response_format"] == {"type": "json_object"}
    system = seen["body"]["messages"][0]["content"]
    assert "count_rows" in system and "quality_explain" in system  # the allowlist, nothing else


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "rate limit"}),
        httpx.Response(500, text="oops"),
        httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": '{"operation": 5}'}}]}),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_provider_problems_become_provider_errors(response):
    with pytest.raises(provider.ProviderError):
        provider.choose_operation("q", [], transport=_transport(lambda request: response))


def test_timeouts_become_provider_errors_without_leaking_details(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(provider.ProviderError):
        provider.explain("q", "The total is 5.", None, transport=_transport(handler))
    assert "Bearer" not in caplog.text and "The total is 5." not in caplog.text
