from researcher import clean_html, evidence_prompt, Source, wikipedia_search, news_search


def test_clean_html():
    assert clean_html('<b>Good</b> &amp; useful') == 'Good & useful'


def test_wikipedia_parsing(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'query': {'search': [{'title': 'Example Business', 'snippet': '<span>Company</span>'}]}}
    monkeypatch.setattr('researcher.requests.get', lambda *args, **kwargs: Response())
    items = wikipedia_search('example')
    assert items[0].url == 'https://en.wikipedia.org/wiki/Example_Business'
    assert items[0].description == 'Company'


def test_news_parsing(monkeypatch):
    class Response:
        content = b'<rss><channel><item><title>Example</title><link>https://news.google.com/a</link><pubDate>Fri, 30 Oct 2026 12:00 GMT</pubDate></item></channel></rss>'
        def raise_for_status(self): pass
    monkeypatch.setattr('researcher.requests.get', lambda *args, **kwargs: Response())
    items = news_search('example')
    assert len(items) == 1
    assert '2026' in items[0].published


def test_prompt_discloses_uncertainty():
    prompt = evidence_prompt('Acme', 'Competitors?', [Source('Article', 'https://example.com', 'Description', 'today', 'News')])
    assert 'Do not invent' in prompt
    assert 'https://example.com' in prompt
