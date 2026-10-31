import time
from research_progress import stream_events
from researcher import collect_steps


def test_feedback_while_model_is_slow():
    def slow_chunks():
        time.sleep(0.04)
        yield 'Hello '
        yield 'world'
    events = list(stream_events(slow_chunks, tick=0.005))
    assert any(kind == 'waiting' for kind, _, _ in events)
    assert ''.join(v for k, v, _ in events if k == 'text') == 'Hello world'
    assert all(elapsed >= 0 for _, _, elapsed in events)


def test_stream_error_is_not_silent():
    def fail():
        yield 'partial'
        raise RuntimeError('test failure')
    events = list(stream_events(fail, tick=0.005))
    assert ('error', 'test failure') in [(k,v) for k,v,_ in events]


def test_provider_activity_announces_before_requests(monkeypatch):
    events = []
    def wiki(q):
        events.append('requested Wikipedia')
        return []
    def news(q):
        events.append('requested news')
        return []
    monkeypatch.setattr('researcher.wikipedia_search', wiki)
    monkeypatch.setattr('researcher.news_search', news)
    assert list(collect_steps('example', on_start=lambda name: events.append('starting '+name))) == [
        ('Wikipedia', [], None), ('Google News RSS', [], None)
    ]
    assert events == ['starting Wikipedia', 'requested Wikipedia', 'starting Google News RSS', 'requested news']


def test_app_has_visible_help_and_activity():
    from pathlib import Path
    src = (Path(__file__).parent.parent/'app.py').read_text(encoding='utf-8')
    assert 'st.selectbox(' in src
    assert 'options=models' in src
    assert 'st.text_area(' in src
    assert 'background: #fff !important;' in src
    assert 'Research objective — type or replace this text' in src
    assert 'Live agent activity and metrics' in src
    assert 'Ollama preparing briefing' in (Path(__file__).parent.parent/'research_engine.py').read_text(encoding='utf-8')
