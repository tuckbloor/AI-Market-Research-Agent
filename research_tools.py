"""Twenty bounded, read-only research capabilities with explicit provenance.

Specialised discovery tools use targeted public searches; they do NOT claim to have
scraped prices, financial statements, reviews or market figures until source pages
have actually been read. Providers can change access rules without notice.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from urllib.parse import urlparse, urlencode, urljoin, quote
import ipaddress
import os
import re
import socket
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from researcher import Source, news_search, wikipedia_search, clean_html

USER_AGENT = {"User-Agent": "DocumentedMarketResearchAgent/1.0 (+read-only; public-source research)"}
MAX_HTML = 850_000


class ToolUnavailable(RuntimeError):
    """Specific capability needs credentials, data or an accessible provider."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: str
    requires_key: bool = False


SPECS = (
    ToolSpec('wikipedia_search', 'Encyclopedia and company background', 'Background'),
    ToolSpec('news_search', 'UK Google News RSS headlines and dates', 'News'),
    ToolSpec('web_search', 'General public web search results', 'Web'),
    ToolSpec('webpage_reader', 'Read actual text of a public HTTPS web page', 'Web'),
    ToolSpec('company_website_research', 'Find and read official company pages', 'Companies'),
    ToolSpec('competitor_discovery', 'Discover named competitors and competing products', 'Competitors'),
    ToolSpec('competitor_comparison', 'Find independent competitor comparison material', 'Competitors'),
    ToolSpec('product_research', 'Find product features and specifications', 'Products'),
    ToolSpec('pricing_research', 'Find published pricing and pricing models', 'Pricing'),
    ToolSpec('companies_house', 'Official UK company register search (optional API key)', 'Companies', True),
    ToolSpec('financial_research', 'Public annual accounts and financial disclosures', 'Finance'),
    ToolSpec('market_size_research', 'Industry estimates, scope and dated statistics', 'Market'),
    ToolSpec('google_trends', 'Google search-interest history (optional pytrends access)', 'Market'),
    ToolSpec('customer_review_research', 'Public review and user-feedback discovery', 'Customers'),
    ToolSpec('social_discussion_research', 'Public community and industry conversations', 'Customers'),
    ToolSpec('job_market_research', 'Skills demand and recruitment signals', 'Jobs'),
    ToolSpec('government_data_research', 'UK government and ONS publications', 'Government'),
    ToolSpec('tender_research', 'UK public-sector tenders and contracts', 'Tenders'),
    ToolSpec('technology_research', 'Technology, product releases and industry changes', 'Technology'),
    ToolSpec('source_verification', 'Read independent source pages to cross-check claims', 'Verification'),
)
TOOLS = {t.name: t for t in SPECS}
assert len(TOOLS) == 20


def _request(url: str, *, params: dict | None = None, timeout: int = 20, **kwargs):
    response = requests.get(url, params=params, timeout=(min(5, timeout), max(5, timeout)),
                            headers=USER_AGENT, **kwargs)
    response.raise_for_status()
    return response


def _safe_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ToolUnavailable('Only public HTTPS websites on standard port 443 are allowed.')
    host = parsed.hostname.lower().rstrip('.')
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost', '.test')):
        raise ToolUnavailable('Private/local network addresses cannot be researched.')
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ToolUnavailable(f'Cannot resolve public website: {host}') from exc
    if not infos or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in infos):
        raise ToolUnavailable('Website resolves to a private or reserved address.')
    return url


def webpage_reader(query: str, timeout: int = 20, limit: int = 4) -> list[Source]:
    """Read a public HTTPS HTML page, including bounded validated redirects.

    A 301/302 to another HTTPS hostname is normal for official UK websites.
    Every redirect is independently checked; internal networks and non-HTML
    responses are rejected. No JavaScript or active content is executed.
    """
    url = _safe_public_url(query.strip())
    visited: set[str] = set()
    for _ in range(5):
        if url in visited:
            raise ToolUnavailable('Website contains a redirect loop.')
        visited.add(url)
        with _request(url, timeout=timeout, allow_redirects=False, stream=True) as response:
            if response.is_redirect:
                location = response.headers.get('Location', '').strip()
                if not location:
                    raise ToolUnavailable('Redirect did not specify a destination.')
                url = _safe_public_url(urljoin(url, location))
                continue
            kind = response.headers.get('Content-Type', '').lower()
            if kind and not ('html' in kind or 'text/plain' in kind):
                raise ToolUnavailable(f'Source is not a supported text page ({kind[:60]}).')
            raw = bytearray()
            for part in response.iter_content(chunk_size=32768):
                raw.extend(part)
                if len(raw) > MAX_HTML:
                    raise ToolUnavailable('Page exceeds the bounded text-reading limit.')
        soup = BeautifulSoup(bytes(raw), 'html.parser')
        for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'noscript', 'form', 'aside']):
            tag.decompose()
        title = (soup.title.get_text(' ', strip=True) if soup.title else urlparse(url).hostname) or url
        article = soup.find('main') or soup.find('article') or soup.body or soup
        content = ' '.join(article.stripped_strings)
        content = re.sub(r'\s+', ' ', unescape(content)).strip()
        if len(content) < 120:
            raise ToolUnavailable('The public page contains too little usable text (possibly JavaScript-only).')
        return [Source(title[:170], url, content[:6500], '', 'Web page — directly read')]
    raise ToolUnavailable('Website redirected too many times (limit: 5).')


# Candidate URLs only: these are NOT research evidence, competitor rankings or
# verified company facts. Each is admitted to the report only after reading it.
# They provide a real original-page route when public search services return
# nothing except Google News redirect URLs.
OFFICIAL_STARTING_POINTS = {
    'saas': (
        'https://www.sage.com/en-gb/',
        'https://www.theaccessgroup.com/en-gb/',
        'https://www.iris.co.uk/',
        'https://www.freeagent.com/',
        'https://www.xero.com/uk/',
    ),
    'maintenance': (
        'https://www.emaint.com/',
        'https://www.fiixsoftware.com/',
        'https://www.maintainx.com/',
        'https://www.ifs.com/',
    ),
}


def candidate_original_pages(subject: str, sources: list[Source]) -> list[str]:
    """Order only accessible-looking public URL candidates; never fabricate text.

    Discovery pages from genuine searches take priority. A short collection of
    documented official company homepages is a *last-resort lookup plan*, not a
    list of proven competitors.
    """
    urls: list[str] = []
    banned = ('news.google.', 'bing.com', 'duckduckgo.com', 'reddit.com',
              'trustpilot.com', 'capterra.com', 'g2.com', 'google.com')
    ordered = sorted(sources, key=lambda s: (
        0 if any(x in s.provider.lower() for x in ('company website', 'web search', 'government')) else 1,
        0 if s.url.lower().startswith('https://') else 1,
    ))
    for s in ordered:
        host = (urlparse(s.url).hostname or '').lower()
        if not host or any(host == bad or host.endswith('.'+bad) for bad in banned):
            continue
        if s.url.startswith('https://') and s.url not in urls:
            urls.append(s.url)
    if _is_maintenance_subject(subject):
        urls.extend(x for x in OFFICIAL_STARTING_POINTS['maintenance'] if x not in urls)
    elif _is_saas_subject(subject):
        urls.extend(x for x in OFFICIAL_STARTING_POINTS['saas'] if x not in urls)
    return urls

def _rss_search(query: str, timeout: int = 20, limit: int = 8) -> list[Source]:
    """Bing public RSS endpoint. Availability varies; no fake results on failure."""
    response = _request('https://www.bing.com/search', params={'q': query[:260], 'format': 'rss'}, timeout=timeout)
    root = ET.fromstring(response.content)
    if root.tag.lower().endswith('html'):
        raise ToolUnavailable('Web-search provider returned HTML rather than an RSS feed.')
    found = []
    for item in root.findall('.//item')[:limit]:
        url = item.findtext('link', '').strip()
        if not url.startswith('https://'):
            continue
        found.append(Source(clean_html(item.findtext('title', ''))[:180], url,
                            clean_html(item.findtext('description', ''))[:800],
                            item.findtext('pubDate', ''), 'Web search — RSS preview'))
    if not found:
        raise ToolUnavailable('Web search returned no usable public links.')
    return found


def web_search(query: str, timeout: int = 20, limit: int = 8) -> list[Source]:
    try:
        return _rss_search(query, timeout, limit)
    except (requests.RequestException, ET.ParseError, ToolUnavailable):
        # Some regions block RSS search. An alternative public HTML search is used
        # only to find leads, and all HTML scraping is best-effort.
        response = _request('https://html.duckduckgo.com/html/',
                            params={'q': query[:260]}, timeout=timeout)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = []
        for result in soup.select('.result')[:limit]:
            link = result.select_one('a.result__a')
            if not link:
                continue
            url = link.get('href', '')
            if url.startswith('//'):
                url = 'https:' + url
            if 'uddg=' in url:
                from urllib.parse import parse_qs, unquote
                parsed = parse_qs(urlparse(url).query).get('uddg', [])
                if parsed:
                    url = unquote(parsed[0])
            if not url.startswith('https://'):
                continue
            snippet = result.select_one('.result__snippet')
            items.append(Source(link.get_text(' ', strip=True)[:170], url,
                                snippet.get_text(' ', strip=True)[:800] if snippet else '',
                                '', 'Web search — HTML preview'))
        if not items:
            raise ToolUnavailable('Public web-search providers unavailable or returned no results.')
        return items


def _targeted(query: str, suffix: str, timeout: int, limit: int = 7) -> list[Source]:
    return web_search(f'{query[:150]} {suffix}', timeout, limit)


def company_website_research(query: str, timeout: int = 20, limit: int = 5) -> list[Source]:
    if query.startswith('https://'):
        return webpage_reader(query, timeout)
    candidates = _targeted(query, 'official website company products services', timeout, 5)
    # Results remain clearly labelled as search leads until the agent reads a page.
    return [Source(x.title, x.url, x.description, x.published, 'Company website — discovery lead') for x in candidates]


def competitor_discovery(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    suffix = ('CMMS EAM competitors alternatives vendors providers UK'
              if _is_maintenance_subject(query) else 'SaaS cloud software UK vendors competitors companies alternatives')
    return [Source(x.title, x.url, x.description, x.published, 'Competitor discovery — lead')
            for x in _targeted(query, suffix, timeout, limit)]


def competitor_comparison(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Competitor comparison — lead')
            for x in _targeted(query, 'compare software features independent review alternatives', timeout, limit)]


def product_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Product research — lead')
            for x in _targeted(query, 'products modules capabilities features documentation', timeout, limit)]


def pricing_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Pricing — unverified public lead')
            for x in _targeted(query, 'pricing plans per user month software GBP', timeout, limit)]


def companies_house(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    key = os.getenv('COMPANIES_HOUSE_API_KEY', '').strip()
    if not key:
        raise ToolUnavailable('COMPANIES_HOUSE_API_KEY not set. Get a free key from Companies House Developer Hub.')
    response = _request('https://api.company-information.service.gov.uk/search/companies',
                        params={'q': query[:200], 'items_per_page': min(10, limit)},
                        auth=(key, ''), timeout=timeout)
    out = []
    for item in response.json().get('items', [])[:limit]:
        number = str(item.get('company_number', '')).strip()
        if not re.fullmatch(r'[A-Za-z0-9]{6,9}', number):
            continue
        out.append(Source(item.get('title', 'Company'),
                          f'https://find-and-update.company-information.service.gov.uk/company/{number}',
                          f'Company number {number}; status {item.get("company_status", "unknown")}; '
                          f'created {item.get("date_of_creation", "unknown")}. Registry record, not proof of financial health.',
                          '', 'Companies House — official API'))
    return out


def financial_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Financial filings — discovery lead')
            for x in _targeted(query, 'annual report financial results filed accounts turnover site:gov.uk OR site:companieshouse.gov.uk OR site:investors', timeout, limit)]


def market_size_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Market size — estimate lead')
            for x in _targeted(query, 'market size statistics 2025 2026 methodology revenue UK', timeout, limit)]


def google_trends(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    """Real interest-over-time data, only when optional Google Trends client is usable."""
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise ToolUnavailable('Google Trends needs the optional pytrends package: pip install pytrends') from exc
    phrase = query.strip()[:90]
    if not phrase:
        return []
    client = TrendReq(hl='en-GB', tz=0, requests_args={'timeout': (5, max(5, timeout))})
    client.build_payload([phrase], timeframe='today 12-m', geo='GB')
    frame = client.interest_over_time()
    if frame.empty or phrase not in frame.columns:
        raise ToolUnavailable('Google Trends did not return comparable GB search-interest data.')
    series = frame[phrase]
    last = series.iloc[-1]
    mean = round(float(series.mean()), 1)
    url = 'https://trends.google.com/trends/explore?' + urlencode({'geo': 'GB', 'q': phrase})
    return [Source(f'Google Trends: UK search interest for {phrase}', url,
                   f'12-month relative search interest: latest {int(last)} / 100; period mean {mean} / 100. '
                   'Indexed search interest, not market size or search volume. Dates: '
                   f'{series.index[0].date()} to {series.index[-1].date()}.',
                   str(series.index[-1].date()), 'Google Trends — relative interest')]


def customer_review_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Customer reviews — discovery lead')
            for x in _targeted(query, 'review customer feedback complaints site:capterra.com OR site:g2.com OR site:trustpilot.com', timeout, limit)]


def social_discussion_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Social discussions — unrepresentative lead')
            for x in _targeted(query, 'experience discussion recommendation site:reddit.com OR site:community', timeout, limit)]


def job_market_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Jobs — skills demand lead')
            for x in _targeted(query, 'jobs vacancies hiring engineer implementation consultant UK', timeout, limit)]


def government_data_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Government data — official lead')
            for x in _targeted(query, 'site:ons.gov.uk OR site:gov.uk statistics report dataset', timeout, limit)]


def tender_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'UK tenders — discovery lead')
            for x in _targeted(query, 'site:find-tender.service.gov.uk OR site:contractsfinder.service.gov.uk tender contract', timeout, limit)]


def technology_research(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    return [Source(x.title, x.url, x.description, x.published, 'Technology — discovery lead')
            for x in _targeted(query, 'industrial AI IoT maintenance CMMS technology release 2026', timeout, limit)]


def source_verification(query: str, timeout: int = 20, limit: int = 7) -> list[Source]:
    """Read a supplied original URL; cannot claim independent corroboration from one page."""
    if not query.startswith('https://'):
        raise ToolUnavailable('To verify a source, give an original HTTPS URL from the source list.')
    results = webpage_reader(query, timeout)
    return [Source(x.title, x.url, x.description + '\nOne page was directly read; independent corroboration NOT established.',
                   x.published, 'Original source — directly inspected') for x in results]


HANDLERS = {
    'wikipedia_search': wikipedia_search,
    'news_search': news_search,
    'web_search': web_search,
    'webpage_reader': webpage_reader,
    'company_website_research': company_website_research,
    'competitor_discovery': competitor_discovery,
    'competitor_comparison': competitor_comparison,
    'product_research': product_research,
    'pricing_research': pricing_research,
    'companies_house': companies_house,
    'financial_research': financial_research,
    'market_size_research': market_size_research,
    'google_trends': google_trends,
    'customer_review_research': customer_review_research,
    'social_discussion_research': social_discussion_research,
    'job_market_research': job_market_research,
    'government_data_research': government_data_research,
    'tender_research': tender_research,
    'technology_research': technology_research,
    'source_verification': source_verification,
}
assert set(HANDLERS) == set(TOOLS)


def execute_tool(name: str, query: str, timeout: int = 20) -> list[Source]:
    if name not in HANDLERS:
        raise ValueError(f'Tool {name!r} is not in the read-only tool registry.')
    if not query.strip():
        raise ValueError('Research query cannot be empty.')
    results = HANDLERS[name](query.strip()[:300], timeout=timeout)
    return results[:10]


STOP_WORDS = {'the', 'with', 'from', 'software', 'market', 'research', 'industry',
              'company', 'united', 'kingdom', '2026', '2025', 'uk', 'for', 'and',
              'systems', 'system', 'requirements', 'requirement', 'requirments', 'business'}

SAAS_ALIASES = ('saas', 'software as a service', 'software-as-a-service', 'cloud software',
                'cloud-based software', 'subscription software', 'subscription-based software',
                'enterprise software', 'cloud application', 'business applications')
MAINTENANCE_ALIASES = ('cmms', 'eam', 'maintenance management', 'equipment maintenance',
                       'asset maintenance', 'work order', 'work-order', 'plant maintenance',
                       'predictive maintenance', 'industrial maintenance', 'maintenance software',
                       'enterprise asset management')
TANGENTS = ('fleet management', 'farm management', 'construction management',
            'project management', 'property management')


def _is_maintenance_subject(subject: str) -> bool:
    s = subject.lower()
    return any(x in s for x in ('maintenance', 'cmms', 'enterprise asset management',
                                'plant asset', 'work order', 'eam software'))


def _is_saas_subject(subject: str) -> bool:
    s = subject.lower().replace('s.a.a.s.', 'saas')
    return any(x in s for x in ('saas', 'software as a service', 'software-as-a-service',
                                'cloud software', 'subscription software'))


def relevance_score(subject: str, source: Source) -> int:
    """Domain-aware relevance score; never a claim that the source is factually correct.

    A broad SaaS subject must not require the word 'requirments' in every result.
    Narrow CMMS subjects must still reject unrelated fleet/farm/project software.
    """
    title = source.title.lower()
    content = f'{title} {source.description.lower()}'
    words = {w for w in re.findall(r'[a-z0-9]+', subject.lower())
             if len(w) > 2 and w not in STOP_WORDS}
    if _is_maintenance_subject(subject):
        # 'maintenance' alone in an unrelated field is too weak: need actual
        # software/product context or a specific maintenance-domain synonym.
        has_domain = any(x in content for x in MAINTENANCE_ALIASES)
        if not has_domain:
            return 0
        score = 5 + sum(3 if w in title else 1 for w in words if w in content)
        if any(x in content for x in TANGENTS) and not any(x in content for x in
                ('cmms', 'eam', 'asset maintenance', 'industrial maintenance', 'work order')):
            score -= 6
        return max(0, score)
    if _is_saas_subject(subject):
        aliases = [x for x in SAAS_ALIASES if x in content]
        # Broad software-as-a-service searches match synonyms and product
        # categories; an article about 'cloud software' needn't spell 'SaaS'.
        score = (6 if aliases else 0) + sum(2 if w in title else 1 for w in words if w in content)
        if any(x in content for x in TANGENTS) and not aliases:
            score -= 4
        return max(0, score)
    return sum(3 if w in title else 1 for w in words if w in content)


def filter_and_rank(subject: str, sources: list[Source], max_results: int = 8) -> tuple[list[Source], int]:
    """Discard unrelated leads without excluding common market synonyms."""
    ranked = sorted(sources, key=lambda x: relevance_score(subject, x), reverse=True)
    matched = [x for x in ranked if relevance_score(subject, x) > 0]
    return matched[:max_results], len(sources) - len(matched)


def search_friendly_subject(subject: str) -> str:
    """Repair common user typos and expand SaaS, without changing the requested topic."""
    clean = re.sub(r'\brequirments\b', 'requirements', subject, flags=re.I)
    clean = re.sub(r'\bsaas\b', 'SaaS', clean, flags=re.I)
    if _is_saas_subject(clean) and not re.search(r'software.as.a.service', clean, re.I):
        clean += ' software-as-a-service'
    return clean[:250]


def focused_queries(subject: str, objective: str) -> list[tuple[str, str]]:
    """Related searches for poor evidence coverage, never fabricated sources."""
    if _is_maintenance_subject(subject):
        queries = [
            ('web_search', 'UK CMMS maintenance management software vendors features official'),
            ('company_website_research', 'UK maintenance management software CMMS official products'),
            ('government_data_research', 'UK manufacturing digital maintenance software statistics'),
            ('pricing_research', 'CMMS software UK pricing official per user'),
        ]
    elif _is_saas_subject(subject):
        queries = [
            ('web_search', 'UK SaaS software as a service providers market companies official'),
            ('company_website_research', 'UK software as a service company products official'),
            ('government_data_research', 'UK cloud computing software as a service business adoption ONS'),
            ('web_search', 'UK SaaS software industry research digital economy 2026'),
        ]
    else:
        queries = [
            ('web_search', f'{subject[:100]} companies products official UK'),
            ('company_website_research', f'{subject[:100]} official companies'),
            ('government_data_research', f'{subject[:100]} UK statistics'),
            ('web_search', f'{subject[:100]} sector competitors products'),
        ]
    return queries


def choose_research_plan(subject: str, objective: str, budget: int = 8) -> list[str]:
    """Quick initial discovery. Leave tool calls for recovery and source reading."""
    text = (subject + ' ' + objective).lower()
    picks = ['competitor_discovery', 'web_search', 'news_search']
    rules = [
        (('price', 'pricing', 'cost', 'subscription'), 'pricing_research'),
        (('competitor', 'alternatives', 'rival'), 'competitor_comparison'),
        (('feature', 'product', 'capabilit'), 'product_research'),
        (('market size', 'market share', 'revenue', 'growth'), 'market_size_research'),
        (('company', 'registration', 'director', 'filing'), 'companies_house'),
        (('financial', 'profit', 'turnover'), 'financial_research'),
        (('trend', 'demand'), 'google_trends'),
        (('customer', 'review', 'complaint'), 'customer_review_research'),
        (('social', 'forum', 'discussion'), 'social_discussion_research'),
        (('job', 'hiring', 'recruit'), 'job_market_research'),
        (('ons', 'government', 'official data', 'statistics'), 'government_data_research'),
        (('tender', 'procurement', 'contract'), 'tender_research'),
        (('technology', 'innovation', 'ai', 'digital'), 'technology_research'),
    ]
    for terms, tool in rules:
        if any((re.search(r'\b' + re.escape(term) + r'\b', text) if len(term) <= 3 else term in text)
               for term in terms) and tool not in picks:
            picks.append(tool)
    return picks[:max(1, budget)]
