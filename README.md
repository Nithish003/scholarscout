# 🔭 ScholarScout

**An autonomous research-opportunity agent — powered by NVIDIA Nemotron on Nebius Token Factory, with live web search by Tavily.**

Built for the **Nebius × NVIDIA Global AI Hackathon** (Best Apps & Agents track).

---

## What it does

Researchers — especially students and early-career academics — waste hours hunting
for *where* to submit their work: calls for papers, conference deadlines,
peer-reviewed journals, and open grants are scattered across dozens of sites, and
it's hard to tell a reputable venue from a predatory one.

**ScholarScout** does it for you. Give it your research field and it:

1. **Reasons about your field** (Nemotron) to generate focused search queries.
2. **Searches the live web** (Tavily) for current CFPs, deadlines, journals, and grants.
3. **Judges each venue** (Nemotron) for reputability — flagging predatory /
   pay-to-publish-without-review venues — and writes a clean, grouped digest with
   a suggested submission plan.

Output is grouped into **⏰ Urgent (≤45 days)**, **Open now**, **Upcoming deadlines**,
and **Best early targets**, each with deadlines, cost (FREE vs APC), a reputability
note, and a clickable link.

## How it uses the required tech

| Requirement | How ScholarScout uses it |
|---|---|
| **NVIDIA open-source model (Nemotron)** | Nemotron does all three reasoning steps: query generation, venue reputability judgement, and digest writing. Set via `NEBIUS_MODEL`. |
| **Nebius Token Factory** | All inference runs on Token Factory's OpenAI-compatible endpoint (`https://api.tokenfactory.us-central1.nebius.com/v1/`). One client, swappable model. |
| **Tavily** (bonus) | Live `search()` with `search_depth="advanced"` turns Nemotron's queries into real, cited sources. Degrades gracefully to model-only if no Tavily key. |

## Architecture

```
  field ──▶ [Nemotron: generate queries] ──▶ [Tavily: live search] ──▶ [Nemotron: judge + write digest] ──▶ Markdown digest
            (scholarscout.generate_queries)   (scholarscout.search_web)  (scholarscout.write_digest)
```

`scholarscout.py` is the engine (also runnable as a CLI). `app.py` is the Streamlit UI / hosted demo.

## Run it locally

```bash
git clone <your-repo-url>
cd scholarscout
pip install -r requirements.txt

export NEBIUS_API_KEY="your-nebius-key"          # required
export NEBIUS_MODEL="nvidia/Llama-3_3-Nemotron-Super-49B-v1"   # an NVIDIA Nemotron id from the catalog
export TAVILY_API_KEY="your-tavily-key"          # optional, enables live search

# UI:
streamlit run app.py
# or CLI:
python3 scholarscout.py "computational biology + QUBO optimization"
```

> Copy `.env.example` to `.env` to keep keys in a file instead (it's git-ignored). **Never commit real keys.**

## Feedback for Nebius / NVIDIA / Tavily

- **Nebius Token Factory:** the OpenAI-compatible API made integration a drop-in —
  swapping to a Nemotron model was a single env var. The quick-start snippet on the
  dashboard got us running in minutes.
- **NVIDIA Nemotron:** strong at the structured-reasoning + JSON-ish query generation
  and at the "judge this venue" task; instruction-following on the grouped-digest
  format was reliable.
- **Tavily:** `search_depth="advanced"` returned clean, relevant, citable results that
  were easy to feed back into the model as grounding — exactly the agentic-search fit.
- **Wishlist:** a one-call "search + rerank" helper, and clearer per-model context/
  rate-limit hints in the catalog UI.

## License

MIT — see [LICENSE](LICENSE).
