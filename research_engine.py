"""Thread-safe bounded market research runner with observable agent metrics.

Only tool definitions implemented here can be selected by Ollama. Research is read-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any
from urllib.parse import urlparse
import re

from ollama_client import OllamaError, ResearchCancelled, choose_tool, stream_briefing
from researcher import Source, evidence_prompt, news_search, wikipedia_search
from research_tools import (TOOLS, execute_tool, filter_and_rank, choose_research_plan,
                            focused_queries, search_friendly_subject, candidate_original_pages, ToolUnavailable)

TERMINAL = {"complete", "error", "cancelled", "timed_out"}


def is_directly_inspected(source: Source) -> bool:
    return ('directly' in source.provider.lower() or 'official api' in source.provider.lower())


def preliminary_report(subject: str, sources: list[Source], reason: str) -> str:
    """Only quote real leads when evidence is too weak for competitor conclusions."""
    lines = [f'# Preliminary research — {subject}', '',
             '**Evidence is insufficient for a reliable market/competitor briefing.**', '',
             reason, '',
             'No market-size estimates, named competitive rankings, prices or forecasts are asserted here.',
             '', '## Retrieved leads (not independently verified)', '']
    for index, item in enumerate(sources[:16], 1):
        lines.extend([f'{index}. [{item.title}]({item.url}) — {item.provider}',
                      f'   - {item.description[:280] or "No source summary available."}'])
    if not sources:
        lines.append('No suitable public sources were retrieved.')
    lines.extend(['', '## Next research needed', '',
                  '- Search a more specific industry/product category or a named company.',
                  '- Inspect original provider and company pages before stating market facts.',
                  '- Check financial figures, prices and competitor claims with dated primary evidence.'])
    return '\n'.join(lines) + '\n'


def citation_audit(text: str, sources: list[Source]) -> str:
    """Display valid source IDs and flag unsourced wording; never claim proof."""
    ids = set(re.findall(r'\[S(\d+)\]', text))
    allowed = {str(i) for i in range(1, min(len(sources), 24) + 1)}
    invalid = sorted(ids - allowed, key=int)
    valid = sorted(ids & allowed, key=int)
    # This check is intentionally procedural, not an automated truth verdict.
    issues = []
    if invalid:
        issues.append('Unknown source IDs: ' + ', '.join(f'[S{i}]' for i in invalid))
    if not valid:
        issues.append('The model did not cite any supplied source IDs.')
    lines = ['\n---', '### Evidence and provenance check',
             f'Valid source references used: **{len(valid)}** / {min(len(sources), 24)} supplied.',
             f'Directly inspected pages or official API records: **{sum(is_directly_inspected(x) for x in sources)}**.',
             'A source ID confirms a retrieved record exists; it does **not** establish that every claim is supported.']
    if issues:
        lines.append('**Check required:** ' + '; '.join(issues))
    if not any(is_directly_inspected(x) for x in sources):
        lines.append('**Lead-only research:** original page contents could not be inspected.')
    lines.append('Cross-check any competitor names, financial figures, prices and dates on original websites.')
    return '\n\n'.join(lines) + '\n'



@dataclass(frozen=True)
class Settings:
    model: str = ""
    use_ai: bool = True
    autonomous: bool = True
    max_tools: int = 8
    source_timeout: int = 20
    model_timeout: int = 180
    total_timeout: int = 600

    def validated(self) -> "Settings":
        if not 5 <= self.source_timeout <= 120:
            raise ValueError("Source timeout must be between 5 and 120 seconds.")
        if not 30 <= self.model_timeout <= 900:
            raise ValueError("Ollama timeout must be between 30 and 900 seconds.")
        if not 60 <= self.total_timeout <= 3600:
            raise ValueError("Overall timeout must be between 60 and 3600 seconds.")
        if not 2 <= self.max_tools <= 15:
            raise ValueError("Tool-call limit must be between 2 and 15.")
        return self


@dataclass
class ResearchJob:
    subject: str
    objective: str
    settings: Settings
    started: float = field(default_factory=monotonic)
    cancel: Event = field(default_factory=Event)
    lock: Lock = field(default_factory=Lock)
    status: str = "running"
    stage: str = "Preparing research"
    progress: int = 3
    sources: list[Source] = field(default_factory=list)
    briefing: str = ""
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    finished: float | None = None
    search_calls: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    streamed_chunks: int = 0
    output_tokens: int | None = None
    input_tokens: int | None = None
    output_speed: float | None = None
    agent_choices: int = 0
    was_fallback: bool = False
    rejected_leads: int = 0
    successful_tools: int = 0
    failed_tools: int = 0
    provider_counts: dict[str, int] = field(default_factory=dict)
    upgraded_sources: int = 0
    original_page_attempts: int = 0
    original_page_failures: int = 0
    tool_timings: list[dict] = field(default_factory=list)
    thread: Thread | None = field(default=None, repr=False)

    def event(self, detail: str, stage: str | None = None, progress: int | None = None):
        with self.lock:
            if self.status in TERMINAL:
                return
            if stage is not None:
                self.stage = stage
            if progress is not None:
                self.progress = max(self.progress, min(99, progress))
            self.messages.append(f"{monotonic() - self.started:5.1f}s · {detail}")
            self.messages = self.messages[-65:]

    def add_sources(self, new: list[Source]):
        """Deduplicate leads, but UPGRADE a preview when its original page is read.

        The earlier version threw away primary-page evidence because the search
        preview had already inserted the URL. Direct evidence must win.
        """
        with self.lock:
            if self.status in TERMINAL:
                return 0
            by_url = {s.url: i for i, s in enumerate(self.sources)}
            added = 0
            for source in new:
                if not source.url.startswith('https://'):
                    continue
                if source.url in by_url:
                    previous = self.sources[by_url[source.url]]
                    if is_directly_inspected(source) and not is_directly_inspected(previous):
                        self.sources[by_url[source.url]] = source
                        self.upgraded_sources += 1
                    continue
                if len(self.sources) >= 65:
                    break
                by_url[source.url] = len(self.sources)
                self.sources.append(source)
                added += 1
            return added

    def count(self, **fields: int):
        with self.lock:
            if self.status in TERMINAL:
                return
            for name, amount in fields.items():
                setattr(self, name, getattr(self, name) + amount)

    def emit(self, text: str):
        with self.lock:
            if self.status not in TERMINAL:
                self.briefing += text
                self.streamed_chunks += 1

    def stats(self, payload: dict):
        with self.lock:
            if self.status in TERMINAL:
                return
            self.output_tokens = payload.get("eval_count")
            self.input_tokens = payload.get("prompt_eval_count")
            duration = payload.get("eval_duration_ns", payload.get("eval_duration"))
            if duration and self.output_tokens:
                self.output_speed = round(self.output_tokens / (duration / 1_000_000_000), 1)

    def end(self, state: str, detail: str):
        with self.lock:
            if self.status in TERMINAL:
                return
            self.status = state
            self.stage = detail
            self.finished = monotonic()
            self.progress = 100
            self.messages.append(f"{self.finished-self.started:5.1f}s · {detail}")
            if state == "error":
                self.errors.append(detail)
            if state in {"timed_out", "cancelled"}:
                self.cancel.set()

    def request_cancel(self):
        self.cancel.set()
        self.end("cancelled", "Cancellation requested. Pending network operations may take time to close.")

    def enforce_deadline(self):
        with self.lock:
            done = self.status in TERMINAL
        if not done and monotonic() - self.started >= self.settings.total_timeout:
            self.cancel.set()
            self.end("timed_out", "Overall research time limit reached. Partial sources are retained.")

    def check_active(self):
        self.enforce_deadline()
        if self.cancel.is_set():
            raise ResearchCancelled("Cancelled or overall timeout reached")

    def snapshot(self) -> dict[str, Any]:
        self.enforce_deadline()
        with self.lock:
            return {
                "subject": self.subject, "objective": self.objective, "status": self.status,
                "stage": self.stage, "progress": self.progress, "sources": list(self.sources),
                "briefing": self.briefing, "messages": list(self.messages), "errors": list(self.errors),
                "search_calls": self.search_calls, "tool_calls": self.tool_calls,
                "model_calls": self.model_calls, "agent_choices": self.agent_choices,
                "streamed_chunks": self.streamed_chunks, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "output_speed": self.output_speed,
                "was_fallback": self.was_fallback, "rejected_leads": self.rejected_leads,
                "successful_tools": self.successful_tools, "failed_tools": self.failed_tools,
                "provider_counts": dict(self.provider_counts), "tool_timings": list(self.tool_timings),
                "original_pages_read": sum(is_directly_inspected(x) for x in self.sources),
                "upgraded_sources": self.upgraded_sources,
                "original_page_attempts": self.original_page_attempts,
                "original_page_failures": self.original_page_failures,
                "elapsed": round((self.finished or monotonic())-self.started, 1),
                "max_seconds": self.settings.total_timeout,
            }


def source_search(job: ResearchJob, tool: str, query: str) -> None:
    """Execute one bounded real tool, rank relevance and record honest progress."""
    job.check_active()
    if tool not in TOOLS:
        raise ValueError('Unknown read-only research tool')
    started = monotonic()
    job.count(search_calls=1, tool_calls=1)
    if tool in {'webpage_reader', 'source_verification'}:
        job.count(original_page_attempts=1)
    job.event(f'Agent tool: {tool} · {query[:130]}', stage=f'Researching · {TOOLS[tool].description}')
    try:
        items = execute_tool(tool, query, timeout=job.settings.source_timeout)
        job.check_active()
        if tool in {'webpage_reader', 'source_verification', 'companies_house', 'google_trends'}:
            ranked, rejected = items, 0  # direct evidence should not be discarded by title ranking
        else:
            ranked, rejected = filter_and_rank(job.subject, items, 8)
        added = job.add_sources(ranked)
        with job.lock:
            if job.status not in TERMINAL:
                job.rejected_leads += rejected
                job.successful_tools += 1
                job.provider_counts[tool] = job.provider_counts.get(tool, 0) + added
        job.event(f'{tool} completed · {len(items)} leads · {rejected} off-topic filtered · {added} new source(s)')
    except Exception as exc:
        job.check_active()
        job.count(failed_tools=1)
        if tool in {'webpage_reader', 'source_verification'}:
            job.count(original_page_failures=1)
        message = f'{tool}: {type(exc).__name__}: {str(exc)[:220]}'
        with job.lock:
            job.errors.append(message)
        job.event(f'{tool} unavailable / failed: {str(exc)[:135]}. Continuing with other tools.')
    finally:
        with job.lock:
            job.tool_timings.append({'tool': tool, 'seconds': round(monotonic()-started, 2)})
            job.tool_timings = job.tool_timings[-50:]


def execute(job: ResearchJob):
    """Research-first workflow with recovery, source inspection and honesty gates."""
    try:
        job.settings.validated()
        job.event('Research started · building subject-aware tool plan', progress=5)
        search_subject = search_friendly_subject(job.subject)
        if search_subject != job.subject:
            job.event(f'Expanded search terminology: {search_subject}')
        max_calls = job.settings.max_tools
        # Discovery, original-page inspection and recovery are all part of the
        # *same* strict tool budget. Do not consume nearly all calls on headlines.
        primary_reserve = min(3, max(1, max_calls // 3)) if max_calls >= 3 else 0
        initial_limit = min(3, max(1, max_calls - primary_reserve - (1 if max_calls >= 5 else 0)))
        plan = choose_research_plan(job.subject, job.objective, budget=initial_limit)
        job.event('Research plan (initial): ' + ' → '.join(plan))
        completed: set[tuple[str, str]] = set()
        for step, tool in enumerate(plan):
            job.check_active()
            query = search_subject
            if tool == 'news_search':
                query += ' 2025 OR 2026'
            source_search(job, tool, query)
            completed.add((tool, query.casefold()))
            job.event(f'Discovery stage {step+1}/{len(plan)} finished',
                      progress=10 + int(28*(step+1)/len(plan)))

        # Don't ask the model to decide which news feed to use while we still
        # have zero real web-page evidence. First inspect original websites.
        # Include official company homepages as *candidates*, never as evidence
        # unless a request successfully reads actual text from that URL.
        def inspect_pages(max_attempts: int, *, target: int):
            attempts = 0
            candidates = candidate_original_pages(job.subject, job.snapshot()['sources'])
            for url in candidates:
                if attempts >= max_attempts or job.snapshot()['tool_calls'] >= max_calls:
                    break
                if job.snapshot()['original_pages_read'] >= target:
                    break
                job.check_active()
                attempted = {x.split(' · ')[-1] for x in job.snapshot()['messages']
                             if 'Trying original website · ' in x}
                if url in attempted:
                    continue
                attempts += 1
                job.event(f'Trying original website · {url}',
                          stage='Reading original websites', progress=45)
                source_search(job, 'source_verification', url)

        inspect_pages(primary_reserve, target=2 if max_calls >= 7 else 1)

        if (len(job.snapshot()['sources']) < 5 or
                job.snapshot()['original_pages_read'] < 1):
            job.event('Evidence is thin · widening relevant searches before writing',
                      stage='Recovering missing market evidence', progress=52)
            for tool, query in focused_queries(job.subject, job.objective):
                # Reserve a further read if enough overall calls remain.
                if job.snapshot()['tool_calls'] >= max_calls - (1 if max_calls >= 6 else 0):
                    break
                if len(job.snapshot()['sources']) >= 7 and job.snapshot()['original_pages_read'] >= 1:
                    break
                job.check_active()
                if (tool, query.casefold()) in completed:
                    continue
                source_search(job, tool, query)
                completed.add((tool, query.casefold()))
        if job.snapshot()['tool_calls'] < max_calls:
            inspect_pages(max_calls - job.snapshot()['tool_calls'], target=3)

        # Optional model-directed research, only AFTER primary retrieval. A
        # small/slow model must not prevent page reads or exhaust the budget.
        if (job.settings.use_ai and job.settings.autonomous and job.settings.model
                and job.snapshot()['original_pages_read'] >= 2
                and job.snapshot()['tool_calls'] < max_calls
                and job.settings.total_timeout - (monotonic() - job.started) >= 40):
            candidates = [name for name in TOOLS if name not in plan
                          and name not in {'google_trends', 'companies_house',
                                           'webpage_reader', 'source_verification'}]
            if candidates:
                job.count(model_calls=1, agent_choices=1)
                job.event('Optional agent tool choice (up to 10 seconds)',
                          stage='Agent deciding a targeted follow-up', progress=60)
                summary = '; '.join(f'{x.provider}: {x.title}' for x in job.snapshot()['sources'][:7])
                try:
                    tool, query = choose_tool(job.subject, job.objective, summary, job.settings.model,
                                              timeout_seconds=min(10, job.settings.model_timeout),
                                              available_tools=candidates[:12])
                    job.check_active()
                    if tool in TOOLS and (tool, query.casefold()) not in completed:
                        source_search(job, tool, query)
                    else:
                        job.event('Agent chose no new applicable research tool')
                except OllamaError as exc:
                    job.was_fallback = True
                    job.event(f'Optional model planning unavailable; primary sources retained: {str(exc)[:120]}')
        elif job.settings.autonomous and job.settings.use_ai:
            job.was_fallback = True
            job.event('Skipped optional model planning; source reading takes priority')
        elif not job.settings.use_ai:
            job.event('Source-only mode: no Ollama calls')

        job.check_active()
        snapshot = job.snapshot()
        sources = snapshot['sources']
        inspected = snapshot['original_pages_read']
        job.event(f'Evidence collection finished · {len(sources)} leads · {inspected} directly inspected record(s)',
                  stage='Checking research sufficiency', progress=67)
        if len(sources) < 4:
            message = (f'Only {len(sources)} relevant source(s) were found. A confident competitor '
                       'or market-size report would be misleading. Broaden the subject or retry later.')
            job.event('Insufficient evidence for an AI market briefing; supplying honest source-only report')
            job.emit(preliminary_report(job.subject, sources, message))
            job.end('complete', 'Limited evidence · source-only report (not a verified market briefing)')
            return
        if inspected < 2:
            message = (f'Only {inspected} original source page(s) were successfully read '
                       f'from {job.snapshot()["original_page_attempts"]} attempt(s). '
                       'A credible competitor comparison requires multiple independently checked sources. '
                       'See tool errors and the original-source links, then retry with a more specific market.')
            job.event('Original evidence too thin for generated factual market claims')
            job.emit(preliminary_report(job.subject, sources, message))
            job.end('complete', 'Limited original evidence · preliminary sources only')
            return
        if not job.settings.use_ai or not job.settings.model:
            job.emit(preliminary_report(job.subject, sources,
                       'AI briefing was not enabled. Inspect the original public sources.'))
            job.end('complete', 'Relevant public sources collected · no Ollama briefing requested')
            return
        job.check_active()
        job.count(model_calls=1)
        prompt = evidence_prompt(job.subject, job.objective, sources)
        if not inspected:
            job.event('Original pages were not accessible; briefing must label all findings as tentative')
        job.event(f'Sending {min(24, len(sources))} evidence records to {job.settings.model}; waiting for first words',
                  stage='Ollama preparing briefing (evidence-labelled draft)', progress=72)
        quality_header = ('> **Evidence status:** ' +
                          ('Original pages/official records were read. Check each citation and claim.' if inspected
                           else 'Preliminary — search results and headlines only; no original page could be inspected.') +
                          '\n\n')
        job.emit(quality_header)
        for chunk in stream_briefing(prompt, job.settings.model,
                                     read_timeout_seconds=min(job.settings.model_timeout,
                                                              max(10, int(job.settings.total_timeout -
                                                                          (monotonic()-job.started)))),
                                     cancel_event=job.cancel, on_metrics=job.stats):
            job.check_active()
            job.emit(chunk)
            if job.snapshot()['streamed_chunks'] == 2:
                job.event('Ollama is streaming an evidence-labelled research draft',
                          stage='Ollama generating briefing', progress=84)
        job.check_active()
        with job.lock:
            final_report = job.briefing
        valid_ids = {str(i) for i in range(1, min(len(sources), 24) + 1)}
        cited_ids = set(re.findall(r'\[S(\d+)\]', final_report)) & valid_ids
        inspected_ids = {str(i) for i, src in enumerate(sources[:24], 1)
                         if is_directly_inspected(src)}
        if cited_ids and not (cited_ids & inspected_ids):
            job.event('Generated draft cited previews only; withholding an unverified competitor report')
            with job.lock:
                job.briefing = preliminary_report(job.subject, sources,
                    'Ollama cited only search previews. The unsupported draft was withheld; '
                    'direct original-page citations are required for reported competitor facts.')
        elif not cited_ids:
            # Do not deliver an unsupported generated competitor report as if it
            # were researched. The live draft may have streamed, but final output
            # replaces it with a transparent list of actual source links.
            job.event('Ollama supplied no valid source IDs; replacing its unverified text with source-only report')
            with job.lock:
                job.briefing = preliminary_report(job.subject, sources,
                    'Ollama did not cite any valid source IDs. Its unsupported draft was withheld.')
        else:
            job.emit(citation_audit(final_report, sources))
        job.end('complete' , 'Research complete · evidence status and sources available')
    except ResearchCancelled:
        job.end('cancelled', 'Research stopped by user or overall deadline')
    except Exception as exc:
        job.end('error', f'Research could not finish: {type(exc).__name__}: {exc}')


def start_job(subject: str, objective: str, settings: Settings) -> ResearchJob:
    settings.validated()
    if not subject.strip() or not objective.strip():
        raise ValueError("Enter both a research subject and objective.")
    job = ResearchJob(subject.strip(), objective.strip(), settings)
    job.thread = Thread(target=execute, args=(job,), daemon=True, name="market-research-agent")
    job.thread.start()
    return job
