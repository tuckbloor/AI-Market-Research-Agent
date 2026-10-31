import json
import requests
import pytest
from ollama_client import installed_models, OllamaError, stream_briefing


class FakeResponse:
    def __init__(self, payload=None, lines=None, status=None):
        self.payload = payload
        self.lines = lines or []
        self.status = status
    def json(self): return self.payload
    def raise_for_status(self):
        if self.status:
            raise requests.HTTPError('404 Not Found')
    def iter_lines(self): return iter(self.lines)
    def __enter__(self): return self
    def __exit__(self, *args): return False


def test_model_dropdown_lists_only_installed_model_names(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.get', lambda *args, **kwargs: FakeResponse({
        'models': [{'name': 'qwen2.5:3b'}, {'name': 'llama3.2:3b'}, {'name': 'llama3.2:3b'}, {}, {'name': ''}]
    }))
    assert installed_models() == ['llama3.2:3b', 'qwen2.5:3b']


def test_model_list_failure_has_helpful_message(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError('network down')
    monkeypatch.setattr('ollama_client.requests.get', fail)
    with pytest.raises(OllamaError, match='Start Ollama'):
        installed_models()


def test_model_list_rejects_invalid_payload(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.get', lambda *args, **kwargs: FakeResponse(['wrong']))
    with pytest.raises(OllamaError):
        installed_models()


def test_stream_ollama_returns_chunks(monkeypatch):
    calls = []
    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        data = [
            {'message': {'content': 'Useful '}, 'done': False},
            {'message': {'content': 'research'}, 'done': False},
            {'done': True},
        ]
        return FakeResponse(lines=[json.dumps(x).encode() for x in data])
    monkeypatch.setattr('ollama_client.requests.post', fake_post)
    assert ''.join(stream_briefing('Question?', 'llama3.2:3b')) == 'Useful research'
    assert calls[0]['stream'] is True
    assert calls[0]['json']['model'] == 'llama3.2:3b'
    assert calls[0]['json']['stream'] is True


def test_stream_ollama_rejects_no_model():
    with pytest.raises(OllamaError, match='Select an installed'):
        list(stream_briefing('some question', ''))


def test_stream_ollama_reports_service_failure(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw: FakeResponse(status=404))
    with pytest.raises(OllamaError, match='rejected'):
        list(stream_briefing('Question?', 'fake'))


def test_stream_ollama_reports_empty_response(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw: FakeResponse(lines=[b'{"done":true}']))
    with pytest.raises(OllamaError, match='without an answer'):
        list(stream_briefing('Question?', 'fake'))


def test_stream_ollama_reports_bad_json(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw: FakeResponse(lines=[b'<html>502</html>']))
    with pytest.raises(OllamaError, match='unreadable'):
        list(stream_briefing('Question?', 'fake'))


def test_stream_ollama_reports_model_error(monkeypatch):
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw: FakeResponse(lines=[b'{"error":"model not found"}']))
    with pytest.raises(OllamaError, match='model not found'):
        list(stream_briefing('Question?', 'fake'))
