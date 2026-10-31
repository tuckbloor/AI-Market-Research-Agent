"""AI Market Research Agent — responsive Streamlit interface."""
from __future__ import annotations

import json
from dataclasses import asdict

import streamlit as st

from ollama_client import OllamaError, installed_models
from research_engine import Settings, start_job
from research_tools import SPECS

st.set_page_config(page_title="AI Market Research Agent", page_icon="📈", layout="wide")

st.markdown("""
<style>
/* Unmistakably interactive form controls; do not style genuinely disabled inputs. */
div[data-testid="stTextInput"] input:not(:disabled),
div[data-testid="stTextArea"] textarea:not(:disabled) {
    background: #fff !important;
    color: #122438 !important;
    -webkit-text-fill-color: #122438 !important;
    caret-color: #087f75 !important;
    border: 2px solid #0d9488 !important;
    border-radius: 12px !important;
    opacity: 1 !important;
    font-size: 1.05rem !important;
}
div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stTextArea"] textarea::placeholder {
    color: #637487 !important; opacity: 1 !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    outline: 3px solid rgba(13,148,136,.25) !important;
    border-color: #0f766e !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #122438 !important;
    border: 2px solid #0d9488 !important;
    border-radius: 12px !important;
}
div[data-testid="stTextArea"] textarea:not(:disabled) {min-height: 136px;}
</style>
""", unsafe_allow_html=True)

DEFAULT_OBJECTIVE = (
    "Identify the market landscape, leading competitors, recent developments, customer needs, "
    "potential opportunities and risks. Cite public source links, distinguish evidence "
    "from assumptions and identify questions worth investigating next."
)


@st.cache_data(ttl=30, show_spinner=False)
def get_models():
    return installed_models()


st.title("📈 AI Market Research Agent")
st.write("Investigate a market, company or product using public sources and your local **Ollama** model. "
         "See every step, long-running request status, source links and agent metrics.")
st.caption("20 read-only research tools available. Web/news results are leads until the source is directly inspected; provider availability varies.")

with st.sidebar:
    st.subheader("How to use this app")
    st.markdown("**1.** Enter the market or company.\n\n**2.** Describe what you need to know.\n\n"
                "**3.** Select your installed Ollama model and limits.\n\n"
                "**4.** Start research. Watch agent decisions, activity and metrics.")
    st.divider()
    st.info("Your research stays in this browser session. No search history database; no file uploads or modifications.")
    st.caption("Public research requires internet. Ollama runs locally when enabled.")
    st.caption("Companies House API needs a free key; Google Trends requires an optional client. Missing services are reported, never fabricated.")

current_job = st.session_state.get("market_job")
running = current_job is not None and current_job.snapshot()["status"] == "running"

st.subheader("1 · What are you researching?")
st.write("**Enter the specific business, industry, product or market.** This is the subject the agent will search for.")
subject = st.text_input("Market, company or product", placeholder="e.g. UK industrial maintenance software",
                        key="market_subject", disabled=running)

st.subheader("2 · What should the agent find out?")
st.write("**Explain the questions you want answered.** Mention competitors, recent news, target customers, opportunities or risks.")
if "market_objective" not in st.session_state:
    st.session_state["market_objective"] = DEFAULT_OBJECTIVE
objective = st.text_area("Research objective — type or replace this text", key="market_objective",
                         height=145, disabled=running,
                         placeholder="e.g. Compare the UK competitors and identify underserved customers...")
st.caption("Example: 'Compare five UK competitors, recent sector changes and gaps for a new software product.'")

st.subheader("3 · Ollama model and research limits")
st.write("**Choose from models installed on your PC.** No model name needs to be typed.")
cols = st.columns([4, 1])
with cols[0]:
    use_ai = st.checkbox("Use Ollama to make research decisions and write the briefing", value=True, disabled=running)
with cols[1]:
    if st.button("↻ Refresh models", disabled=running, use_container_width=True):
        get_models.clear()
        st.rerun()

models = []
model_error = ""
if use_ai:
    try:
        models = get_models()
    except OllamaError as exc:
        model_error = str(exc)
if use_ai and model_error:
    st.warning(model_error + " Source-only research will still work.")
if use_ai and not models and not model_error:
    st.warning("No local models found. Try `ollama pull llama3.2:3b` and click Refresh models.")
model = st.selectbox("Installed Ollama model", options=models,
                     index=0 if models else None,
                     placeholder="No installed Ollama model available",
                     disabled=running or not use_ai or not models)

if use_ai and models:
    st.success(f"Ollama connected · {len(models)} local model(s) available")
    autonomous = st.checkbox("Autonomous tool selection — Ollama chooses which sources to search", value=True,
                             disabled=running, help="Ollama can choose from bounded read-only tools after the fast source plan. Tool-choice calls have a 28-second cap so small models cannot stall for minutes.")
else:
    autonomous = False
    st.info("Without Ollama, the app collects public source links and you can still export them.")

with st.expander("⏱ Long research queries and timeouts", expanded=False):
    st.write("**Long requests are supported.** Set the maximum time the agent may run, the timeout "
             "for each public source, and how long Ollama may be silent before reporting a timeout.")
    max_runtime = st.number_input("Overall research timeout (seconds)", min_value=60, max_value=3600,
                                  value=900, step=60, disabled=running,
                                  help="Hard user-visible limit. When reached, research stops displaying as active; current network requests may finish in the background.")
    source_timeout = st.number_input("Public source timeout, per request (seconds)", min_value=5, max_value=120,
                                     value=25, step=5, disabled=running)
    model_timeout = st.number_input("Ollama briefing response idle timeout (seconds)", min_value=30, max_value=900,
                                    value=300, step=30, disabled=running)
    tool_budget = st.slider("Maximum research tools to run", min_value=2, max_value=15,
                            value=8, disabled=running, help="The agent runs a targeted research plan first; Ollama may add up to two more tool choices.")

with st.expander("🧰 View all 20 research tools and requirements", expanded=False):
    st.write("The agent selects relevant tools; it doesn't run all 20 for every question. Some tools are specialised discovery searches rather than direct primary-data APIs.")
    for tool in SPECS:
        st.write(f"**{tool.name}** — {tool.description}" + (" · *requires Companies House API key*" if tool.requires_key else ""))
    st.caption("Optional Google Trends: install pytrends into .venv if you want the search-interest tool. Public search feeds can sometimes block automated requests.")

st.write("**Start when ready.** Below you'll see what the agent is doing, plus how long the investigation has taken.")
start = st.button("🔎 Start market research", type="primary", use_container_width=True, disabled=running)
if start:
    if not subject.strip():
        st.error("Please enter a research subject in Section 1.")
    elif not objective.strip():
        st.error("Please enter a research objective in Section 2.")
    else:
        settings = Settings(
            model=model or "", use_ai=bool(use_ai and model), autonomous=bool(autonomous),
            max_tools=int(tool_budget), source_timeout=int(source_timeout),
            model_timeout=int(model_timeout), total_timeout=int(max_runtime),
        )
        try:
            st.session_state["market_job"] = start_job(subject, objective, settings)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

st.divider()


@st.fragment(run_every="1s")
def show_research():
    job = st.session_state.get("market_job")
    if job is None:
        st.info("Ready to research. Enter your details above and click **Start market research**.")
        return
    snap = job.snapshot()
    st.subheader("4 · Live agent activity and metrics")
    st.write(f"**Current stage:** {snap['stage']}")
    st.progress(snap["progress"] / 100, text=f"{snap['progress']}% · {snap['status'].replace('_', ' ').title()}")
    a, b, c, d = st.columns(4)
    a.metric("Elapsed", f"{snap['elapsed']:.0f}s")
    b.metric("Source leads", len(snap["sources"]))
    c.metric("Search tool calls", snap["tool_calls"])
    d.metric("Ollama calls", snap["model_calls"])
    e, f, g, h = st.columns(4)
    e.metric("Agent decisions", snap["agent_choices"])
    f.metric("Output chunks", snap["streamed_chunks"])
    g.metric("Output tokens", snap["output_tokens"] if snap["output_tokens"] is not None else "—")
    h.metric("Tokens / sec", snap["output_speed"] if snap["output_speed"] is not None else "—")
    if snap["status"] == "running":
        remaining = max(0, snap["max_seconds"] - snap["elapsed"])
        st.info(f"Research is active · {remaining:.0f}s remaining before the overall limit. "
                "Large local models can take time to load or generate their first words.")
        if st.button("⛔ Cancel research", key="cancel_market_run", type="secondary"):
            job.request_cancel()
            st.rerun(scope="fragment")
    elif snap["status"] == "complete":
        st.success(snap["stage"])
    elif snap["status"] in ("timed_out", "cancelled"):
        st.warning(snap["stage"] + " Partial source results may be available below.")
    else:
        st.error(snap["stage"])
    if snap["was_fallback"]:
        st.caption("The agent used the fast research plan when Ollama tool selection was unavailable or repeated.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Successful tools", snap.get("successful_tools", 0))
    m2.metric("Failed / unavailable", snap.get("failed_tools", 0))
    m3.metric("Off-topic filtered", snap.get("rejected_leads", 0))
    m4.metric("Distinct tool types", len(snap.get("provider_counts", {})))
    o1, o2, o3 = st.columns(3)
    o1.metric("Original pages / official records inspected", snap.get("original_pages_read", 0))
    o2.metric("Search previews upgraded to full pages", snap.get("upgraded_sources", 0))
    o3.metric("Original-page attempts / blocked", f"{snap.get('original_page_attempts', 0)} / {snap.get('original_page_failures', 0)}")
    if snap["status"] == "complete" and len(snap["sources"]) < 4:
        st.warning("Evidence is insufficient for a comprehensive market briefing. "
                   "The report below lists actual leads and what still needs checking.")
    elif snap["status"] == "complete" and snap.get("original_pages_read", 0) == 0:
        st.warning("No original pages could be inspected. Treat findings as research leads, "
                   "not verified claims. Check links before relying on the report.")
    with st.expander("📊 Tool performance and research coverage", expanded=False):
        for item in snap.get("tool_timings", []):
            st.write(f"{item['tool']} · {item['seconds']:.1f}s")
        st.caption("Counts describe activity, not whether an external claim is verified. All research tools are read-only.")
    if snap["errors"]:
        for message in snap["errors"]:
            st.warning(message)
    with st.expander("🔧 What is the agent doing? — full activity log", expanded=snap["status"] == "running"):
        for message in snap["messages"][-40:]:
            st.text(message)
    if snap["briefing"].strip():
        st.subheader("Research results and evidence status")
        if snap["status"] == "running":
            st.caption("Live generation — the model has not finished yet.")
        elif snap["status"] != "complete":
            st.warning("This is incomplete AI text because the run did not finish. Do not use it as a final report.")
        st.markdown(snap["briefing"] + (" ▌" if snap["status"] == "running" else ""))
        if snap["status"] == "complete":
            st.download_button("⬇ Download briefing (.md)", snap["briefing"],
                               file_name="market-research-briefing.md", mime="text/markdown")
    if snap["sources"]:
        st.subheader("Public sources — open and verify the original pages")
        st.caption("Search previews and headlines are unverified leads. Records marked directly read or official API carry stronger provenance, but should still be checked.")
        for item in snap["sources"]:
            with st.expander(f"{item.provider} · {item.title}"):
                st.write(item.description or "No description available.")
                if item.published:
                    st.caption(f"Date from source: {item.published}")
                st.link_button("🔗 Open original source", item.url)
        st.download_button("⬇ Export source list (.json)",
                           json.dumps([asdict(s) for s in snap["sources"]], indent=2, ensure_ascii=False),
                           file_name="market-research-sources.json", mime="application/json")


show_research()
