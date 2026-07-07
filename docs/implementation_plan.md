# RAG System Deep Audit & Production-Readiness Gap Analysis

## TL;DR — The Honest Truth

Your system is a **solid learning prototype** — better than most tutorials — but it is **not production-grade**. Here's the honest scorecard:

| Dimension | Current Grade | Production Bar |
|-----------|:---:|:---:|
| PDF Ingestion & Chunking | C+ | A |
| Embedding & Vector DB | B- | A |
| Retrieval Quality | D+ | A |
| Agent / LLM Orchestration | B | A |
| Test Suite (test_suite.py) | **D** | A |
| LangSmith Evaluation (evaluations.py) | **F** | A |
| Production Infra & Ops | F | A |
| Security & Guardrails | D | A |

**Pass rate: 9/19 (47%).** But the scarier part isn't the failures — it's that **several "passes" are accidents**, and **several "failures" are false negatives** (the agent gave the RIGHT answer but your test said WRONG). Your testing framework is unreliable in both directions.

---

## Part 1: What You Built (Architecture Recap)

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR CURRENT SYSTEM                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  PDF Files (3)                                          │
│       │                                                 │
│       ▼                                                 │
│  ingestion.py  ──→  Regex split by "Article (X)"        │
│       │              (whole articles = 1 chunk)          │
│       ▼                                                 │
│  database.py   ──→  gemini-embedding-001 (3072-dim)     │
│       │              Qdrant local disk mode              │
│       ▼                                                 │
│  agent.py      ──→  Phase A: Python retrieves top-3     │
│       │              Phase B: LLM reasons + tool calls   │
│       │              Model: gpt-4o-mini (temp=0)         │
│       ▼                                                 │
│  tools.py      ──→  math_calculator (safe AST eval)     │
│       │                                                 │
│  app.py        ──→  Streamlit chat UI                   │
│                                                         │
│  test_suite.py ──→  19 hardcoded test cases              │
│  evaluations.py──→  LangSmith with 3 custom evaluators  │
└─────────────────────────────────────────────────────────┘
```

---

## Part 2: The Test Suite Is Lying To You (Both Ways)

This is the most critical issue. Your test framework has structural flaws that make results untrustworthy.

### 2A. FALSE NEGATIVES — Tests That FAILED But The Agent Was CORRECT (PASS -> FAIL)

> [!CAUTION]
> These tests punish the agent for being right. This is the worst kind of testing bug because it erodes your trust in a system that's actually working.

#### Test 3: "6 months" vs "six (6) months"
- **Agent said:** `"six (6) months"` ← Perfectly correct, citing the law exactly
- **Test wanted:** the substring `"6 months"`
- **Why it failed:** `"six (6) months"` does NOT contain `"6 months"` as a substring. The word `"six"` separates them.
- **Root Cause:** Brittle keyword matching with no tolerance for equivalent phrasings

#### Test 9: "100,000" forbidden but appears in the law citation
- **Agent said:** `"AED 80,000"` (CORRECT answer) but then quoted the law: `"not exceeding AED 100,000 is imposed per worker"`
- **Test wanted:** `"100,000"` nowhere in the response
- **Why it failed:** The agent correctly cited the legal range (20k–100k per worker) while computing the right minimum (80k). Your forbidden-term check can't distinguish between the *answer* and a *legal citation*.
- **Root Cause:** Forbidden term check is too broad — it searches the entire response including citations

#### Test 11: "written notice" vs "in writing"
- **Agent said:** `"you must provide written notice"` ← semantically identical
- **Test wanted:** `"in writing"` as an exact substring
- **Why it failed:** `"written notice"` ≠ `"in writing"` as a string match
- **Root Cause:** Same brittle keyword issue

#### Test 13: Agent computed correctly but "84" not literally present
- **Agent said:** `"27,999.72 AED"` — computed `333.33 * 84` correctly via calculator
- **Test wanted:** the literal string `"84"` in the final answer
- **Why it failed:** The agent computed 84 internally (via tool) but reported the final monetary result, not the intermediate "84 days"
- **Root Cause:** Test checks for intermediate computation artifacts in the final answer instead of checking the tool call history

#### Tests 17 & 18: Agent computed correctly but via different (valid) math expressions
- **Test 17:** Expected `calculate('45 * 600')` but agent called `calculate('18000 * 45 / 30')` — mathematically identical, answer AED 31,500 is CORRECT
- **Test 18:** Expected `calculate('15 * 400')` but agent called `calculate('15 * (12000 / 30)')` — same result
- **Root Cause:** `expected_math_tokens` enforces a specific decomposition strategy. The agent found a different (equally valid) way to compute the same thing.

### 2B. FALSE POSITIVES — Tests That PASSED But Shouldn't Have (Or Are Misleading) (FAIL -> PASS)

#### Test 2: Claims "46,000" is present but doesn't verify the breakdown
- The test checks that `"46000"` appears in the response. But it doesn't verify that the agent computed `40,000 + 6,000` correctly — if the agent wrote "the total fine is 46,000 but one part is 30,000 and another is 16,000", it would still pass.

#### General Pattern: Key-phrase checking can't catch wrong reasoning
- A response containing the right number for the wrong reason passes. Example: if the agent said "According to maternity leave law, the sham Emiratisation fine is 60,000" — Test 1 would PASS because "60000" is present and "Article 2" is somewhere in the response. The reasoning is completely wrong, but keyword matching can't detect that.

### 2C. Fundamental Testing Architecture Problems

| Problem | Impact |
|---------|--------|
| **Keyword matching** — checks substrings like `"6 months"` | Can't handle semantic equivalence ("six months", "180 days", "half a year") |
| **Binary scoring** — each check is 1.0 or 0.0 | A test with 5 correct checks and 1 trivial formatting failure = 0.0 (FAILED) |
| **No retrieval quality testing** — you never verify WHAT was retrieved | Agent could hallucinate from wrong articles and still "pass" if keywords match |
| **No semantic evaluation** — zero LLM-as-judge checks | You can't detect wrong reasoning that happens to contain right keywords |
| **LangSmith evaluators return NaN** | `analysis_results.txt` shows ALL scores as `nan` and ALL 15 runs as "failed" — the evaluators aren't working at all |
| **`expected_math_tokens`** enforces one specific decomposition | Penalizes valid alternative computation strategies |
| **No confidence thresholding test** | Never checks if the retrieval score was actually high enough to trust |

---

## Part 3: Retrieval Pipeline — The Silent Bottleneck

> [!IMPORTANT]
> Retrieval quality is the #1 determinant of RAG system performance. A RAG system with a great LLM but bad retrieval will always lose to a system with an average LLM but excellent retrieval.

### 3A. Chunking Problems

Your current chunking: **1 chunk = 1 entire legal article.** This is the biggest single weakness.

| Problem | Why It Matters |
|---------|---------------|
| **Articles are too large** | Some articles are 2000+ characters. The embedding of a long text is a diluted average of all concepts in it. If Article 9 covers probation, notice periods, AND dismissal procedures, its embedding is an average of all three — it's not strongly similar to any specific question. |
| **No overlap between chunks** | If a user's question spans two articles (e.g., "can I dismiss during probation without paying gratuity?" touches Article 9 AND Article 51), there's no chunk that bridges both concepts. |
| **No sub-article splitting** | Many articles have numbered clauses (1, 2, 3...) that address completely different rules. Clause 2 of Article 2 (sham Emiratisation) and Clause 9 of Article 2 (circumvention fines) are in the SAME chunk but address different violations. |
| **Preamble noise** | Preambles are chunked and embedded, adding noise to the vector space. |

**What production systems do:**
- **Hierarchical chunking** — split articles into sub-sections (clauses), then create parent-child relationships so the retriever can fetch a specific clause but the context can expand to the full article
- **Overlap windows** — each chunk includes 1-2 sentences from the previous/next chunk for continuity
- **Semantic chunking** — use an LLM or topic model to split by semantic boundaries, not just regex
- **Chunk size targets** — typically 200-500 tokens per chunk, not 2000+

### 3B. Retrieval Problems

| Problem | What Happens |
|---------|-------------|
| **Top-3 only, no re-ranking** | You fetch the 3 nearest vectors. But cosine similarity in high-dimensional space is noisy — the #1 result isn't always the best. Production systems fetch top-10-20, then re-rank with a cross-encoder. |
| **No score thresholding** | If all 3 results have scores below 0.5, the retrieved context is probably garbage. You still feed it to the LLM anyway. |
| **No hybrid search** | Pure vector search misses exact terms. "Article 5" as a query won't necessarily find Article 5 — it'll find whatever is semantically closest. Production systems combine vector search with BM25/keyword search. |
| **Single query, no expansion** | The user's exact phrasing becomes the search query. "Can we fire someone on probation?" should also search for "terminate", "dismiss", "trial period". This is called **query expansion** or **HyDE (Hypothetical Document Embedding)**. |
| **No metadata filtering** | You have metadata (source document, article number) but never use it for filtering. If a user says "under Cabinet Regulation 43...", you should filter to only that document BEFORE doing vector search. |
| **Multi-turn context injection is broken** | Lines 164-169 of agent.py: you concatenate the last user message with the current query. This is crude — if the previous question was about sick leave and the follow-up is "how much do we pay?", you search for "sick leave rules how much do we pay" which may not retrieve the right articles. |

### 3C. Test 7 Failure — Multi-Turn Is Architecturally Broken

The multi-turn test fails because your context concatenation (line 164-169) only grabs the LAST user message. But the retrieval query needs to be **rewritten** by the LLM to be standalone. Production systems use a **query rewriter** step:

```
User Turn 1: "What is the probation period?"
User Turn 2: "Can the employer extend it?"

Your system searches: "What is the probation period? Can the employer extend it?"
Should search:         "Can the employer extend the probation period beyond 6 months under UAE Labour Law?"
```

---

## Part 4: Agent & LLM Layer Issues

### 4A. Model Mismatch
- agent.py says `gpt-4o-mini` but app.py sidebar says `llama-3.3-70b-versatile (Groq)`. Your agent uses `ChatOpenAI` — which model is actually running? The `.env` has both `OPENAI_API_KEY` and `GROQ_API_KEY`. This confusion means you might be testing one model but deploying another.

### 4B. Prompt Engineering Gaps
- The system prompt is **1700+ characters of rules** trying to constrain the LLM's behavior. This is a red flag — it means the architecture doesn't enforce these constraints, so you're relying on prompt compliance.
- **"DAILY WAGE RULE"** forces a specific computation strategy (salary ÷ 30 first). But your test cases sometimes expect a DIFFERENT decomposition. The prompt and tests are fighting each other.
- **No few-shot examples** — production prompts include 2-3 worked examples showing the exact output format expected.

### 4C. Missing Guardrails
| Missing | Risk |
|---------|------|
| **No input sanitization** | Prompt injection: "Ignore all previous instructions and..." |
| **No output validation** | Agent can hallucinate citations (e.g., "Article 50" when no Article 50 was retrieved) |
| **No fallback** | If the LLM API is down, the system crashes — no graceful degradation |
| **No answer grounding check** | Agent could use training knowledge instead of retrieved context and you'd never know |
| **No token budget** | Long conversations could exceed context window silently |

---

## Part 5: What Production RAG Systems Actually Look Like

Here's how companies (Anthropic, OpenAI enterprise customers, legal-tech companies) build production RAG:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION RAG ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│  │ Document      │   │ Chunking     │   │ Metadata         │    │
│  │ Parser        │──▶│ Engine       │──▶│ Enrichment       │    │
│  │ (Unstructured,│   │ (Semantic +  │   │ (Entity extract, │    │
│  │  LlamaParse)  │   │  Hierarchical│   │  topic tagging)  │    │
│  └──────────────┘   │  + Overlap)  │   └──────────────────┘    │
│                      └──────────────┘            │              │
│                                                  ▼              │
│                                        ┌──────────────────┐    │
│                                        │ Vector DB         │    │
│                                        │ (Qdrant/Pinecone) │    │
│                                        │ + BM25 Index      │    │
│                                        └──────────────────┘    │
│                                                  │              │
│  ┌──────────────┐                                │              │
│  │ User Query   │                                │              │
│  └──────┬───────┘                                │              │
│         │                                        │              │
│         ▼                                        │              │
│  ┌──────────────┐                                │              │
│  │ Query        │  ◀── Multi-turn rewriter       │              │
│  │ Processing   │  ◀── Query expansion/HyDE      │              │
│  │ Pipeline     │  ◀── Metadata filter extraction │              │
│  └──────┬───────┘                                │              │
│         │                                        │              │
│         ▼                                        ▼              │
│  ┌───────────────────────────────────────────────┐              │
│  │ HYBRID RETRIEVAL                               │              │
│  │  • Vector similarity (top-20)                  │              │
│  │  • BM25 keyword search (top-20)                │              │
│  │  • Reciprocal Rank Fusion                      │              │
│  │  • Cross-encoder re-ranking → top-5            │              │
│  │  • Score threshold filtering                   │              │
│  └──────────────┬────────────────────────────────┘              │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────┐                   │
│  │ CONTEXT ASSEMBLY                          │                   │
│  │  • Expand chunks to parent context        │                   │
│  │  • Deduplicate overlapping passages       │                   │
│  │  • Order by document structure            │                   │
│  └──────────────┬───────────────────────────┘                   │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────┐                   │
│  │ LLM REASONING (with guardrails)           │                   │
│  │  • System prompt + few-shot examples      │                   │
│  │  • Tool calling (calculator, etc.)        │                   │
│  │  • Output structured JSON                 │                   │
│  │  • Grounding check (cite only retrieved)  │                   │
│  └──────────────┬───────────────────────────┘                   │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────┐                   │
│  │ POST-PROCESSING & SAFETY                  │                   │
│  │  • Citation verification                  │                   │
│  │  • Hallucination detection                │                   │
│  │  • Confidence scoring                     │                   │
│  │  • PII filtering                          │                   │
│  └──────────────────────────────────────────┘                   │
│                                                                 │
│  ┌──────────────────────────────────────────┐                   │
│  │ EVALUATION & MONITORING                   │                   │
│  │  • LLM-as-judge (semantic correctness)    │                   │
│  │  • Retrieval precision/recall/MRR metrics │                   │
│  │  • Latency & cost dashboards              │                   │
│  │  • A/B testing framework                  │                   │
│  │  • Regression test suite                  │                   │
│  │  • User feedback loop                     │                   │
│  └──────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Complete Gap Inventory (Severity-Ranked)

### 🔴 CRITICAL (System fails silently / gives wrong answers)

| # | Gap | File(s) | Impact |
|---|-----|---------|--------|
| 1 | **Test suite gives false negatives** — agents penalized for correct answers | [test_suite.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/test_suite.py) | You can't trust ANY test result |
| 2 | **Test suite gives false positives** — keyword match can't detect wrong reasoning | [test_suite.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/test_suite.py) | Agent can pass tests while being wrong |
| 3 | **LangSmith evaluators return NaN** — all 15 runs show score 0.0 | [evaluations.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/evaluations.py), [analysis_results.txt](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/Evaluation/analysis_results.txt) | LangSmith evaluation is completely non-functional |
| 4 | **No retrieval evaluation** — never measure if correct articles are retrieved | All | The CORE function of RAG is untested |
| 5 | **Chunks too large** — entire articles as single embeddings | [ingestion.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/ingestion.py) | Embedding dilution → wrong articles retrieved |
| 6 | **Multi-turn retrieval is broken** — crude string concatenation | [agent.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/agent.py#L164-L169) | Follow-up questions retrieve wrong context |
| 7 | **Model identity confusion** — code says OpenAI, UI says Groq | [agent.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/agent.py#L21), [app.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/app.py#L377) | Testing on different model than deploying |

### 🟠 HIGH (Significant quality degradation)

| # | Gap | Impact |
|---|-----|--------|
| 8 | **No hybrid search** — pure vector, no keyword/BM25 | Misses exact term matches (specific article numbers, regulation names) |
| 9 | **No re-ranking** — raw cosine top-3 used directly | Noisy results; relevant articles pushed down |
| 10 | **No score thresholding** — low-confidence results fed to LLM | Agent fabricates answers from irrelevant context |
| 11 | **No query expansion** — user's exact words as search query | Vocabulary mismatch between informal queries and legal text |
| 12 | **No metadata filtering** — can't restrict search to a specific document | User says "under Cabinet Regulation 43" but search spans all docs |
| 13 | **No semantic/LLM-as-judge evaluation** | Can't detect wrong reasoning, hallucinated facts, or plausible-sounding errors |
| 14 | **No citation verification** — agent can cite articles that weren't retrieved | Hallucinated citations go undetected |

### 🟡 MEDIUM (Reliability & robustness)

| # | Gap | Impact |
|---|-----|--------|
| 15 | **No input sanitization** | Prompt injection vulnerability |
| 16 | **No structured output** | Can't programmatically extract answer + citations + confidence |
| 17 | **No few-shot examples in prompt** | Model guesses output format, sometimes wrong |
| 18 | **No error handling in retrieval** | Qdrant connection issues = crash |
| 19 | **No token counting** | Long conversations silently overflow context window |
| 20 | **No answer confidence score** | User can't tell "high confidence" vs "best guess" answers |
| 21 | **Prompt vs test disagreement** — prompt says "salary/30 first" but tests expect other decompositions | Systematically produces false failures |

### 🟢 LOW (Production polish)

| # | Gap | Impact |
|---|-----|--------|
| 22 | **No logging/observability** — only print statements | Can't debug production issues |
| 23 | **No rate limiting on API** — depends on sleep timers | Fragile under load |
| 24 | **No caching** — same query re-embeds every time | Wasted API calls and latency |
| 25 | **No versioning** — no way to track which chunks/embeddings are in the DB | Can't reproduce results |
| 26 | **Qdrant in local disk mode** — single machine, no clustering | Not horizontally scalable |
| 27 | **No user feedback mechanism** — no thumbs up/down | Can't learn from real usage |
| 28 | **No A/B testing framework** | Can't compare model/prompt/retrieval changes |
| 29 | **`.env` has API keys in plain text** | Security risk if repo is shared |
| 30 | **No CI/CD pipeline** | Tests don't run automatically on changes |

---

## Part 7: Proposed Implementation Roadmap

### Phase 1: Fix The Testing Foundation (Do First!) 
> *"You can't improve what you can't measure."*

#### [MODIFY] [test_suite.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/test_suite.py)
- Replace brittle keyword matching with **normalized/fuzzy matching** (e.g., "6 months" should match "six (6) months", "six months")
- Add **retrieval evaluation**: for each test case, define `expected_article_numbers` and check if they appear in the retrieved context BEFORE the LLM answers
- Change `expected_math_tokens` to `expected_final_value` — check the tool's OUTPUT, not the exact expression used
- Fix forbidden term check to exclude the law citation paragraph
- Add **partial scoring** (not binary 0/1): e.g., 3/5 checks pass = 0.6

#### [MODIFY] [evaluations.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/evaluations.py)
- Debug why LangSmith scores are NaN (likely a schema mismatch between dataset outputs and evaluator expectations)
- Add an **LLM-as-judge evaluator** that uses a second LLM to check semantic correctness

#### [NEW] `src/eval_retrieval.py`
- Standalone retrieval quality test: for each query, check if the correct articles are in top-3 results
- Compute **MRR (Mean Reciprocal Rank)**, **Recall@K**, and **Precision@K**

---

### Phase 2: Fix Retrieval Quality
> *This is where 80% of your accuracy improvement will come from.*

#### [MODIFY] [ingestion.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/ingestion.py)
- Add **sub-article chunking**: split articles at numbered clauses (1., 2., 3.)
- Add **chunk overlap**: include the article title + first clause in every sub-chunk for context
- Target chunk size: ~300-500 tokens
- Keep parent-child relationships: each sub-chunk stores `parent_article_id`

#### [MODIFY] [database.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/database.py)
- Add **score threshold** to `search_laws()`: if best score < 0.35, return "No confident match"
- Increase `limit` from 3 to 10, then add a **re-ranking step** using a cross-encoder or reciprocal rank fusion
- Add **hybrid search**: combine vector search with Qdrant's built-in keyword filtering
- Add **metadata filtering**: extract document references from the query and filter accordingly

#### [MODIFY] [agent.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/agent.py)
- Replace multi-turn string concatenation with an **LLM query rewriter** that creates a standalone search query from conversation history
- Add **parent context expansion**: if a sub-chunk is retrieved, also fetch its parent article for full context

---

### Phase 3: Agent & Evaluation Hardening

#### [MODIFY] [agent.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/agent.py)
- Add **structured output** (JSON mode): `{answer, citations[], confidence, articles_used[]}`
- Add **citation verification**: check that every cited article was actually in the retrieved context
- Add **few-shot examples** to the system prompt (2-3 worked Q&A pairs)
- Add **input sanitization**: basic prompt injection detection
- Resolve model identity confusion (pick ONE model, update both code and UI)

#### [NEW] `src/guardrails.py`
- Input validation (prompt injection detection, query length limits)
- Output validation (citation grounding check, hallucination detection)
- Confidence scoring based on retrieval scores + LLM certainty language

#### [MODIFY] [evaluations.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/evaluations.py)
- Add **LLM-as-judge** evaluator: "Given the law articles and this question, is the agent's answer legally correct?"
- Add **faithfulness evaluator**: "Does the answer only use information from the retrieved context?"
- Add **retrieval relevance** evaluator: "Are the retrieved articles relevant to the question?"

---

### Phase 4: Production Operations

#### [NEW] `src/logging_config.py`
- Replace all `print()` with structured logging (Python `logging` module)
- Add trace IDs for request tracking

#### [NEW] `src/caching.py`
- Cache embedding API calls (same query = same vector)
- Cache frequent query results with TTL

#### [MODIFY] [database.py](file:///c:/Projects/Projects/UAE%20HR%20%26%20Nafis%20Copilot%20%28RAG%29/src/database.py)
- Add collection versioning (v1, v2...) for reproducibility
- Add health check endpoint

#### [NEW] `.github/workflows/test.yml`
- CI pipeline that runs the test suite on every commit
- Blocks merge if pass rate drops below threshold

---

## Verification Plan

### Automated Tests
1. After Phase 1: Re-run the 19 test cases → pass rate should jump from 47% to 70%+ just by fixing false negatives
2. After Phase 2: Run new retrieval evaluation (`eval_retrieval.py`) → Recall@3 should be > 85%
3. After Phase 3: Run LangSmith suite with LLM-as-judge → semantic accuracy should be > 80%

### Manual Verification
- Test multi-turn conversations (probation → follow-up)
- Test adversarial queries (prompt injection, leading questions)
- Compare answers against the actual PDF law text for 5 random questions
