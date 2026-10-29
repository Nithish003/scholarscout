"""
ScholarScout — Streamlit UI.

Run locally:
    export NEBIUS_API_KEY="..."          # your Nebius Token Factory key
    export TAVILY_API_KEY="..."          # optional, enables live search
    export NEBIUS_MODEL="nvidia/..."     # an NVIDIA Nemotron model id
    streamlit run app.py

This is the hosted demo you submit to the hackathon.
"""

import os
import streamlit as st

# On Streamlit Community Cloud, secrets live in st.secrets (not os.environ).
# Bridge them into the environment BEFORE importing the engine, which reads
# os.environ. Locally (no secrets file) this is a harmless no-op.
try:
    for _k in ("NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL", "TAVILY_API_KEY"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass  # no secrets.toml locally — rely on real environment variables

import scholarscout as ss

st.set_page_config(page_title="ScholarScout", page_icon="🔭", layout="centered")

st.title("🔭 ScholarScout")
st.caption(
    "Autonomous research-opportunity agent — powered by **NVIDIA Nemotron** on "
    "**Nebius Token Factory**, with live search by **Tavily**."
)

with st.sidebar:
    st.header("Setup")
    st.markdown(
        "Keys are read from the environment:\n"
        "- `NEBIUS_API_KEY` (required)\n"
        "- `TAVILY_API_KEY` (optional, enables live search)\n"
        "- `NEBIUS_MODEL` (an NVIDIA Nemotron id)"
    )
    st.write("**Model:**", f"`{ss.NEBIUS_MODEL}`")
    st.write("**Nebius key:**", "✅ set" if os.environ.get("NEBIUS_API_KEY") else "❌ missing")
    st.write("**Tavily key:**", "✅ set (live search)" if os.environ.get("TAVILY_API_KEY") else "⚠️ not set (model-only)")
    n_queries = st.slider("Search queries", 3, 8, 5)

field = st.text_input(
    "Your research field",
    value="probabilistic computing, p-bits, Ising machines, QUBO",
    help="Be specific — e.g. 'computational biology + QUBO optimization'.",
)

if st.button("🚀 Scout opportunities", type="primary", use_container_width=True):
    if not os.environ.get("NEBIUS_API_KEY"):
        st.error("Set NEBIUS_API_KEY in your environment first.")
        st.stop()

    log_box = st.empty()
    logs = []

    def progress(msg):
        logs.append(f"• {msg}")
        log_box.info("\n\n".join(logs))

    try:
        with st.spinner("Scouting…"):
            result = ss.scout(field, n_queries=n_queries, progress=progress)
    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.stop()

    log_box.success(
        f"Done — model `{result.model}`, "
        f"{'live Tavily search' if result.used_tavily else 'model-only mode'}, "
        f"{len(result.sources)} sources."
    )

    st.divider()
    st.markdown(result.digest_markdown)

    with st.expander(f"🔎 Search queries Nemotron generated ({len(result.queries)})"):
        for q in result.queries:
            st.write("-", q)

    if result.sources:
        with st.expander(f"📚 Raw sources from Tavily ({len(result.sources)})"):
            for s in result.sources:
                if s["url"]:
                    st.markdown(f"- [{s['title'] or s['url']}]({s['url']})")

    st.download_button(
        "⬇️ Download digest (Markdown)",
        data=result.digest_markdown,
        file_name=f"scholarscout_{field[:30].replace(' ', '_')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.divider()
st.caption(
    "Built for the Nebius × NVIDIA Global AI Hackathon. "
    "Informational only — verify every deadline on the official venue page."
)
