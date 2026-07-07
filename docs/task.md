# Project Task Tracker: UAE HR & Nafis Copilot

Current Focus: **Phase 3: Agent & Evaluation Hardening**
Goal: Add structured output (JSON mode), enforce citation verification, add input sanitization, and improve evaluation robustness.

## Phase 1: Test Suite Hardening (Completed)
- `[x]` **1.1 Test Suite Refactoring**
- `[x]` **1.2 Consolidation of Tests**
- `[x]` **1.3 Retrieval Evaluation (`eval_retrieval.py`)**
- `[x]` **1.4 Semantic Evaluation Strategy**

---

## Phase 2: Fix Retrieval Quality (Completed)

### 1. Sub-Article Chunking & Overlap Windows (`ingestion.py`)
- `[x]` Modify `split_by_articles()` to include a second pass for large articles.
- `[x]` Write `split_article_into_subclauses()` using regex to find `1.`, `2.`, `a.`, `b.` markers.
- `[x]` Ensure chunks are combined to stay between 300-600 tokens (don't make them too small).
- `[x]` Prepend the parent Article Header + Title to every sub-chunk so it retains semantic context.
- `[x]` Skip splitting for articles under 500 characters.

### 2. Score Thresholding & Limit Expansion (`database.py`)
- `[x]` Update `search_laws()` to fetch `limit=5` (up from 3) to give the LLM more context.
- `[x]` Implement a `score_threshold = 0.35`. Any retrieved chunk with a cosine similarity below this will be discarded to prevent the LLM from hallucinating on irrelevant data.
- `[x]` Add parent article deduplication logic (if multiple chunks from the same article are found, ensure we don't overwhelm the LLM with redundant text).
- `[x]` Rebuild Qdrant Database (`force_recreate=True`) to ingest the new sub-chunks.

### 3. Multi-Turn Query Rewriting (`agent.py`)
- `[x]` Replace crude string concatenation with an LLM-powered query rewriter.
- `[x]` Create a new function `rewrite_query_for_search()` that uses a *free-tier model* (e.g., Groq/Llama or Gemini 1.5 Flash).
- `[x]` Prompt the rewriter to replace pronouns ("it") with the actual subject ("probation period") based on conversation history.
- `[x]` Implement fallback logic in case the LLM rewrite fails.

### 4. Evaluation Updates (`eval_retrieval.py` & `test_suite.py`)
- `[x]` Update `eval_retrieval.py` to check for `Recall@5` instead of `Recall@3`.
- `[x]` Ensure tests accommodate the new sub-chunking format. The "6 months" issue (which was fixed locally in Phase 1) needs to be validated against LangSmith's `accuracy_evaluator`.

---

## DEFERRED ITEMS (Not doing in Phase 2)
*We are explicitly skipping these features for now to isolate variables and measure the impact of chunking first. These are logged here so we don't lose track of them.*

1. **Hybrid Search (Vector + BM25)**
   - *Why deferred:* Adds significant complexity (new dependency, index maintenance, score fusion). Sub-article chunking and query rewriting should solve our current failures. We will measure the improvement before adding a secondary search index.
2. **Cross-Encoder Re-ranking**
   - *Why deferred:* Adds a new model dependency (e.g., `sentence-transformers/cross-encoder`) and ~200-500ms latency per query. Our Recall@3 was already 1.000; the issue was context dilution (chunk size), not ranking errors.

---

## Phase 3: Agent & Evaluation Hardening (Completed)
- `[x]` Add structured output (JSON mode) schema (`schemas.py`)
- `[x]` Integrate structured output parsing into `agent.py`
- `[x]` Add input sanitization and guardrails (`guardrails.py`)
- `[x]` Update UI (`app.py`) to handle structured dict output and render badges
- `[x]` Upgrade evaluation suite (`evaluations.py`) to use fuzzy/semantic similarity

## Phase 4: Production Operations (In Progress)
- `[x]` **4.1 Observability (Logging)**
  - Created `src/logging_config.py` with Trace ID injection and dual console+file output.
  - Replaced all `print()` in `agent.py`, `database.py`, `ingestion.py` with structured logger calls.
  - Each user request now gets a unique 8-char Trace ID (e.g. `[0BD21E0E]`).
  - Log file written to `logs/copilot.log`.
- `[x]` **4.2 Performance (Caching)**
  - Created `src/caching.py` using `diskcache` (persistent across restarts).
  - Cache limit set to **50 MB** (10× our actual ~3.7 MB need for 150 chunks).
  - `get_embeddings()` in `database.py` now checks the cache first per text snippet.
  - Verified: Run 1 shows "Cache MISS → Gemini API called". Run 2 shows "Cache HIT → instant".
  - Same search results confirmed on both runs (deterministic embeddings).
- `[x]` **4.3 Resilience (Database Versioning)**
  - Implemented version detection (`_get_next_collection_version()`) to automatically find the next available version (e.g. `v2`).
  - Switched ingestion to build versioned collections in the background.
  - Added atomic alias swapping (`swap_alias_to_active()`) using Qdrant client aliases.
  - Implemented automatic cleanup of older collection versions (`v1` is automatically deleted after `v2` goes active).
- `[x]` **4.4 Safety (CI/CD Pipeline)**
  - Created `.github/workflows/test.yml` GitHub Actions pipeline script.
  - Set up automated Python environment provisioning and dependencies installation.
  - Set up background DB initialization step.
  - Added exit code checks to `test_suite.py` to correctly report passes/failures to the cloud runner.
