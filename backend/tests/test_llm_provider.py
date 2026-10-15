from __future__ import annotations

import httpx
import pytest

from app.llm.providers import LLMProviderError, OpenAICompatibleProvider


def test_openai_compatible_provider_parses_citations_and_tracks_usage(monkeypatch) -> None:
    def create_client(*, timeout: float):
        assert timeout == 2

        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
                assert url == "https://llm.example/v1/chat/completions"
                assert headers["Authorization"] == "Bearer test-api-key"
                assert json["stream"] is False
                return httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "Rendering is important [1]."}}],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                    },
                    request=httpx.Request("POST", url),
                )

        return Client()

    monkeypatch.setattr("app.llm.providers.httpx.Client", create_client)
    provider = OpenAICompatibleProvider(
        api_key="test-api-key",
        model="configured-test-model",
        base_url="https://llm.example/v1",
        timeout_seconds=2,
        max_retries=0,
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
    )
    result = provider.generate_grounded_answer(
        question="How does rendering matter?", prompt="evidence [1]", citation_ids=[1]
    )
    assert result.answer == "Rendering is important [1]."
    assert result.citation_ids == [1]
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 20
    assert result.estimated_cost_usd == pytest.approx(0.00014)


def test_provider_retries_retryable_http_status(monkeypatch) -> None:
    statuses = [429, 200]

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url: str, **_kwargs):
            status = statuses.pop(0)
            body = (
                {"choices": [{"message": {"content": "Supported [1]."}}]}
                if status == 200
                else {"error": "transient"}
            )
            return httpx.Response(status, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.llm.providers.httpx.Client", lambda **_kwargs: Client())
    monkeypatch.setattr("app.llm.providers.time.sleep", lambda _seconds: None)
    provider = OpenAICompatibleProvider(api_key="test-api-key", model="model", max_retries=1)
    assert provider.generate_grounded_answer(
        question="Question", prompt="Context", citation_ids=[1]
    ).citation_ids == [1]
    assert not statuses


def test_provider_does_not_call_external_service_without_evidence(monkeypatch) -> None:
    def unexpected_client(**_kwargs):
        raise AssertionError("provider must abstain before making a request")

    monkeypatch.setattr("app.llm.providers.httpx.Client", unexpected_client)
    provider = OpenAICompatibleProvider(api_key="key", model="model")
    result = provider.generate_grounded_answer(question="Question", prompt="", citation_ids=[])
    assert result.citation_ids == []
    assert "not provide enough evidence" in result.answer


def test_provider_rejects_remote_http_and_hides_error_body(monkeypatch) -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleProvider(api_key="key", model="model", base_url="http://api.example/v1")

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url: str, **_kwargs):
            return httpx.Response(
                401,
                text="sensitive provider response details",
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("app.llm.providers.httpx.Client", lambda **_kwargs: Client())
    provider = OpenAICompatibleProvider(api_key="key", model="model", max_retries=0)
    with pytest.raises(LLMProviderError, match="HTTP 401") as caught:
        provider.generate_grounded_answer(question="Question", prompt="Context", citation_ids=[1])
    assert "sensitive" not in str(caught.value)
