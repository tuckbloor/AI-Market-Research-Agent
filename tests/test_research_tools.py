from types import SimpleNamespace
import pytest
from researcher import Source
from research_tools import (TOOLS, HANDLERS, SPECS, ToolUnavailable, execute_tool,
                            choose_research_plan, filter_and_rank, relevance_score,
                            companies_house, webpage_reader, _safe_public_url)


def src(text):
    return Source(text, f'https://example.com/{len(text)}', text, '', 'Test')


def test_20_real_handlers_and_no_duplicate_names():
    assert len(SPECS) == 20
    assert set(TOOLS) == set(HANDLERS)
    assert len({id(fn) for fn in HANDLERS.values()}) == 20


def test_every_tool_dispatches_its_own_handler(monkeypatch):
    import research_tools as rt
    for name in TOOLS:
        if name == 'google_trends' or name == 'companies_house':
            continue
        value=src(name)
        monkeypatch.setitem(rt.HANDLERS, name, lambda q, timeout, s=value: [s])
        result=execute_tool(name, 'industrial maintenance software')
        assert result[0].title == name


def test_missing_ch_key_is_explicit(monkeypatch):
    monkeypatch.delenv('COMPANIES_HOUSE_API_KEY', raising=False)
    with pytest.raises(ToolUnavailable, match='API_KEY'):
        companies_house('Industrial maintenance software')


def test_companies_house_auth_uses_key_and_official_data(monkeypatch):
    import research_tools as rt
    monkeypatch.setenv('COMPANIES_HOUSE_API_KEY', 'example-secret')
    captured=[]
    class Fake:
        def json(self):
            return {'items':[{'company_number':'12345678','title':'Example Limited', 'company_status':'active'}]}
    def fake_request(*args, **kwargs):
        captured.append(kwargs)
        return Fake()
    monkeypatch.setattr(rt, '_request', fake_request)
    results=companies_house('Example')
    assert '12345678' in results[0].url
    assert captured[0]['auth']==('example-secret','')


def test_relevance_filters_fleet_and_farm_noise():
    relevant=src('Industrial CMMS maintenance software for asset work orders')
    irrelevant=src('Five farm management software vendors')
    matched, rejected=filter_and_rank('UK industrial maintenance software', [irrelevant,relevant])
    assert relevant in matched
    assert irrelevant not in matched
    assert rejected==1


def test_seed_plan_targets_user_goal():
    plan=choose_research_plan('UK industrial maintenance software', 'five competitors pricing target customers risks', 8)
    assert 'competitor_discovery' in plan
    assert 'pricing_research' in plan
    assert 'customer_review_research' in plan
    assert len(plan)<=8


def test_local_network_url_rejected_without_dns():
    for u in ['http://example.org','https://127.0.0.1/test','https://localhost/admin','file:///etc/passwd','https://example.org:8443']:
        with pytest.raises(ToolUnavailable):
            _safe_public_url(u)


def test_webpage_reader_extracts_text_from_mocked_html(monkeypatch):
    import research_tools as rt
    monkeypatch.setattr(rt, '_safe_public_url', lambda url:url)
    class Fake:
        headers={'Content-Type':'text/html'}
        is_redirect=False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,chunk_size):
            yield b'<html><title>Example CMMS</title><main><h1>Predictive maintenance</h1><p>' + b'Equipment and maintenance software for UK factories. '*3 + b'</p><script>ignore this</script></main></html>'
    monkeypatch.setattr(rt,'_request', lambda *a, **kw:Fake())
    result=webpage_reader('https://example.com')
    assert 'Equipment and maintenance' in result[0].description
    assert 'ignore this' not in result[0].description
    assert result[0].provider.startswith('Web page')


def test_sensitive_tools_do_not_use_shell_or_modify_files():
    import inspect, research_tools
    code=inspect.getsource(research_tools)
    assert 'subprocess.' not in code
    assert 'os.system(' not in code
    assert 'requests.post(' not in code


def test_public_web_rss_parsing(monkeypatch):
    import research_tools as rt
    class Fake:
        content=b'<rss><channel><item><title>UK CMMS supplier</title><link>https://example.org/a</link><description>Industrial maintenance application</description><pubDate>2026</pubDate></item></channel></rss>'
    monkeypatch.setattr(rt, '_request', lambda *a, **kw: Fake())
    results=rt.web_search('maintenance management software')
    assert len(results)==1
    assert results[0].url == 'https://example.org/a'
    assert results[0].provider == 'Web search — RSS preview'


def test_fallback_html_search_when_rss_unavailable(monkeypatch):
    import research_tools as rt
    def broken_rss(*args, **kw):
        raise rt.ToolUnavailable('RSS blocked')
    monkeypatch.setattr(rt, '_rss_search', broken_rss)
    class Fake:
        text='<div class="result"><a class="result__a" href="https://example.org/supplier">CMMS manufacturer</a><div class="result__snippet">Industrial maintenance software for UK</div></div>'
    monkeypatch.setattr(rt, '_request', lambda *a, **kw: Fake())
    results=rt.web_search('CMMS')
    assert results[0].url == 'https://example.org/supplier'
    assert 'HTML preview' in results[0].provider


def test_source_verification_wont_claim_independent_confirmation(monkeypatch):
    import research_tools as rt
    monkeypatch.setattr(rt, 'webpage_reader', lambda *a, **kw: [src('Original page text about CMMS')])
    result=rt.source_verification('https://example.com/report')
    assert 'NOT established' in result[0].description
    with pytest.raises(rt.ToolUnavailable):
        rt.source_verification('CMMS maintenance pricing')


def test_direct_page_fails_closed_on_redirect_and_binary(monkeypatch):
    import research_tools as rt
    monkeypatch.setattr(rt,'_safe_public_url',lambda x:x)
    class Fake:
        headers={'Content-Type':'application/pdf'}
        is_redirect=False
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(rt,'_request', lambda *a, **kw: Fake())
    with pytest.raises(rt.ToolUnavailable, match='text page'):
        rt.webpage_reader('https://example.org/report.pdf')
    class Redirect(Fake):
        is_redirect=True
    monkeypatch.setattr(rt,'_request', lambda *a, **kw: Redirect())
    with pytest.raises(rt.ToolUnavailable, match='Redirect'):
        rt.webpage_reader('https://example.org/redirect')
