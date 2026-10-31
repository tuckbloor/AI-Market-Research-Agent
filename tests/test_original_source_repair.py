"""End-to-end regression of real first run (7 Google News sources, 0 primary reads).

Uses synthetic provider HTML so real internet/Ollama cannot mask a retrieval failure.
"""
from urllib.parse import urlparse
from researcher import Source
from research_engine import ResearchJob, Settings, execute
from research_tools import candidate_original_pages, webpage_reader, ToolUnavailable


def news(i):
    return Source(f'UK SaaS news article {i}',
                  f'https://news.google.com/rss/articles/test{i}',
                  'UK software-as-a-service industry report', '', 'Google News RSS')


def test_run_with_google_news_only_still_reads_two_official_pages(monkeypatch):
    import research_engine as eng
    calls = []
    def execute_tool(tool, query, timeout=20):
        calls.append((tool, query))
        if tool == 'source_verification':
            if 'sage.com' in query or 'iris.co.uk' in query or 'theaccessgroup.com' in query:
                return [Source('Real company product page', query,
                               'The company publishes accounting and business software services on its official website',
                               '', 'Original source — directly inspected')]
            raise ToolUnavailable('Other page blocked')
        return [news(i) for i in range(1, 8)]
    monkeypatch.setattr(eng, 'execute_tool', execute_tool)
    monkeypatch.setattr(eng, 'choose_tool', lambda *a, **kw: ('finish', ''))
    monkeypatch.setattr(eng, 'stream_briefing',
                        lambda *a, **kw: iter(['A company describes its cloud accounting services [S8] [S9].']))
    job = ResearchJob('UK SAAS software requirments',
                      'Compare UK SaaS vendors, cite original websites',
                      Settings(model='small-local', max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete', snap['errors']
    assert snap['original_page_attempts'] >= 2
    assert snap['original_pages_read'] >= 2
    assert any('sage.com' in q or 'iris.co.uk' in q for tool, q in calls
               if tool == 'source_verification')
    assert 'A company describes' in snap['briefing'], snap['briefing']
    assert snap['tool_calls'] <= 8


def test_no_original_sites_no_ollama_claims(monkeypatch):
    import research_engine as eng
    def execute_tool(tool, query, timeout=20):
        if tool == 'source_verification':
            raise ToolUnavailable('403 Forbidden: original website blocks automated access')
        return [news(i) for i in range(1, 8)]
    monkeypatch.setattr(eng, 'execute_tool', execute_tool)
    monkeypatch.setattr(eng, 'stream_briefing', lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError('Must not generate factual market claims from headlines')))
    job = ResearchJob('UK SAAS software requirments', 'Market research',
                      Settings(model='energy-tf:latest', max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete'
    assert snap['original_pages_read'] == 0
    assert snap['original_page_attempts'] >= 2
    assert snap['original_page_failures'] == snap['original_page_attempts']
    assert 'Evidence is insufficient' in snap['briefing']
    assert any('403 Forbidden' in e for e in snap['errors'])
    assert snap['model_calls'] == 0
    assert snap['tool_calls'] <= 8


def test_official_candidates_only_are_not_research_evidence():
    result = candidate_original_pages('UK SaaS', [news(1)])
    assert 'https://www.iris.co.uk/' in result
    assert all('news.google.com' not in url for url in result)
    assert result.index('https://www.sage.com/en-gb/') < result.index('https://www.iris.co.uk/')


def test_redirect_reads_https_destination_only(monkeypatch):
    import research_tools as rt
    visited = []
    def validate(url):
        assert url.startswith('https://') and not url.endswith('/private')
        return url
    monkeypatch.setattr(rt, '_safe_public_url', validate)
    class Fake:
        def __init__(self, redirect):
            self.is_redirect = redirect
            self.headers = {'Location': 'https://www.iris.co.uk/cloud/' } if redirect else {'Content-Type':'text/html'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, chunk_size):
            return iter([b'<html><title>Cloud services</title><main>' + b'Cloud SaaS applications for accountants, payroll and HR departments. ' * 4 + b'</main></html>'])
    def fetch(url, **kw):
        visited.append(url)
        return Fake(len(visited) == 1)
    monkeypatch.setattr(rt, '_request', fetch)
    results = webpage_reader('https://www.iris.co.uk/')
    assert visited == ['https://www.iris.co.uk/', 'https://www.iris.co.uk/cloud/']
    assert results[0].url == 'https://www.iris.co.uk/cloud/'
    assert 'payroll' in results[0].description


def test_unsafe_redirect_is_rejected(monkeypatch):
    import research_tools as rt
    monkeypatch.setattr(rt, '_safe_public_url', lambda u:
                        (_ for _ in ()).throw(ToolUnavailable('Private/local network addresses cannot be researched.'))
                        if '127.0.0.1' in u else u)
    class Fake:
        is_redirect = True
        headers = {'Location':'http://127.0.0.1/private'}
        def __enter__(self): return self
        def __exit__(self,*args): pass
    monkeypatch.setattr(rt, '_request', lambda *a, **kw: Fake())
    import pytest
    with pytest.raises(ToolUnavailable, match='Private/local'):
        webpage_reader('https://example.org/redirect')


def test_generated_report_citing_previews_only_is_withheld(monkeypatch):
    import research_engine as eng
    def execute_tool(tool, query, timeout=20):
        if tool == 'source_verification':
            return [Source('Original software product', query,
                           'First-party statement about cloud payroll products',
                           '', 'Original source — directly inspected')]
        return [news(i) for i in range(1, 7)]
    monkeypatch.setattr(eng, 'execute_tool', execute_tool)
    monkeypatch.setattr(eng, 'choose_tool', lambda *a, **kw: ('finish', ''))
    monkeypatch.setattr(eng, 'stream_briefing', lambda *a, **kw:
                        iter(['UK SaaS market leaders have 90% market share [S1].']))
    job = ResearchJob('UK SaaS software requirements', 'Identify UK software competitors',
                      Settings(model='small-local', max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['original_pages_read'] >= 2
    assert '90% market share' not in snap['briefing']
    assert 'only search previews' in snap['briefing']
