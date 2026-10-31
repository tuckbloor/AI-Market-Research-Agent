# AI Market Research Agent

**A local, tool-using AI agent for researching companies, industries, products and market opportunities.** Built with **Python**, **Streamlit** and **Ollama**, with **20 read-only research tools**, original-source inspection, live activity, configurable timeouts and downloadable research reports.

> **Public beta / research assistant.** This is not a certified market intelligence or financial due-diligence platform. Search results, company websites and AI-generated conclusions must be independently checked before making commercial decisions.

## At a glance

| Capability | What you get |
| --- | --- |
| AI research | Optional local Ollama model for selecting further tools and drafting the report |
| Research coverage | 20 allowlisted, read-only research handlers |
| Sources | Web and news discovery, company websites, official UK company records where configured |
| Evidence | Distinguishes search-result leads from pages actually retrieved and read |
| Interface | Guided market and research-objective inputs, installed-model dropdown, clear progress and activity log |
| Controls | Cancel, adjustable timeouts and tool-call budget |
| Metrics | Elapsed time, sources, tools, failures, original pages read, model calls, token output where available |
| Exports | Markdown research briefing and JSON source list |
| Installation | Windows launcher automatically creates a project-local `.venv` and installs dependencies |

**What makes this an agent?** It can use Ollama to choose additional investigations from a restricted set of tools, act on the tool results, and produce a source-referenced report. It begins with a quick, objective-based research plan so a slow local model does not prevent initial research. If model tool selection fails, the application can use a bounded fallback plan. This is **bounded autonomy**, not unrestricted web browsing or computer control.

---

## 1. Requirements

### Required

- **Windows 10 or Windows 11**, with PowerShell or Command Prompt.
- **Python 3** installed. Python **3.14** is preferred by the Windows launcher; the scripts can also try another installed Python 3 interpreter.
- **Internet access** to install dependencies on first launch and to access public research sources.
- A browser for the Streamlit interface.

### Optional — Ollama AI mode

- [Ollama](https://ollama.com/) installed and running locally.
- At least one locally downloaded Ollama model. The application reads the installed model list automatically; you do **not** need to type model names.
- Enough system RAM/CPU/GPU capacity for your chosen model. Local generation can be slow on CPU-only systems.

**Without Ollama:** the app still collects public research sources and can export the source list, but AI-directed tool choices and AI-written briefings are unavailable.

### Optional integrations

- **Companies House API key** for the official UK company-register tool.
- **`pytrends`** for Google Trends, which uses an unofficial interface and may be blocked by Google.

No paid commercial research subscription is bundled.

---

## 2. Install on Windows — first time

### Step 1 — Place the files in your project folder

Extract the downloaded Project 03 ZIP **into `E:\`**. It should create:

```text
E:\
└── 03-market-research\
    ├── app.py
    ├── research_engine.py
    ├── research_tools.py
    ├── researcher.py
    ├── ollama_client.py
    ├── research_progress.py
    ├── START-HERE.bat
    ├── ensure-env.bat
    ├── run-app.bat
    ├── run-tests.bat
    ├── setup.bat
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── requirements-optional.txt
    ├── README.md
    ├── sample-data\
    └── tests\
```

The folder must be `E:\03-market-research`, **not** `E:\03-market-research\03-market-research`. If you use another drive, substitute your actual project path in the examples below.

### Step 2 — Check Python

Open **PowerShell** and run:

```powershell
py -3.14 --version
```

If you have a different Python 3 version, check it with:

```powershell
py -3 --version
```

The launcher can use another installed Python 3 when `py -3.14` is unavailable. If none of these commands work, install Python from [python.org](https://www.python.org/downloads/windows/) and enable the Windows Python launcher. Reopen PowerShell after installation.

### Step 3 — Start the application (automatic setup)

**Easiest:** double-click `START-HERE.bat` inside `E:\03-market-research`.

**Or run these commands in PowerShell:**

```powershell
cd E:\03-market-research
.\run-app.bat
```

On first launch, the startup scripts:

1. Look for `.venv\Scripts\python.exe`.
2. Create `.venv` automatically if it does not exist.
3. Install missing Python packages from `requirements.txt`.
4. Start the Streamlit application.

**You do not need to run `setup.bat` beforehand.** The first run needs internet access to install the packages; subsequent launches reuse the existing virtual environment if the required packages are present.

The terminal should display a local Streamlit address. Open **<http://localhost:8501>** if the browser does not launch automatically. Keep the terminal window open while using the application.

### Step 4 — Run the automated tests

From a separate PowerShell window, or after stopping the app:

```powershell
cd E:\03-market-research
.\run-tests.bat
```

The test script creates `.venv` if needed, installs development dependencies including `pytest`, then runs the tests. It will display **passed/failed** results in the terminal. These automated tests use simulated network/model responses for many scenarios; they do not guarantee a particular website or Ollama model will be accessible on your computer.

### Step 5 — Stop and restart

Press **Ctrl+C** in the terminal running Streamlit. Restart with:

```powershell
cd E:\03-market-research
.\run-app.bat
```

You normally do **not** need to repeat setup.

---

## 3. Set up Ollama (optional but recommended)

1. Download/install [Ollama](https://ollama.com/).
2. Start Ollama on your PC. The application expects the default local Ollama endpoint at `http://127.0.0.1:11434`.
3. Open PowerShell and see which models are available:

   ```powershell
   ollama list
   ```

4. If you do not already have a suitable model, you can try:

   ```powershell
   ollama pull llama3.2:3b
   ```

5. Start Project 03, select **Use Ollama to make research decisions and write the briefing**, then choose a model from **Installed Ollama model**.
6. Click **Refresh models** if you have installed a model while the app is already running.

**Model guidance:** Models vary greatly in speed and instruction-following ability. A smaller model may answer more quickly but may struggle with complex tool choices and citation requirements; a larger model can require significantly more memory and time. The app's fast research plan and short model-planning timeout reduce the impact of slow tool decisions, but the final briefing may still take several minutes on a CPU.

**To research without Ollama:** uncheck **Use Ollama to make research decisions and write the briefing**. The app will collect and show available public sources without generating an AI briefing.

---

## 4. User guide — your first market research run

The main screen has four numbered sections. You do not need to upload documents or enter file paths: this application researches **public online sources**.

### Section 1 — What are you researching?

Enter a focused topic in **Market, company or product**.

Good examples:

- `UK Computerised Maintenance Management Software (CMMS)`
- `UK industrial maintenance software for manufacturers`
- `UK SaaS accounting software for small businesses`
- `UK garden equipment retail market`

A broad subject such as `UK SaaS software` spans many unrelated sectors. A specific market usually gives more relevant competitors and more useful opportunities.

### Section 2 — What should the agent find out?

Enter your instructions in **Research objective — type or replace this text**. You can overwrite the example/default objective.

**Recommended copy-and-paste test:**

**Market:**

```text
UK Computerised Maintenance Management Software (CMMS)
```

**Research objective:**

```text
Research the UK CMMS market for manufacturing businesses.
Identify up to five credible competitors and inspect their official
websites where accessible. Compare their products, typical customers,
maintenance features and publicly advertised pricing. Investigate
relevant developments during 2025 and 2026. Recommend three realistic
opportunities for a new entrant, identify risks, and distinguish
verified website evidence from assumptions. Provide source links and
explain any important evidence gaps.
```

The agent may not find five supported competitors or published pricing for every market. **It should report gaps rather than invent data.**

### Section 3 — Ollama model and research limits

1. Tick **Use Ollama to make research decisions and write the briefing** if you want AI output.
2. Pick a model from **Installed Ollama model**.
3. Keep **Autonomous tool selection** enabled if you want the model to choose further research actions when possible.
4. Open **Long research queries and timeouts** if you want to adjust the limits.
5. Expand **View all 20 research tools and requirements** to see the tool descriptions and optional integration requirements.

**Suggested starting settings:**

| Setting in the app | Default | What it means |
| --- | ---: | --- |
| Overall research timeout | **900 seconds (15 min)** | Maximum user-visible research window, adjustable from 60 to 3,600 seconds |
| Public source timeout, per request | **25 seconds** | Per web request, adjustable from 5 to 120 seconds |
| Ollama briefing response idle timeout | **300 seconds** | Maximum wait while the model sends no new response data, adjustable from 30 to 900 seconds |
| Maximum research tools to run | **8** | Tool-call budget, adjustable from 2 to 15 |

The app may use **fewer than 20 tools** in a single run. Twenty is the number of *available tool types*, not the number that must execute. A separate short model-planning timeout is built in, so a slow Ollama tool decision does not hold up the entire investigation. That short planning limit is distinct from the longer briefing timeout.

### Section 4 — Start research and watch progress

Click **Start market research**.

During the run you will see:

- **One progress bar** and a current stage.
- **Elapsed time** and remaining time before the overall limit.
- **Live activity log** showing the selected research tools, results, errors and fallback decisions.
- **Agent Metrics** including tool calls, source leads, model calls and output statistics.
- **Cancel research** while work is active.

The activity log may say the agent used the **fast research plan**. That is expected when Ollama tool choice is unavailable, repeated or too slow. It does **not** mean all 20 tools were used.

**Important about cancellation/timeouts:** the user interface stops the active research when cancelled or timed out, but an already-running HTTP request or model call can take until its configured timeout to exit. Some partial source data may remain visible.

---

## 5. Understand the report and evidence

Research results may include these sections:

- Market and competitor overview.
- Relevant developments, where dated sources are available.
- Potential customer requirements and purchasing needs.
- Possible business opportunities and risks.
- Evidence gaps and suggested next investigations.
- Source references and links to the original material.

**A source lead is not a verified fact.** A headline or search snippet is only a discovery result. The app attempts to read original public HTTPS pages and separately records which pages were actually inspected. Even a directly read company page can contain marketing claims that need independent confirmation.

### Evidence-first behaviour

The app is designed to reserve part of its research budget for original-page inspection before generating a full briefing. If there are too few relevant sources or too few directly inspected originals, it should give a **clearly labelled preliminary source report** instead of presenting an unsupported competitor analysis as established fact.

A cited source ID means the referenced source record exists. It **does not prove** that every interpretation, price, market-size estimate or competitor ranking is accurate. Open important original links before relying on them.

### Agent Metrics explained

| Metric | Interpretation |
| --- | --- |
| **Elapsed** | Total visible run time |
| **Source leads** | Unique source records collected; includes previews and directly inspected pages |
| **Search tool calls** | Research tool invocations actually made |
| **Ollama calls** | Calls made to the local model (including planning and briefing) |
| **Agent decisions** | Recorded attempts to obtain an Ollama-directed research action |
| **Successful / failed tools** | Tool executions that succeeded or failed; success does not mean a result is relevant |
| **Off-topic filtered** | Leads removed by the local relevance heuristic, which can sometimes be too strict |
| **Distinct tool types** | Number of different research handlers used during this run |
| **Original pages / official records inspected** | Sources whose actual readable page content or official record was retrieved |
| **Original-page attempts / blocked** | Site-reading attempts and those that failed (for example HTTP 403) |
| **Search previews upgraded to full pages** | Preview records replaced by direct source content when possible |
| **Output chunks** | Streaming pieces of the response received from Ollama |
| **Output tokens / tokens per second** | Reported when the Ollama response provides sufficient usage information |

An **HTTP 403 Forbidden** from a company website means that site rejected the automated request. It does not necessarily indicate an application bug. The website should be listed as blocked/unavailable, not treated as inspected evidence.

### Export your results

At the bottom of a completed run, use:

- **Download briefing (.md)** for the report in Markdown.
- **Export source list (.json)** for structured source records and links.

The application does **not** maintain a persistent research-history database. Download anything you want to keep before closing the browser session.

---

## 6. All 20 available research tools

The tools are **read-only** and restricted to supported public research actions. Many specialised tools discover candidates using targeted public search queries; they do not represent 20 independent commercial APIs.

| # | Tool | Purpose | Important limitation |
| ---: | --- | --- | --- |
| 1 | `wikipedia_search` | Company and industry background | Encyclopaedia coverage varies |
| 2 | `news_search` | Google News RSS articles and dates | Headline and snippet are leads only |
| 3 | `web_search` | General public web searching | Search providers may rate-limit or change behaviour |
| 4 | `webpage_reader` | Fetch and extract readable text from a public HTTPS page | Sites may block automated access |
| 5 | `company_website_research` | Locate official company sites and inspect a supplied URL | A company homepage does not prove market share |
| 6 | `competitor_discovery` | Find likely vendors and competing products | Candidate names need confirmation |
| 7 | `competitor_comparison` | Discover product comparisons and alternatives | Comparisons may be biased or outdated |
| 8 | `product_research` | Search for publicly described product features | Features should be checked on official pages |
| 9 | `pricing_research` | Discover advertised pricing and subscription plans | Prices may be regional, dated or hidden |
| 10 | `companies_house` | UK official company-register searches | **Requires an API key** |
| 11 | `financial_research` | Discover accounts and public financial disclosures | Not all private companies disclose detailed figures |
| 12 | `market_size_research` | Find market estimates and published statistics | Methodology and geographic scope must be checked |
| 13 | `google_trends` | Relative search-interest data | **Optional `pytrends`; unofficial and may be blocked** |
| 14 | `customer_review_research` | Locate public customer feedback | Reviews are not representative samples |
| 15 | `social_discussion_research` | Find relevant public discussions | Online sentiment is not market-wide evidence |
| 16 | `job_market_research` | Find public hiring/skills-demand signals | Listings may be duplicated or outdated |
| 17 | `government_data_research` | Find ONS and GOV.UK statistics | Some results are discovery leads, not direct APIs |
| 18 | `tender_research` | Find public procurement opportunities | Tender status and closing dates can change |
| 19 | `technology_research` | Search product, AI and industry technology updates | Confirm announcements at their original source |
| 20 | `source_verification` | Read original public pages to inspect supporting material | Reading a page is not independent factual verification |

---

## 7. Optional data-source configuration

### UK Companies House API

The Companies House API provides official UK company-register records, but it requires an API key.

1. Register an application and obtain a key from the [Companies House Developer Hub](https://developer.company-information.service.gov.uk/).
2. Open PowerShell.
3. Set the key **only for the current terminal session**, then start the app:

   ```powershell
   cd E:\03-market-research
   $env:COMPANIES_HOUSE_API_KEY = "YOUR_API_KEY_HERE"
   .\run-app.bat
   ```

4. Keep that terminal window open while researching. If you launch the app from a different shell, set the variable there too.

Without the key, the Companies House tool reports that it is unavailable; the rest of the application can still function. **Never commit your real key to GitHub, place it in `app.py`, or include it in screenshots.**

### Optional Google Trends client

After the main app has created `.venv`, run:

```powershell
cd E:\03-market-research
.\.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
```

This installs `pytrends`. It is an unofficial Google Trends integration and may fail when Google changes or restricts the service. Trends numbers represent **relative search interest**, not total searches or market revenue.

---

## 8. Troubleshooting

| Problem | What to do |
| --- | --- |
| **`Python environment missing`** | Use the current `run-app.bat` / `START-HERE.bat` package. These scripts automatically create `.venv`. Check that `ensure-env.bat` is in the same root folder. |
| **`No usable Python installation was found`** | Install Python 3, make sure the Windows launcher works, and retry `py -3 --version`. |
| **Package installation fails** | Verify internet connectivity and Python installation; re-run `run-app.bat` and read the error above `[ERROR]`. |
| **App doesn't open a browser** | Open `http://localhost:8501` manually and keep the terminal running. If that port is already taken, use the URL printed by Streamlit. |
| **Ollama not connected** | Start Ollama; check `ollama list`; verify it is reachable at `http://127.0.0.1:11434`; then click **Refresh models**. |
| **Model list empty** | Download a model with `ollama pull llama3.2:3b` and refresh the dropdown. |
| **Model takes a long time** | Select a smaller installed model, allow a longer briefing idle timeout and overall timeout, or disable AI for source-only searching. |
| **Ollama cannot select a tool** | The app uses a fast source plan and bounded fallback; watch the activity log. This is different from briefing generation failing. |
| **Original websites return HTTP 403** | The site blocks automated requests. Check the supplied link manually; a different public source may be needed. |
| **Too many off-topic results** | Make the market more specific, such as `UK CMMS software for manufacturers`, and clarify the objective. |
| **Only a preliminary report appears** | Too few relevant original pages were accessible. Review source links and try a narrower subject; the app should not invent unverified findings. |
| **Companies House unavailable** | Set `COMPANIES_HOUSE_API_KEY` before launching the application. |
| **Google Trends unavailable** | Install `requirements-optional.txt`; the external service may still block requests. |
| **Tests don't start** | Run `run-tests.bat`; it installs its own missing test packages. Review any failing test output. |
| **A research run appears frozen** | Check the live stage and elapsed timer, adjust timeouts, or use **Cancel research**. Network/model calls may take until their timeout to exit. |

### Manual setup (only if the automatic launcher fails)

```powershell
cd E:\03-market-research
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If you have Python 3.14 installed and want to force it, substitute `py -3.14` for `py -3`.

> **PowerShell tip:** You do not have to activate `.venv` to run this app. Using `.\.venv\Scripts\python.exe` directly avoids PowerShell execution-policy problems.

---

## 9. Project structure

```text
03-market-research/
├── app.py                   # Streamlit interface, controls, activity and metrics
├── research_engine.py       # Research planning, limits, background run and evidence handling
├── research_tools.py        # 20 read-only research tool handlers
├── researcher.py            # Source records, news/Wikipedia support and briefing context
├── ollama_client.py         # Local model list, tool choices and streaming output
├── research_progress.py     # Research progress helpers
├── requirements.txt         # Main Python packages
├── requirements-dev.txt     # Test packages
├── requirements-optional.txt # Optional Google Trends integration
├── START-HERE.bat           # One-click Windows launcher
├── ensure-env.bat           # Automatic Python environment setup
├── setup.bat                # Optional manual environment setup
├── run-app.bat              # Start application and auto-setup if needed
├── run-tests.bat            # Run tests and auto-setup if needed
├── sample-data/             # Example research subjects
└── tests/                   # Automated tests and provider simulations
```

Main Python dependencies: **Streamlit**, **Requests** and **Beautiful Soup**. Development tests use **pytest**. Dependency version ranges are defined in the respective `requirements*.txt` files.

## 10. Privacy, safety and limitations

- **Local Ollama:** prompts and generated answers are processed by the selected local Ollama model when enabled. Research searches and website requests still go to external public services over the internet.
- **Read-only tools:** the research agent does not run arbitrary shell commands, edit websites or modify local user documents.
- **No persistent research database:** research activity is held in the app's active session. Download reports you wish to keep.
- **Public website access:** some sites block automation, require authentication, use JavaScript-heavy content or contain paywalled material. Those sources may remain inaccessible.
- **Not all tools are independent APIs:** several tools use purpose-specific public searches rather than direct integration with third-party platforms.
- **Evidence limitations:** original pages may contain company marketing statements or dated information. A valid source ID does not establish that a claim is true.
- **Report limitations:** competitor rankings, prices, revenue, market size and opportunities may be incomplete or wrong. Verify critical decisions with original sources and primary research.
- **Bounded operation:** the app enforces tool budgets and timeout limits; an in-flight HTTP/model request may continue briefly after cancellation.

### Contributing and release notes

Contributions, issue reports and improvements are welcome once the repository is published. Check `CHANGELOG.md` for the changes included in the supplied project version. No particular open-source licence is asserted by this README: add a `LICENSE` file to your repository before publishing under a specific licence.

---

**Built for practical research, transparent evidence and learning how real tool-using AI agents work.**
