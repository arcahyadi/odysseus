"""Regression checks for the local multi-model request path."""

from types import SimpleNamespace

import pytest

from src import multi_model_executor as module


@pytest.mark.asyncio
async def test_registered_endpoint_identity_and_chat_url(monkeypatch):
    looked_up = []
    sent = []

    class FakeDb:
        def close(self):
            pass

    class FakeResponse:
        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"hello"}}]}'
            yield 'data: [DONE]'

    class FakeClient:
        def __init__(self, **kwargs):
            self.headers = kwargs['headers']

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def post(self, url, json):
            sent.append((url, json['model'], self.headers))
            return FakeResponse()

    def find_endpoint(_db, endpoint_id, owner):
        looked_up.append((endpoint_id, owner))
        return SimpleNamespace(base_url=f'https://{endpoint_id}.example/v1', api_key='secret')

    monkeypatch.setattr(module, 'SessionLocal', FakeDb)
    monkeypatch.setattr(module, '_owned_endpoint_by_id', find_endpoint)
    monkeypatch.setattr(module.httpx, 'AsyncClient', FakeClient)

    results = await module.MultiModelExecutor().execute_multi_model(
        prompt='hi', model_ids=['model-a', 'model-b'],
        endpoint_urls=['https://ignored.example/v1', 'https://ignored.example/v1'],
        endpoint_ids=['endpoint-a', 'endpoint-b'], owner='alice', headers={}, config={},
    )

    assert looked_up == [('endpoint-a', 'alice'), ('endpoint-b', 'alice')]
    assert [url for url, _, _ in sent] == [
        'https://endpoint-a.example/v1/chat/completions',
        'https://endpoint-b.example/v1/chat/completions',
    ]
    assert results['model-a']['messages'] == [{'role': 'assistant', 'content': 'hello'}]
    assert results['model-b']['success'] is True


@pytest.mark.asyncio
async def test_missing_registered_endpoint_fails_before_request(monkeypatch):
    class FakeDb:
        def close(self):
            pass

    monkeypatch.setattr(module, 'SessionLocal', FakeDb)
    monkeypatch.setattr(module, '_owned_endpoint_by_id', lambda *_: None)

    with pytest.raises(ValueError, match='Model endpoint not found'):
        await module.MultiModelExecutor().execute_multi_model(
            prompt='hi', model_ids=['model-a'], endpoint_urls=None,
            endpoint_ids=['not-owned'], owner='alice', headers={}, config={},
        )
