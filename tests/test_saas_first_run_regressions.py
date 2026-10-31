"""Regressions reproducing the real 219-second / 37-rejected-leads SaaS report.

All operations mock providers and Ollama: these tests make NO network requests.
"""
from __future__ import annotations

import re

import pytest

from researcher import Source, evidence_prompt
from research_engine import (ResearchJob, Settings, citation_audit, execute,
                             is_directly_inspected, source_search)
from research_tools import (relevance_score, filter_and_rank,
                            focused_queries, competitor_discovery, search_friendly_subject, ToolUnavailable)

SUBJECT = 'UK SAAS software requirments'
OBJECTIVE = ('Identify the market landscape, leading competitors, recent developments, '
             'customer needs, potential opportunities and risks.')


def record(title: str, suffix: str, provider='Web search — RSS preview', desc='') -> Source:
    return Source(title, f'https://example.org/{suffix}', desc, '', provider)


def test_saas_search_does_not_demand_misspelled_requirements():
    results = [
        record('UK software-as-a-service market and providers', 'a'),
        record('Subscription software adoption in British businesses', 'b'),
        record('Cloud software pricing models and CRM', 'c'),
        record('Fleet management hardware update', 'd'),
        record('Farm machinery buying guide', 'e'),
    ]
    retained, rejected = filter_and_rank(SUBJECT, results)
    assert len(retained) == 3
    assert rejected == 2
    assert all(relevance_score(SUBJECT, x) > 0 for x in retained)


def test_specific_cmms_still_excludes_fleet_management_noise():
    results = [record('Construction project management software', 'c'),
               record('UK CMMS maintenance and asset work-order software', 'm')]
    retained, rejected = filter_and_rank('UK industrial maintenance software', results)
    assert [x.url for x in retained] == ['https://example.org/m']
    assert rejected == 1


def test_generic_saas_competitor_tool_no_longer_inserts_cmms_keywords(monkeypatch):
    import research_tools as tools
    requests = []
    def fake_targeted(query, suffix, timeout, limit):
        requests.append(suffix)
        return [record('UK enterprise SaaS competitors', 'competitors')]
    monkeypatch.setattr(tools, '_targeted', fake_targeted)
    competitor_discovery(SUBJECT)
    assert 'SaaS' in requests[0]
    assert 'CMMS' not in requests[0]
    competitor_discovery('UK maintenance software')
    assert 'CMMS' in requests[1]


def test_actual_page_replaces_same_url_preview_and_count_changes():
    preview = record('CMS vendor pricing', 'original', 'Web search — RSS preview', 'short snippet')
    inspected = record('CMS vendor pricing', 'original', 'Original source — directly inspected',
                       'Actual page text with product pricing and disclaimers')
    job = ResearchJob('SaaS', 'comparison', Settings())
    assert job.add_sources([preview]) == 1
    assert job.add_sources([inspected]) == 0  # no duplicate source lead
    snap = job.snapshot()
    assert len(snap['sources']) == 1
    assert snap['original_pages_read'] == 1
    assert snap['upgraded_sources'] == 1
    assert snap['sources'][0].description.startswith('Actual page')


def test_saas_follows_up_when_original_queries_give_two_offtopic_news_leads(monkeypatch):
    calls = []
    def fake_tool(tool, query, timeout=20):
        calls.append((tool, query))
        if 'UK SaaS software as a service providers' in query:
            return [record('UK SaaS provider ' + str(i), 's' + str(i), desc='subscription cloud software')
                    for i in range(6)]
        if tool == 'source_verification':
            return [record('UK SaaS provider 0', 's0', 'Original source — directly inspected',
                           desc='Published primary research about software subscriptions')]
        return [record('Fleet management comparison', 'fleet'+str(len(calls)))]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    job = ResearchJob(SUBJECT, OBJECTIVE, Settings(use_ai=False, max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete'
    assert len(snap['sources']) >= 5, snap['messages']
    assert snap['tool_calls'] <= 8
    assert snap['original_pages_read'] >= 1
    assert any('widening relevant searches' in x for x in snap['messages'])
    assert any('SaaS' in query for _, query in calls)


def test_two_headlines_cannot_generate_unverified_market_facts(monkeypatch):
    calls = []
    def fake_tool(tool, query, timeout=20):
        calls.append(tool)
        if tool == 'source_verification':
            raise ToolUnavailable('Provider blocks original article')
        return [record('SaaS market article '+str(len(calls) % 2), str(len(calls) % 2),
                       'Google News RSS', 'SaaS cloud software headline')]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    monkeypatch.setattr('research_engine.stream_briefing',
                        lambda *a, **kw: pytest.fail('Do not call Ollama on two headlines'))
    job = ResearchJob(SUBJECT, OBJECTIVE, Settings(model='llama3.2:3b',max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete'
    assert 'Evidence is insufficient' in snap['briefing']
    assert 'market-size' in snap['briefing']
    assert snap['model_calls'] == 0


def test_ollama_uncited_competitor_list_withheld(monkeypatch):
    index = [0]
    def fake_tool(tool, query, timeout=20):
        index[0] += 1
        return [record('UK SaaS supplier cloud software '+str(index[0]), 'vendor'+str(index[0]))]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    monkeypatch.setattr('research_engine.choose_tool', lambda *a, **kw: ('finish', ''))
    monkeypatch.setattr('research_engine.stream_briefing',
                        lambda *a, **kw: iter(['Salesforce leads the UK SaaS market. 30% share!']))
    job = ResearchJob(SUBJECT, OBJECTIVE, Settings(model='local',max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete', snap['errors']
    assert 'Salesforce leads' not in snap['briefing']
    assert 'Evidence is insufficient' in snap['briefing']
    assert snap['model_calls'] == 0


def test_source_ids_are_supplied_to_ollama_and_unknown_references_flagged():
    sources = [record('UK SaaS cloud software','a'), record('Cloud SaaS report','b')]
    prompt = evidence_prompt(SUBJECT, OBJECTIVE, sources)
    assert '"id": "S1"' in prompt
    assert '"id": "S2"' in prompt
    assert '[S1]' in prompt
    audit = citation_audit('Statement [S1] other statement [S99].', sources)
    assert 'Unknown source IDs' in audit
    assert '[S99]' in audit
    assert 'Valid source references used: **1**' in audit


def test_valid_citation_keeps_answer_and_exposes_evidence_audit(monkeypatch):
    index = [0]
    def fake_tool(tool, query, timeout=20):
        index[0] += 1
        if tool == 'source_verification':
            return [Source('Company website', query,
                           'Official SaaS company offering verified payroll and accounting applications',
                           '', 'Original source — directly inspected')]
        return [record('UK SaaS company news software '+str(index[0]), 'a'+str(index[0]))]
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    monkeypatch.setattr('research_engine.choose_tool', lambda *a, **kw: ('finish',''))
    monkeypatch.setattr('research_engine.stream_briefing',
                        lambda *a, **kw: iter(['The source describes a SaaS company [S1].']))
    job = ResearchJob(SUBJECT, OBJECTIVE, Settings(model='local', max_tools=8))
    execute(job)
    snap = job.snapshot()
    assert snap['status'] == 'complete'
    assert 'The source describes' in snap['briefing']
    assert 'Evidence and provenance check' in snap['briefing']
    assert 'supplied' in snap['briefing']


def test_fast_model_planning_never_uses_five_minute_tool_timeout(monkeypatch):
    requested = []
    counter = [0]
    def fake_tool(tool, query, timeout=20):
        counter[0] += 1
        if tool == 'source_verification':
            return [Source('Official company page', query, 'Published SaaS products and services',
                           '', 'Original source — directly inspected')]
        return [record('SaaS software business provider '+str(counter[0])+'-'+str(i), str(counter[0])+'-'+str(i)) for i in range(2)]
    def fake_choice(*args, **kwargs):
        requested.append(kwargs['timeout_seconds'])
        return ('finish', '')
    monkeypatch.setattr('research_engine.execute_tool', fake_tool)
    monkeypatch.setattr('research_engine.choose_tool', fake_choice)
    monkeypatch.setattr('research_engine.stream_briefing',
                        lambda *a, **kw: iter(['The result discusses SaaS [S1].']))
    job = ResearchJob(SUBJECT, OBJECTIVE, Settings(model='local', max_tools=8))
    execute(job)
    assert requested == [10]
    assert job.snapshot()['tool_calls'] <= 8


def test_typo_friendly_search_preserves_topic_and_expands_term():
    query = search_friendly_subject(SUBJECT)
    assert 'requirments' not in query
    assert 'requirements' in query
    assert 'software-as-a-service' in query
    assert 'UK' in query


def test_app_reports_primary_page_metrics():
    from pathlib import Path
    app = (Path(__file__).parent.parent / 'app.py').read_text(encoding='utf8')
    assert 'Original pages / official records inspected' in app
    assert 'Search previews upgraded to full pages' in app
    assert 'Research results and evidence status' in app
    assert 'st.selectbox(' in app
    assert 'Cancel research' in app
