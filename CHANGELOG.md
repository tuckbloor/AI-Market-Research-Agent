# Changelog

## Market Research Agent — evidence and retrieval repair (31 October 2026)

- Fixed broad SaaS relevance handling: synonym matching and search typo expansion; maintained strict CMMS off-topic filtering.
- Removed automatic CMMS/EAM terms from generic SaaS competitor queries.
- Added adaptive follow-up searches when the initial provider results are too thin.
- Fixed source deduplication to upgrade an existing preview when an original page is directly read.
- Added separate metrics for directly inspected pages and upgraded previews.
- Prioritised evidence gathering over optional model planning, with a short 12-second selection cap.
- Added a hard minimum-evidence gate: no comprehensive AI briefing from only one or two RSS headlines.
- Required numbered source references in an AI draft, and withheld a draft that cites none of the supplied sources.
- Added evidence/provenance summaries and more cautious report instructions.
- Kept the original UI layout, model dropdown, white/teal inputs, one progress bar, Cancel, exports and Windows scripts.
- Added offline tests that replay the user's broad SaaS failed-first-run scenario.


## Market Research Agent — 20-tool upgrade (31 October 2026)

- Expanded two provider searches into 20 registered, distinct read-only research handlers.
- Added relevant competitor, product, company, finance, market, tenders, customers and public-source tools.
- Added real Companies House API support (requires a personal API key) and optional Google Trends support.
- Added text extraction from public HTTPS pages with local/private URL rejection, no redirects, limited response size and no local file writes.
- Added public RSS plus HTML search fallback. Automatic source filtering rejects clearly off-topic results and records how many were excluded.
- Changed investigation flow: objective-based research plan starts immediately; Ollama adds optional extra choices with short 25–28-second tool-decision limits. This fixes previous multi-minute tool-selection stalls without removing the longer briefing timeout.
- Added best-effort reading of original source pages and stronger provenance labels.
- Preserved model dropdown, obvious white/teal inputs, help, one progress bar, Cancel, live activity, streamed output and JSON/Markdown export.
- Expanded Agent Metrics with completed/failed tools, rejected leads, tool timings and per-tool source contributions.
- Added offline regression tests for tools, security limits, fallbacks, model timeouts, source relevance and original-page reading.

## Original usability and metrics update (31 October 2026)

- Added local-model selector, Streamlit input guidance, bounded original Wikipedia/Google News tools, research feedback and timeout controls.

## Source-retrieval repair (2026-10-31)

- Preserve calls for original-source inspection *before* Ollama rather than exhausting the budget on search previews.
- Verify public company pages for broad UK SaaS or CMMS searches when search providers return only news redirect URLs. Official URL candidates are not considered evidence unless their page text is fetched.
- Support bounded public HTTPS redirects; retain private-host and binary-download safeguards.
- Display original-page attempts, failures, and provider error details.
- Withhold AI briefing when fewer than two original pages were read, or its citations rely only on headlines.
- Preserve self-installing Windows launcher, 20 tools, and user interface; tests cover successful and blocked primary research.
