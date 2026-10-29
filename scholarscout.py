"""
================================================================================
 ScholarScout — an autonomous research-opportunity agent
================================================================================

Give it your research field; it finds open Calls for Papers, conference
deadlines, journals, and grants, judges each venue's reputability, and returns a
clean, grouped digest with a suggested submission plan.

HOW IT MEETS THE HACKATHON REQUIREMENTS
---------------------------------------
  * Runs on NEBIUS TOKEN FACTORY (OpenAI-compatible endpoint).
  * Uses an NVIDIA OPEN-SOURCE model (Nemotron) for all reasoning:
        1. turning a field into smart search queries,
        2. judging/ranking venues for reputability,
        3. writing the final grouped digest.
  * Uses TAVILY for live web search (qualifies for the "Best Use of Tavily"
    prize). If no Tavily key is present, it degrades gracefully to a
    model-only digest so the demo still runs.

This file is the engine. app.py is the Streamlit UI on top of it.

Keys are read from the environment — NEVER hard-code them:
    NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL, TAVILY_API_KEY
================================================================================
"""

import os
import json
import datetime
from dataclasses import dataclass, field

TODAY = datetime.date.today().isoformat()
CURRENT_YEAR = datetime.date.today().year

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()                      # pulls keys from a local .env if present
except Exception:
    pass

# Tavily is optional — import lazily so the app still runs without it.
try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except Exception:
    _TAVILY_AVAILABLE = False


# ------------------------------------------------------------------------------
# Configuration — all from the environment, with sensible defaults.
# ------------------------------------------------------------------------------
NEBIUS_BASE_URL = os.environ.get(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.us-central1.nebius.com/v1/"
)
# IMPORTANT: this MUST be an NVIDIA open-source (Nemotron) model for the
# hackathon to count. Verify the exact id in your Nebius Model catalog.
NEBIUS_MODEL = os.environ.get("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")


def _nebius_client():
    """Build the Nebius Token Factory client (OpenAI-compatible)."""
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY is not set. Run:  export NEBIUS_API_KEY='...'  "
            "(or put it in a local .env file). Never hard-code the key."
        )
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=api_key)


def _tavily_client():
    """Build the Tavily client if a key is present, else None."""
    key = os.environ.get("TAVILY_API_KEY")
    if _TAVILY_AVAILABLE and key:
        return TavilyClient(api_key=key)
    return None


# ------------------------------------------------------------------------------
# A small helper to call Nemotron on Nebius and get back text.
# ------------------------------------------------------------------------------
def _chat(client, system, user, temperature=0.3, max_tokens=2000):
    resp = client.chat.completions.create(
        model=NEBIUS_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


@dataclass
class ScoutResult:
    field: str
    queries: list = field(default_factory=list)
    sources: list = field(default_factory=list)   # list of {title, url, content}
    digest_markdown: str = ""
    model: str = NEBIUS_MODEL
    used_tavily: bool = False


# ------------------------------------------------------------------------------
# STEP 1 — Nemotron turns a research field into focused search queries.
# ------------------------------------------------------------------------------
def generate_queries(client, research_field, n=5):
    system = (
        "You are a research-opportunity scout. Given a researcher's field, output "
        "concise web-search queries that will surface CURRENT calls for papers, "
        "conference submission deadlines, peer-reviewed journals accepting "
        "submissions, and open research grants. Favor reputable sources "
        "(IEEE, ACM, Springer, Nature, aideadlines.org, wikicfp.com, grants.gov). "
        f"IMPORTANT: today is {TODAY}. Only look for OPEN/UPCOMING opportunities — "
        f"put the year {CURRENT_YEAR} or {CURRENT_YEAR + 1} in most queries so you "
        "surface current deadlines, not expired ones. "
        "Return ONLY a JSON array of query strings, nothing else."
    )
    user = f"Research field: {research_field}\nNumber of queries: {n}"
    raw = _chat(client, system, user, temperature=0.4, max_tokens=500)
    # Be forgiving about formatting the model returns.
    try:
        start, end = raw.find("["), raw.rfind("]")
        queries = json.loads(raw[start : end + 1])
        queries = [str(q).strip() for q in queries if str(q).strip()]
    except Exception:
        queries = [line.strip("-• \t") for line in raw.splitlines() if line.strip()]
    return queries[:n] or [f"{research_field} call for papers 2027 deadline"]


# ------------------------------------------------------------------------------
# STEP 2 — Tavily runs the live searches and returns real sources.
# ------------------------------------------------------------------------------
def search_web(tavily, queries, max_results_per_query=4):
    sources = []
    for q in queries:
        try:
            res = tavily.search(
                query=q, max_results=max_results_per_query, search_depth="advanced"
            )
            for r in res.get("results", []):
                sources.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": (r.get("content", "") or "")[:800],
                    }
                )
        except Exception as e:
            sources.append({"title": f"[search error for '{q}']", "url": "", "content": str(e)})
    # de-dup by url
    seen, deduped = set(), []
    for s in sources:
        if s["url"] and s["url"] in seen:
            continue
        seen.add(s["url"])
        deduped.append(s)
    return deduped


# ------------------------------------------------------------------------------
# STEP 3 — Nemotron reads the sources and writes the judged, grouped digest.
# ------------------------------------------------------------------------------
def write_digest(client, research_field, sources):
    sources_block = "\n\n".join(
        f"[{i+1}] {s['title']}\nURL: {s['url']}\n{s['content']}"
        for i, s in enumerate(sources)
    ) or "(No live search results available — use your own knowledge, and clearly label items as unverified.)"

    system = (
        f"You are a rigorous research-opportunity analyst. Today is {TODAY}. "
        "From the provided web sources, produce a SKIMMABLE markdown digest for the "
        "researcher. Group as:\n"
        "## ⏰ Urgent (deadline within ~45 days)\n"
        "## 1. Open now (rolling / no fixed deadline)\n"
        "## 2. Upcoming deadlines (next ~4 months)\n"
        "## 3. Best early / accessible targets\n\n"
        f"For each venue give: name (bold), deadline + days left (compute days left "
        f"from today, {TODAY}), cost (FREE vs APC ~$), a one-line reputability "
        "judgement, and a clickable markdown link. "
        "Prioritize OPEN/UPCOMING opportunities; SKIP venues whose deadline has "
        "clearly already passed unless they recur (note the next expected cycle). "
        "CRITICAL: only recommend reputable, peer-reviewed, indexed venues "
        "(IEEE/ACM/Springer/Nature/established). Flag anything that looks predatory "
        "or pay-to-publish-without-review. If a fact isn't in the sources, mark it "
        "'(unverified)'. End with a 2-3 line suggested submission plan. Be concise "
        "and use real links from the sources."
    )
    user = f"Research field: {research_field}\n\nSOURCES:\n{sources_block}"
    return _chat(client, system, user, temperature=0.3, max_tokens=4000)


# ------------------------------------------------------------------------------
# The full pipeline: field -> queries -> search -> digest.
# ------------------------------------------------------------------------------
def scout(research_field, n_queries=5, progress=None):
    """Run the whole agent. `progress` is an optional callback(str) for UI logs."""
    def log(msg):
        if progress:
            progress(msg)

    client = _nebius_client()
    tavily = _tavily_client()

    log(f"Asking Nemotron ({NEBIUS_MODEL}) for search queries…")
    queries = generate_queries(client, research_field, n=n_queries)

    sources, used_tavily = [], False
    if tavily:
        log(f"Searching the web with Tavily across {len(queries)} queries…")
        sources = search_web(tavily, queries)
        used_tavily = True
    else:
        log("No Tavily key found — running in model-only mode (no live search).")

    log("Nemotron is judging venues and writing the digest…")
    digest = write_digest(client, research_field, sources)

    return ScoutResult(
        field=research_field,
        queries=queries,
        sources=sources,
        digest_markdown=digest,
        model=NEBIUS_MODEL,
        used_tavily=used_tavily,
    )


# ------------------------------------------------------------------------------
# CLI entry point:  python3 scholarscout.py "your research field"
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    field_arg = " ".join(sys.argv[1:]) or "probabilistic computing, p-bits, Ising machines, QUBO"
    print(f"\nScholarScout — scouting opportunities for: {field_arg}\n" + "=" * 70)
    result = scout(field_arg, progress=lambda m: print(f"  … {m}"))
    print("\n" + "=" * 70)
    print(f"Model: {result.model}  |  Tavily used: {result.used_tavily}  |  "
          f"Sources: {len(result.sources)}")
    print("=" * 70 + "\n")
    print(result.digest_markdown)
