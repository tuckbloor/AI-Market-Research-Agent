"""Deterministic engine tests. No live internet or local Ollama required."""
from time import monotonic
from pathlib import Path

import pytest

from ollama_client import ResearchCancelled, choose_tool
from research_engine import ResearchJob, Settings, execute, source_search, start_job
from researcher import Source


def source(title='CMMS software comparison', provider='Web search — RSS preview', url=None):
    return Source(title, url or 'https://example.org/' + title.replace(' ', '-'),
                  'industrial maintenance asset management software product', '', provider)


def stub_tools(monkeypatch):
    def fake_tool(tool, query, timeout=20):
        if tool == 'source_verification':
            return [Source('Official maintenance software website', query,
                           'Published original maintenance software service information, features and customers',
                           '', 'Original source — directly inspected')]
        return [source(f'{tool} maintenance software {i}') for i in range(2)]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)


def test_settings_limits():
    Settings(model_timeout=300, max_tools=12).validated()
    for kwargs in ({'max_tools': 16}, {'model_timeout': 0}, {'total_timeout': 10}, {'source_timeout': 122}):
        with pytest.raises(ValueError):
            Settings(**kwargs).validated()


def test_timeout_while_worker_waits():
    job = ResearchJob('X','Y',Settings(total_timeout=60), started=monotonic()-100)
    assert job.snapshot()['status']=='timed_out'
    assert job.cancel.is_set()
    with pytest.raises(ResearchCancelled): job.check_active()


def test_cancel_prevents_late_results():
    job = ResearchJob('X','Y',Settings())
    job.add_sources([source()])
    job.request_cancel()
    job.add_sources([source('Another')])
    assert len(job.snapshot()['sources']) == 1
    assert job.snapshot()['status'] == 'cancelled'


def test_20_allowlisted_and_invalid_tools_rejected():
    from research_tools import SPECS, HANDLERS, TOOLS
    assert len(SPECS) == len(TOOLS) == len(HANDLERS) == 20
    with pytest.raises(ValueError):
        source_search(ResearchJob('X','Y',Settings()), 'shell_execute', 'danger')


def test_fast_research_plan_doesnt_wait_for_llm(monkeypatch):
    stub_tools(monkeypatch)
    def fake_stream(*args, **kwargs):
        yield 'A careful market briefing with links.'
    monkeypatch.setattr('research_engine.stream_briefing', fake_stream)
    monkeypatch.setattr('research_engine.choose_tool', lambda *a, **kw: ('finish',''))
    job=ResearchJob('UK industrial maintenance software','competitors pricing risks 2026',
                    Settings(model='llama3.2:3b', max_tools=7))
    execute(job)
    snap=job.snapshot()
    assert snap['status']=='complete', snap
    assert snap['search_calls'] >= 3
    assert snap['successful_tools'] >= 3
    assert snap['model_calls'] >= 1
    assert 'briefing' in snap['briefing']
    assert snap['tool_calls'] <= job.settings.max_tools
    assert any('Research plan' in event for event in snap['messages'])


def test_source_only_without_llm(monkeypatch):
    stub_tools(monkeypatch)
    monkeypatch.setattr('research_engine.choose_tool', lambda *a, **kw: pytest.fail('LLM should be off'))
    job=ResearchJob('maintenance software','competitors',Settings(use_ai=False, max_tools=4))
    execute(job)
    snap=job.snapshot()
    assert snap['model_calls']==0
    assert snap['status']=='complete'
    assert snap['search_calls']==4
    assert snap['tool_calls'] <= job.settings.max_tools


def test_source_tool_failure_maintains_other_results(monkeypatch):
    def sometimes(tool, query, timeout):
        if tool=='web_search': raise RuntimeError('blocked')
        return [source(tool)]
    monkeypatch.setattr('research_engine.execute_tool', sometimes)
    job=ResearchJob('industrial maintenance software','competitors',Settings(use_ai=False,max_tools=3))
    execute(job)
    snap=job.snapshot()
    assert snap['status']=='complete'
    assert snap['failed_tools']==1
    assert snap['successful_tools']==2
    assert snap['errors']


def test_fast_model_tool_decision_timeout_is_bounded(monkeypatch):
    class Fake:
        def raise_for_status(self): pass
        def json(self): return {'message': {'content':'{"tool":"pricing_research","query":"CMMS price"}'}}
    seen=[]
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw:(seen.append(kw),Fake())[1])
    assert choose_tool('CMMS','compare price','','llama3.2:3b',timeout_seconds=300)[0]=='pricing_research'
    assert seen[0]['timeout'][1] <= 28


def test_bad_tool_decision_rejected(monkeypatch):
    class Fake:
        def raise_for_status(self): pass
        def json(self): return {'message': {'content':'{"tool":"powershell","query":"run"}'}}
    monkeypatch.setattr('ollama_client.requests.post', lambda *a, **kw: Fake())
    assert choose_tool('x','y','','model') == ('','')


def test_ui_metrics_models_and_no_persisted_history():
    code=(Path(__file__).parent.parent/'app.py').read_text(encoding='utf-8')
    for term in ('st.selectbox(', 'st.text_input(', 'st.text_area(', 'st.fragment(run_every="1s")',
                 'Cancel research', 'Source leads', 'Successful tools', 'Failed / unavailable',
                 'Off-topic filtered', 'Public source timeout', 'Refresh models', '20 research tools'):
        assert term in code, term
    assert 'search history database' in code


def test_missing_subject_rejected():
    with pytest.raises(ValueError, match='both'):
        start_job('', 'research task', Settings())


def test_slow_ollama_choice_falls_back_after_fast_sources(monkeypatch):
    from ollama_client import OllamaError
    stub_tools(monkeypatch)
    decisions=[]
    def fail_choice(*args, **kwargs):
        decisions.append(kwargs)
        raise OllamaError('research tool selection too slow')
    monkeypatch.setattr('research_engine.choose_tool', fail_choice)
    monkeypatch.setattr('research_engine.stream_briefing', lambda *a, **k: iter(['Grounded research leads.']))
    job=ResearchJob('UK industrial maintenance software','competitors and recent news',Settings(model='llama3.2:3b',max_tools=5))
    execute(job)
    snap=job.snapshot()
    assert snap['status']=='complete'
    assert snap['was_fallback']
    assert snap['successful_tools'] >= 3
    assert not decisions  # sparse evidence uses search recovery rather than wasting time on LLM planning
    assert any('Skipped optional model planning' in x or 'Skipped optional Ollama planning' in x for x in snap['messages'])


def test_original_pages_attempted_on_research_with_enough_budget(monkeypatch):
    calls=[]
    def fake_tool(name, query, timeout=20):
        calls.append(name)
        return [source(f'{name} industrial maintenance software')]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    job=ResearchJob('UK industrial maintenance software','competitors',Settings(use_ai=False,max_tools=6))
    execute(job)
    assert 'source_verification' in calls
    assert job.snapshot()['status']=='complete'
