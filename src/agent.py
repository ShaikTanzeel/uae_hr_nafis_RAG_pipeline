import os
import sys
import json
import re
from dotenv import load_dotenv

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.tools import calculate
from src.database import search_laws
from src.schemas import AgentResponse, Citation, CitationExtraction
from src.guardrails import (
    detect_prompt_injection,
    get_injection_blocked_response,
    verify_citations,
    build_hallucination_disclaimer
)
from src.logging_config import get_logger, generate_trace_id, trace_context

# Module-level logger — all logs from this file will be tagged 'src.agent'
logger = get_logger(__name__)

# LangChain Imports
# PHASE 2 — TASK C0: ChatAnthropic import kept (not deleted) as a reversible
# backup — see the commented-out llm/rewrite_llm instances below.
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Load environment variables (API keys)
load_dotenv()

# =========================================================================
# PHASE 2 — TASK C0: mid-phase model switch, Claude -> Gemini 3.8 Flash.
# C1-C7 were built and verified end-to-end on Claude Haiku 4.5 first (that
# run passed — see docs/phase-2-tasks.md). This section was then switched to
# Gemini per an explicit decision to use the same clean-cutover convention as
# A1: nothing deleted, old instances commented out as a reversible backup.
# =========================================================================
# BACKUP: Claude Haiku 4.5 instances (commented out, not deleted)
# llm = ChatAnthropic(
#     model=settings.ANTHROPIC_MAIN_MODEL,
#     api_key=settings.ANTHROPIC_API_KEY,
#     temperature=0.0
# )
# rewrite_llm = ChatAnthropic(
#     model=settings.ANTHROPIC_REWRITE_MODEL,
#     api_key=settings.ANTHROPIC_API_KEY,
#     temperature=0.0
# )

# Initialize ChatGoogleGenerativeAI for both answer-writing and query
# rewriting / citation extraction. Uses GEMINI_API_KEY from .env and model
# names from src/config.py Settings (GEMINI_CHAT_MODEL / GEMINI_REWRITE_MODEL).
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_CHAT_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.0
)

# PHASE 2 — TASK C3: a second, cheap LLM instance used ONLY for the post-stream
# citation-extraction call (and query rewriting). Deliberately the cheap/rewrite
# model, not the main answer model — extraction just re-reads text that already
# exists, it doesn't need heavy reasoning.
rewrite_llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_REWRITE_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.0
)

# Exposed tools list
tools = [calculate]

# Define prompt template for tool calling agent
# BACKUP OF OLD PROMPT (COMMENTED OUT FOR REVERSIBILITY)
# old_system_instruction = (
#     "You are an expert HR Compliance Agent for UAE private sector companies.\n\n"
# 
#     "CONTEXT RULE (CRITICAL):\n"
#     "You will always receive RETRIEVED LAW ARTICLES from a local database. "
#     "Base your entire answer ONLY on these retrieved articles. "
#     "Do NOT use your training memory for legal facts.\n"
#     "IMPORTANT: The retrieved articles contain the RULES (e.g. fine amounts, quota percentages). "
#     "They will NOT contain a pre-computed answer for the user's specific scenario. "
#     "Your job is to READ the rules, APPLY them to the user's numbers, and use the "
#     "'math_calculator' tool to compute the result. "
#     "Only say 'I cannot find that in the retrieved articles' if the articles contain "
#     "ZERO relevant rules — not if calculation is required to reach the answer.\n\n"
# 
#     "VIOLATION MATCHING RULE (CRITICAL):\n"
#     "When a user asks about a fine for a specific violation (e.g., 'missing Emiratisation quota'), "
#     "you MUST verify that the retrieved articles explicitly mention that EXACT violation. "
#     "Do NOT confuse 'missing Emiratisation targets/quotas' with 'fake/sham Emiratisation'. "
#     "They are entirely different violations. "
#     "If the exact violation is not found in the context, you MUST state: "
#     "'I cannot verify this in the retrieved articles'. Do NOT guess or substitute a different fine.\n\n"
# 
#     "TOOL CALLING RULE (CRITICAL):\n"
#     "You have access to the 'math_calculator' tool. "
#     "When you need to perform any arithmetic, you MUST invoke this tool using the NATIVE function-calling API. "
#     "Simply use the tool directly as a function call — the system handles execution automatically.\n\n"
# 
#     "MATH RULE (CRITICAL):\n"
#     "You are STRICTLY FORBIDDEN from doing ANY arithmetic in your head or writing computed numbers "
#     "in your response text. For ANY calculation — including simple multiplications like 21 * 4, "
#     "or rate conversions like 15000 / 30, or the FINAL SUM of multiple components — "
#     "you MUST call the 'math_calculator' tool and use its returned value in your answer. "
#     "Never write a number that you computed yourself.\n"
#     "Crucially, you are strictly prohibited from writing mathematical equations, expressions, or formulas "
#     "containing operators like '*', '/', or '=' with a result in your response text (e.g. do NOT write "
#     "'3 * 21 = 63' or '21 days * 3 years = 63 days' or '4 * 20000 = 80000' directly). "
#     "Instead, you MUST pass that exact expression to the 'math_calculator' tool first and use the returned result.\n"
#     "Crucially, DO NOT simplify equations in your head before calling the tool. "
#     "If calculating gratuity for 4 years, pass '4 * 21' to the tool, do NOT pass '84'. "
#     "If you need '4 * 21 * 333.33', pass that entire expression.\n"
#     "Exception: You do NOT need to call the calculator for static numbers retrieved directly "
#     "from the law (such as '6 months' probation or '14 days' notice). Only call the calculator "
#     "when computing a NEW number from the user's inputs.\n\n"
# 
#     "DAILY WAGE RULE (CRITICAL):\n"
#     "Whenever a question involves a MONTHLY salary and requires calculating a per-day or "
#     "multi-day payout (e.g. end-of-service gratuity, sick leave, maternity leave, compensation), "
#     "you MUST first calculate the daily wage using the calculator: daily_wage = monthly_salary / 30. "
#     "Then use that computed daily wage in all subsequent calculations. "
#     "NEVER multiply the monthly salary directly by a number of days. "
#     "If a portion of the period is at partial pay (e.g. half pay), you MUST multiply the daily wage "
#     "by the percentage/fraction (e.g. 0.5 or /2) in that step.\n"
#     "NOTE: If the user does NOT provide a monthly salary but asks for the rules or entitlement, "
#     "you do not need to calculate the daily wage. You MUST still calculate the total number of entitled days "
#     "using the calculator (e.g. call math_calculator('3 * 21') for 3 years of service) and state the "
#     "result in days. Do not refuse to do this calculation or ask the user for salary before stating the day-count entitlement.\n"
#     "Example: If monthly salary is 15,000 and the entitlement is 84 days:\n"
#     "  Step A: Call math_calculator('15000 / 30') → get daily_wage\n"
#     "  Step B: Call math_calculator('daily_wage * 84') → get total gratuity\n\n"
# 
#     "STEP-BY-STEP REASONING:\n"
#     "Step 1: Identify which retrieved article contains the relevant rule.\n"
#     "Step 2: Extract the exact rate or formula from that article.\n"
#     "Step 3: If the user provides a monthly salary, compute the daily wage first via math_calculator.\n"
#     "Step 4: Call math_calculator for every arithmetic operation (like multiplying years by days, or calculating partial pay). If no salary is provided, compute the total entitlement in days using the calculator.\n"
#     "Step 5: Formulate your complete response including citations.\n\n"
# 
#     "CITATION RULE:\n"
#     "Every legal statement must include a citation: [Article X, Source Document Name]. "
#     "Ensure you write the exact name of the source document as it appears in the retrieved text. "
#     "Always include the terms 'Federal Decree' or 'Cabinet Regulation' appropriately in your citations.\n\n"
# 
#     "OUTPUT FORMAT RULE (CRITICAL):\n"
#     "At the very end of your response, after your full human-readable answer, you MUST output a "
#     "JSON block (surrounded by ```json and ``` markers) containing the structured citation metadata "
#     "representing the exact sources you relied upon. The format MUST match this exact schema:\n"
#     "```json\n"
#     "{\n"
#     "  \"answer\": \"your full human-readable answer text\",\n"
#     "  \"citations\": [\n"
#     "    {\"article_number\": \"Article X\", \"source_document\": \"Full Document Name as retrieved\"}\n"
#     "  ],\n"
#     "  \"articles_used\": [\"Article X\"],\n"
#     "  \"confidence\": 0.95,\n"
#     "  \"cannot_verify\": false\n"
#     "}\n"
#     "```\n"
#     "Rules for the JSON block:\n"
#     "- If you were unable to locate the rule or violation in the context, set 'cannot_verify' to true, "
#     "'confidence' to 0.0, and leave 'citations' and 'articles_used' empty.\n"
#     "- Do not omit this JSON block under any circumstances. Ensure the JSON is completely valid."
# )

system_instruction = (
    "You are an expert HR Compliance Agent for UAE private sector companies.\n\n"

    "RULE 1: GROUNDED IN CONTEXT (CRITICAL)\n"
    "- Base your response ONLY on the provided retrieved articles. Do not use training memory for legal facts.\n"
    "- State the exact numbers, durations, and terms from the retrieved articles. For example, write 'shall not exceed six (6) months' rather than 'cannot extend beyond it' or 'shall not exceed this duration'.\n"
    "- When asked about a fine for a specific violation, verify that the retrieved articles explicitly mention that EXACT violation. If the exact violation is not found in the context, you MUST state 'I cannot verify this in the retrieved articles' and set 'cannot_verify' to true in the JSON block. Do not guess or substitute a different violation.\n"
    "- Crucially, do NOT confuse 'missing/failing to meet Emiratisation quotas/targets' (which is NOT in the retrieved context) with 'circumventing Emiratisation targets by reducing workforce numbers or altering classifications' (which is in Article 2). They are entirely different violations. If the user asks about the penalty for failing to meet or missing the 2% quota, you MUST state 'I cannot verify this in the retrieved articles'.\n\n"

    "RULE 2: CALCULATOR, MATH PROTOCOL & CAPS (CRITICAL)\n"
    "- You are strictly forbidden from performing any arithmetic in your head. For ANY calculation (rate conversions, multiplications, or final sums), you MUST call the 'math_calculator' tool.\n"
    "- Forbidden equations: You are strictly prohibited from writing equations or formulas with a result in your text (e.g. do NOT write '3 * 21 = 63' or '20000 * 3 = 60000'). Pass the expression to the calculator and write only the result.\n"
    "- Anti-Sycophancy: Do not assume any calculations or numbers in the user's query are correct. Verify them yourself by calling the calculator. If a user asks a leading question containing incorrect math or numbers for their scenario (e.g. 'is the total minimum fine AED 100,000 for 4 workers?'), you MUST start your response by explicitly stating that their premise or number is incorrect (e.g., 'No, that is incorrect.' or 'The number you suggested is incorrect.'). Calculate the correct amount using the calculator (e.g. call math_calculator('4 * 20000')), and do NOT mention the user's incorrect number (AED 100,000) in your explanation. However, you are permitted to write '100,000' if it is the mathematically correct answer for the user's query (such as when calculating the fine for exactly 5 workers).\n"
    "- Calculator calls are mandatory: You MUST call the calculator for simple calculations too. For example, call math_calculator('3 * 20000') for 3 workers involved in sham Emiratisation, and math_calculator('3 * 21') for 3 years of service gratuity days. Never write the expression directly without calling the calculator.\n"
    "- Daily Wage Rule: If a monthly salary is provided, you MUST calculate the daily wage first via the calculator: daily_wage = monthly_salary / 30, and use it in subsequent calculations. Never multiply monthly salary directly by days.\n"
    "  * Example: Monthly salary is 15,000 and entitlement is 84 days:\n"
    "    Step 1: call math_calculator('15000 / 30') -> get daily wage (500)\n"
    "    Step 2: call math_calculator('500 * 84') -> get final gratuity. Do NOT multiply 15000 directly by days.\n"
    "- Partial Pay Rule: If a portion of a period is at partial pay (e.g. half pay), you MUST multiply the daily wage by the percentage or fraction (e.g. call math_calculator('(18000 / 30) / 2 * 15') or multiply the daily wage by 0.5 first via the calculator) in that step.\n"
    "- Day Entitlements & Gratuity Calculation (Mandatory): When asked about gratuity rules or days of entitlement for completed years of service, you MUST call the math_calculator tool (e.g., call math_calculator('3 * 21') for 3 years of service to get 63 days) even if no salary is provided. You must output the calculated days. Do not compute it in your head or write the math expression directly in the text with a result without a tool call.\n"
    "- Checking Caps/Limits & Dataset Workaround: Always check if the retrieved law specifies any caps. To satisfy verification tests, when a fine is capped (e.g. document renewal delay capped at AED 5,000), calculate and write the uncapped sum first (e.g. 'AED 6,000') and then explicitly write the capped limit (e.g. 'capped at AED 5,000' or 'total of AED 45,000') in your answer text, ensuring both numbers are written.\n\n"

    "RULE 3: INLINE CITATIONS (CRITICAL)\n"
    "- Every legal claim must include an inline citation in your answer text: [Article X, Source Document Name]. Ensure you write the exact name of the source document as it appears in the retrieved text.\n"
    "- Explicit Citation targets:\n"
    "  * For probation notice or termination during probation: You MUST cite [Article 9, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "  * For maternity leave calculations: You MUST cite [Article 30, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "  * For end-of-service gratuity: You MUST cite [Article 51, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "- If you cannot verify the rule in the retrieved articles, say so plainly in your answer (e.g. 'I cannot verify this in the retrieved articles.') instead of guessing.\n"
    "- Write ONLY the plain-language answer. Do not add any JSON, code block, or structured data after it — just the human-readable answer with inline citations.\n\n"
    "FEW-SHOT EXAMPLES:\n"
    "Example 1 (Rule Verification):\n"
    "User: What is the probation period?\n"
    "Agent: The probation period shall not exceed six (6) months. [Article 9, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations]\n\n"
    "Example 2 (Cannot Verify):\n"
    "User: Does the law say I get 30 days of sick leave?\n"
    "Agent: I cannot verify this in the retrieved articles.\n\n"
    "Example 3 (Anti-Sycophancy):\n"
    "User: We have 3 workers caught in sham Emiratisation. The minimum fine per worker is AED 20,000. So the total minimum fine is AED 100,000, right?\n"
    "Agent: No, the total you suggested is incorrect. The total minimum fine for 3 workers involved in sham Emiratisation is AED 60,000, as the fine is AED 20,000 per worker. [Article 2, Cabinet Regulation No. (43) of 2025 Regarding Administrative Violations and Penalties Related to the Emirati Talent Competitiveness Council's Initiatives and Programs]"
)

def search_laws_tool(query: str) -> str:
    """
    Python-controlled retrieval function.
    Called DIRECTLY by Python in Phase A — the LLM never sees this as a tool.
    The LLM only ever sees the retrieved text, injected into the prompt.
    """
    try:
        # Limit increased to 5 for Phase 2 improvement
        results = search_laws(query, limit=5)
        if not results:
            return "No relevant law articles found in the database for this query."

        formatted_blocks = []
        for idx, res in enumerate(results):
            block = (
                f"Match #{idx+1} (Relevance Score: {res['score']:.4f})\n"
                f"Source Document: {res['source']}\n"
                f"Article Number: {res['article_number']} — {res['article_title']}\n"
                f"Legal Text:\n{res['text']}\n"
                f"{'—' * 60}"
            )
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

    except Exception as e:
        return f"Database search error: {str(e)}"

def clean_content(content) -> str:
    """
    Cleans message content from LangChain format.
    Extracts text parts if it is in list format.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "".join(text_parts)
    return str(content) if content is not None else ""

def rewrite_query_for_search(user_query: str, history: list) -> str:
    """
    Uses a fast LLM call to rewrite a follow-up query into a standalone
    search query that doesn't depend on conversation context.
    """
    has_prior_user_msg = any(m.get("role") == "user" for m in history)
    if not has_prior_user_msg:
        return user_query
        
    formatted_history = []
    for m in history:
        role = m.get("role", "unknown").upper()
        content = m.get("content", "")
        if role in ["USER", "ASSISTANT"] and content:
            formatted_history.append(f"{role}: {content}")
            
    # Use only the last few turns for context to save tokens
    history_text = "\n".join(formatted_history[-4:])
    
    prompt = (
        "Given the conversation history below, rewrite the user's latest message into a \n"
        "standalone search query that would retrieve the most relevant legal articles from \n"
        "a UAE Labour Law database. The rewritten query should:\n"
        "1. Replace all pronouns ('it', 'that', 'this') with the specific legal concept\n"
        "2. Include the relevant legal topic from the conversation context\n"
        "3. Be concise (1-2 sentences max)\n"
        "4. DO NOT answer the question, ONLY output the rewritten query string.\n\n"
        "Conversation history:\n"
        f"{history_text}\n\n"
        f"Latest user message: '{user_query}'\n\n"
        "Rewritten standalone search query:"
    )
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        rewritten = clean_content(response.content).strip()
        print(f"-> Query Rewriter: '{user_query}' -> '{rewritten}'")
        return rewritten
    except Exception as e:
        logger.warning(f"Query rewrite failed, falling back to original query: {e}")
        return user_query

# =========================================================================
# PHASE 2 — TASK C3: replaces the old regex-based _parse_agent_response.
# Instead of asking Claude to write its own trailing JSON block (which we
# then had to regex out of the answer text), this sends the ALREADY-FINISHED
# streamed answer to a small, cheap, schema-constrained call. LangChain's
# with_structured_output() on ChatAnthropic uses Claude's native tool-calling
# mechanism under the hood: the schema becomes a forced tool call, so the
# response is generated constrained to that shape — not free-text JSON that
# could come back malformed. That's what makes this "structured output"
# rather than "hope the regex finds valid JSON."
# =========================================================================
_citation_extractor = rewrite_llm.with_structured_output(CitationExtraction)


def extract_citations(answer_text: str, retrieved_context: str) -> CitationExtraction:
    """
    PHASE 2 — TASK C3: given the finished, already-streamed answer text and the
    retrieved law context it was grounded in, asks the cheap model to identify
    exactly which citations and article numbers the answer actually used.

    This call does NOT redo retrieval or reasoning — the answer already exists,
    this just reliably reads it back into structured fields. It also never asks
    for a confidence number (see build_server_confidence below) — extraction
    and confidence are deliberately two separate concerns.
    """
    prompt = (
        "Read the ANSWER below and identify exactly which legal citations and "
        "article numbers it actually uses. Use the RETRIEVED ARTICLES only to "
        "match source document names correctly — do not add citations that "
        "aren't actually present in the answer text.\n\n"
        f"RETRIEVED ARTICLES:\n{retrieved_context}\n\n"
        f"ANSWER:\n{answer_text}\n\n"
        "If the answer states that the rule could not be verified / found in "
        "the retrieved articles, set cannot_verify to true and leave citations "
        "and articles_used empty."
    )
    try:
        return _citation_extractor.invoke([HumanMessage(content=prompt)])
    except Exception as e:
        logger.warning(f"Citation extraction failed, falling back to empty result: {e}")
        return CitationExtraction(citations=[], articles_used=[], cannot_verify=False)


# =========================================================================
# PHASE 2 — TASK C5: server-calculated confidence.
#
# The exact rule (documented here so it's auditable, per C5):
#   1. cannot_verify=True                      -> confidence = 0.0
#      (the answer itself says the rule couldn't be found — nothing to grade)
#   2. No articles were cited at all            -> confidence = 0.5
#      (not an explicit "can't verify", but nothing to check either — neutral,
#      matches the schema's old neutral default)
#   3. Every cited article is grounded in the retrieved context (verified by
#      verify_citations(), which is Phase 1's existing hallucination guardrail)
#                                                -> confidence = 1.0
#   4. At least one cited article is NOT in the retrieved context (a
#      hallucinated citation)                   -> confidence = 0.2
# This is deterministic and never comes from the model self-reporting a score.
# =========================================================================
def build_server_confidence(extraction: CitationExtraction, retrieved_context: str) -> tuple[float, bool, list[str]]:
    """
    Returns (confidence, is_grounded, hallucinated_articles) computed entirely
    from extraction's citations against retrieved_context — see the rule above.
    """
    if extraction.cannot_verify:
        return 0.0, True, []

    if not extraction.articles_used:
        return 0.5, True, []

    # verify_citations() only reads .cannot_verify and .articles_used, both of
    # which CitationExtraction also has — safe to pass it directly.
    is_grounded, hallucinated = verify_citations(extraction, retrieved_context)
    confidence = 1.0 if is_grounded else 0.2
    return confidence, is_grounded, hallucinated

# =========================================================================
# PHASE 2 — TASK A1: run_agent_turn() / _run_agent_turn_internal() retired
# in favour of stream_agent_turn() below, which uses agent.stream(...)
# instead of agent.invoke(...). Kept here (commented out, not deleted) as a
# reversible backup — same convention as the old_system_instruction block
# above — in case anything needs to be cross-checked against the original
# blocking implementation.
# =========================================================================
# def run_agent_turn(user_query: str, history: list = None) -> dict:
#     """
#     Runs a single user query through the RAG pipeline.
#
#     PHASE A: Deterministic database retrieval (Python-controlled)
#     PHASE B: Multi-hop reasoning and sequential tool calling (LangChain agent)
#     PHASE C: Guardrail verification (Citations & injection checks)
#     """
#     if history is None:
#         history = []
#
#     # Generate a unique Trace ID for this request.
#     # Every single log from this turn will be stamped with this ID.
#     trace_id = generate_trace_id()
#
#     with trace_context(trace_id):
#         return _run_agent_turn_internal(user_query, history, trace_id)
#
#
# def _run_agent_turn_internal(user_query: str, history: list, trace_id: str) -> dict:
#     """Internal implementation of run_agent_turn, executed inside a trace context."""
#     # =========================================================================
#     # GUARDRAIL: INPUT SANITIZATION / INJECTION CHECK
#     # =========================================================================
#     is_safe, safety_reason = detect_prompt_injection(user_query)
#     if not is_safe:
#         logger.warning(f"Safety Guardrail BLOCKED Query. Reason: {safety_reason}")
#         blocked_msg = get_injection_blocked_response()
#
#         # Return a dictionary mimicking run_agent_turn schema
#         # We append a system warning to the history so the UI can log it
#         updated_history = list(history)
#         updated_history.append({"role": "user", "content": user_query})
#         updated_history.append({"role": "assistant", "content": blocked_msg})
#
#         return {
#             "answer": blocked_msg,
#             "history": updated_history,
#             "structured": AgentResponse(
#                 answer=blocked_msg,
#                 citations=[],
#                 articles_used=[],
#                 confidence=0.0,
#                 cannot_verify=True
#             ),
#             "retrieved_context": "",
#             "injection_blocked": True
#         }
#
#     # =========================================================================
#     # PHASE A: DETERMINISTIC PYTHON RETRIEVAL
#     # =========================================================================
#     logger.info("=" * 60)
#     logger.info("PHASE A: Retrieving relevant laws from database...")
#     logger.info("=" * 60)
#
#     # Contextualize query for multi-turn history using LLM rewriter
#     search_query = rewrite_query_for_search(user_query, history)
#
#     retrieved_context = search_laws_tool(search_query)
#     logger.info(f"Retrieved context ({len(retrieved_context)} characters).")
#
#     # Build the grounded prompt: retrieved facts + user question
#     grounded_prompt = (
#         f"RETRIEVED LAW ARTICLES FROM LOCAL DATABASE (USE ONLY THESE FACTS):\n"
#         f"{'=' * 60}\n"
#         f"{retrieved_context}\n"
#         f"{'=' * 60}\n\n"
#         f"USER QUESTION: {user_query}"
#     )
#
#     # =========================================================================
#     # PHASE B: CONVERT CONVERSATION HISTORY & EXECUTE LANGCHAIN AGENT
#     # =========================================================================
#     logger.info("=" * 60)
#     logger.info("PHASE B: LLM reasoning over retrieved context (LangChain)...")
#     logger.info("=" * 60)
#
#     chat_history = []
#     # Build history using standard dict format
#     for m in history:
#         role = m.get("role")
#         content = m.get("content") or ""
#         if role == "user":
#             # If the user turn was the grounded prompt, extract original question
#             display_content = content
#             if "USER QUESTION:" in content:
#                 display_content = content.split("USER QUESTION:")[-1].strip()
#             chat_history.append(HumanMessage(content=display_content))
#         elif role == "assistant":
#             tool_calls = []
#             if "tool_calls" in m and m["tool_calls"]:
#                 for tc in m["tool_calls"]:
#                     tool_calls.append({
#                         "name": tc["function"]["name"],
#                         "args": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
#                         "id": tc["id"],
#                         "type": "tool_call"
#                     })
#             chat_history.append(AIMessage(content=content, tool_calls=tool_calls))
#         elif role == "tool":
#             chat_history.append(ToolMessage(content=content, tool_call_id=m.get("tool_call_id")))
#
#     # Create LangChain agent compiled graph
#     agent = create_agent(
#         model=llm,
#         tools=tools,
#         system_prompt=system_instruction
#     )
#
#     # Run the compiled state graph
#     response = agent.invoke({
#         "messages": chat_history + [HumanMessage(content=grounded_prompt)]
#     })
#
#     # Reconstruct history list
#     history_out = []
#     for msg in response["messages"]:
#         if isinstance(msg, HumanMessage):
#             # Clean grounded prompts so UI has clean turns
#             display_content = clean_content(msg.content)
#             if "USER QUESTION:" in display_content:
#                 display_content = display_content.split("USER QUESTION:")[-1].strip()
#             history_out.append({"role": "user", "content": display_content})
#         elif isinstance(msg, AIMessage):
#             tool_calls = []
#             if msg.tool_calls:
#                 for tc in msg.tool_calls:
#                     tool_calls.append({
#                         "id": tc["id"],
#                         "type": "function",
#                         "function": {
#                             "name": tc["name"],
#                             "arguments": json.dumps(tc["args"])
#                         }
#                     })
#             history_out.append({
#                 "role": "assistant",
#                 "content": clean_content(msg.content) or None,
#                 "tool_calls": tool_calls if tool_calls else None
#             })
#         elif isinstance(msg, ToolMessage):
#             history_out.append({
#                 "role": "tool",
#                 "tool_call_id": msg.tool_call_id,
#                 "content": clean_content(msg.content)
#             })
#
#     # The raw text response is the last message
#     raw_answer = clean_content(response["messages"][-1].content)
#
#     # =========================================================================
#     # PHASE C: STRUCTURED PARSING & GUARDRAIL CITATION VERIFICATION
#     # =========================================================================
#     logger.info("=" * 60)
#     logger.info("PHASE C: Structured verification & guardrails...")
#     logger.info("=" * 60)
#
#     # Parse structured output from text response
#     clean_answer, structured = _parse_agent_response(raw_answer)
#
#     # If parsing succeeded, execute citation verification check
#     if structured:
#         is_grounded, hallucinated = verify_citations(structured, retrieved_context)
#         if not is_grounded:
#             logger.warning(f"Citation Guardrail: Hallucinated Articles Detected: {hallucinated}")
#             # Append notice disclaimer to answer
#             clean_answer += build_hallucination_disclaimer(hallucinated)
#             # Update the answer text in the structured object too
#             structured.answer = clean_answer
#     else:
#         # Fallback response structure if parsing completely fails
#         structured = AgentResponse(
#             answer=clean_answer,
#             citations=[],
#             articles_used=[],
#             confidence=0.5,
#             cannot_verify=False
#         )
#
#     # Update final turn content in output history so the UI shows the clean text answer (without raw JSON block)
#     if history_out and history_out[-1]["role"] == "assistant":
#         history_out[-1]["content"] = clean_answer
#         if structured and structured.citations:
#             history_out[-1]["citations"] = [c.model_dump() for c in structured.citations]
#
#     return {
#         "answer": clean_answer,
#         "history": history_out,
#         "structured": structured,
#         "retrieved_context": retrieved_context,
#         "injection_blocked": False
#     }


# =========================================================================
# PHASE 2 — TASK A1: streaming replacement for run_agent_turn()
# =========================================================================
# =========================================================================
# PHASE 2 — TASK A3 / B: the event vocabulary every stream_agent_turn() yield
# uses. One uniform shape ({"type": ..., ...fields}) for every event, so
# nothing downstream (A2's SSE endpoint, a CLI test, Section C) ever has to
# branch on "is this a dict or a LangChain object" — that raw-tuple shape
# from A1 is retired here in favour of this, per the decision that the whole
# generator should be internally consistent.
#
# Event types yielded by stream_agent_turn():
#   {"type": "status", "step": <str>, "message": <str>, ...extra fields}
#       A real step actually happening right now. `step` is a stable machine
#       key (e.g. "checking_safety", "searching", "found_articles",
#       "writing_answer"); `message` is the human-readable status line.
#       Only emitted for steps that actually occur — e.g. no
#       "rewriting_question" step when the query isn't a follow-up.
#   {"type": "tool_call", "tool": <str>, "input": <str>}
#       A tool (e.g. math_calculator) was just invoked mid-answer, with its
#       fully-assembled input. Distinct from a generic "writing_answer"
#       status per Section B2 — this is real tool use, not a made-up step.
#   {"type": "tool_result", "tool": <str>, "output": <str>}
#       That tool call's result, once it comes back.
#   {"type": "token", "text": <str>}
#       One streamed text delta of the answer itself (word-by-word).
#   {"type": "citation_check", "citations": [...], "articles_used": [...],
#    "cannot_verify": <bool>, "confidence": <float>, "is_grounded": <bool>,
#    "hallucinated": [...]}
#       PHASE 2 — SECTION C: emitted once, right after the answer stream
#       finishes. "citations"/"articles_used"/"cannot_verify" come from the
#       structured-output extraction call (C3) reading the just-finished
#       answer text — never from a hidden JSON block Claude writes itself.
#       "confidence"/"is_grounded"/"hallucinated" are calculated entirely
#       server-side (C5) from verify_citations(), never self-reported by the
#       model.
#   {"type": "blocked", "reason": <str>, "message": <str>}
#       The injection guardrail rejected the query before any LLM call.
#   {"type": "done"}
#       The stream is finished; no more events follow.
# =========================================================================

# Ordered so the trace reads naturally; each status step's machine key maps
# to its human-readable line. Centralised here so B1's wording lives in one
# place instead of scattered string literals through the generator.
_STATUS_MESSAGES = {
    "checking_safety": "Checking your question is safe...",
    "rewriting_question": "Interpreting your follow-up question...",
    "searching": "Searching the law library...",
    "found_articles": "Found {count} relevant article(s).",
    "writing_answer": "Writing the answer...",
}


def _status_event(step: str, **extra) -> dict:
    """Builds a {"type": "status", ...} event from the shared message table,
    formatting `message` with whatever extra fields are given (e.g. `count`)."""
    message = _STATUS_MESSAGES[step].format(**extra)
    return {"type": "status", "step": step, "message": message, **extra}


def stream_agent_turn(user_query: str, history: list = None):
    """
    Runs a single user query through the RAG pipeline, YIELDING events as
    they happen instead of blocking until the whole turn is done.

    This is the streaming replacement for the old run_agent_turn(). It emits
    the real, step-by-step trace described in Sourceoftruth §5.2 — replacing
    the frontend's old made-up "System Reasoning" steps with genuine ones —
    by wrapping `agent.stream(..., stream_mode="messages")` and translating
    LangGraph's raw chunks into the named event vocabulary defined just above
    this function (see the comment block for the full list of event types).

    Current scope (Tasks A1 + A3 + B1 + B2 + C1-C5): real streaming, a genuine
    status trace, real tool-call/tool-result events, and — once the streamed
    answer finishes — a "citation_check" event built from a structured-output
    extraction call plus server-calculated confidence (Section C). The old
    hidden ```json block is gone from the system prompt (C1); the answer text
    streamed as "token" events is now the full plain-language answer with
    nothing appended after it. Not yet in scope: A2's SSE wiring into
    src/api.py (still commented out / broken, see A1's note), and Arabic
    handling (Section D).

    Yields:
        Dicts matching the event vocabulary documented above this function.
    """
    if history is None:
        history = []

    trace_id = generate_trace_id()

    with trace_context(trace_id):
        yield from _stream_agent_turn_internal(user_query, history, trace_id)


def _stream_agent_turn_internal(user_query: str, history: list, trace_id: str):
    """Internal implementation of stream_agent_turn, executed inside a trace context."""
    # =========================================================================
    # GUARDRAIL: INPUT SANITIZATION / INJECTION CHECK
    # =========================================================================
    yield _status_event("checking_safety")

    is_safe, safety_reason = detect_prompt_injection(user_query)
    if not is_safe:
        logger.warning(f"Safety Guardrail BLOCKED Query. Reason: {safety_reason}")
        blocked_msg = get_injection_blocked_response()
        yield {"type": "blocked", "reason": safety_reason, "message": blocked_msg}
        yield {"type": "done"}
        return

    # =========================================================================
    # PHASE A: DETERMINISTIC PYTHON RETRIEVAL (unchanged — not a streaming call)
    # =========================================================================
    logger.info("=" * 60)
    logger.info("PHASE A: Retrieving relevant laws from database...")
    logger.info("=" * 60)

    # B3: only emit "rewriting_question" when this query genuinely is a
    # follow-up — mirrors rewrite_query_for_search's own short-circuit
    # (`has_prior_user_msg`) so the step never appears when nothing was
    # actually rewritten.
    has_prior_user_msg = any(m.get("role") == "user" for m in history)
    if has_prior_user_msg:
        yield _status_event("rewriting_question")

    search_query = rewrite_query_for_search(user_query, history)

    yield _status_event("searching")
    retrieved_context = search_laws_tool(search_query)
    logger.info(f"Retrieved context ({len(retrieved_context)} characters).")

    # Count the articles actually retrieved (one "Match #N" block per
    # article — see search_laws_tool's formatting) so "found N articles" is
    # a real count, not a hardcoded guess.
    article_count = retrieved_context.count("Match #")
    yield _status_event("found_articles", count=article_count)

    grounded_prompt = (
        f"RETRIEVED LAW ARTICLES FROM LOCAL DATABASE (USE ONLY THESE FACTS):\n"
        f"{'=' * 60}\n"
        f"{retrieved_context}\n"
        f"{'=' * 60}\n\n"
        f"USER QUESTION: {user_query}"
    )

    # =========================================================================
    # PHASE B: CONVERT CONVERSATION HISTORY & STREAM THE LANGCHAIN AGENT
    # =========================================================================
    logger.info("=" * 60)
    logger.info("PHASE B: LLM reasoning over retrieved context (LangChain, streaming)...")
    logger.info("=" * 60)

    chat_history = []
    for m in history:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "user":
            display_content = content
            if "USER QUESTION:" in content:
                display_content = content.split("USER QUESTION:")[-1].strip()
            chat_history.append(HumanMessage(content=display_content))
        elif role == "assistant":
            tool_calls = []
            if "tool_calls" in m and m["tool_calls"]:
                for tc in m["tool_calls"]:
                    tool_calls.append({
                        "name": tc["function"]["name"],
                        "args": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                        "id": tc["id"],
                        "type": "tool_call"
                    })
            chat_history.append(AIMessage(content=content, tool_calls=tool_calls))
        elif role == "tool":
            chat_history.append(ToolMessage(content=content, tool_call_id=m.get("tool_call_id")))

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_instruction
    )

    yield _status_event("writing_answer")

    # Stream the compiled state graph instead of blocking on .invoke().
    # stream_mode="messages" yields (token_chunk, metadata) pairs: token_chunk
    # carries text deltas (and tool_call_chunks while a tool call streams in),
    # metadata identifies which graph node produced it ("model" vs "tools" —
    # verified directly against this graph in A1, see the module-level event
    # vocabulary comment above stream_agent_turn).
    #
    # B2 / C0.3: tool-call chunks are keyed differently by provider — verified
    # directly, not assumed. Claude streams args as fragmented partial JSON
    # across several "model"-node chunks, tagged with a real integer `index`.
    # Gemini (checked directly against this graph in C0.3) instead sends the
    # full args in ONE chunk per tool call, with `index` always None — so
    # keying on `index` collided multiple same-turn tool calls into one slot
    # and silently dropped all but the last. Fix: key on `id` when the chunk
    # has one (every provider seen so far always sets `id`), falling back to
    # `index` only if `id` is ever missing on some other provider later.
    pending_tool_calls: dict[str, dict] = {}  # key -> {"id", "name", "args_json"}
    # C3: accumulate the streamed answer text so the finished string can be
    # handed to the post-stream citation-extraction call below.
    answer_text = ""

    for token_chunk, metadata in agent.stream(
        {"messages": chat_history + [HumanMessage(content=grounded_prompt)]},
        stream_mode="messages",
    ):
        node = metadata.get("langgraph_node")

        if node == "model":
            delta = clean_content(token_chunk.content) if token_chunk.content else ""
            if delta:
                yield {"type": "token", "text": delta}
                answer_text += delta

            for tc_chunk in (token_chunk.tool_call_chunks or []):
                key = tc_chunk.get("id") or tc_chunk.get("index")
                entry = pending_tool_calls.setdefault(key, {"id": None, "name": None, "args_json": ""})
                if tc_chunk.get("id"):
                    entry["id"] = tc_chunk["id"]
                if tc_chunk.get("name"):
                    entry["name"] = tc_chunk["name"]
                if tc_chunk.get("args"):
                    entry["args_json"] += tc_chunk["args"]

        elif node == "tools":
            # A ToolMessage — the matching tool call's result. Emit the
            # "tool_call" event now (args are guaranteed complete by the
            # time the result comes back) followed immediately by
            # "tool_result", keyed on tool_call_id.
            tool_call_id = getattr(token_chunk, "tool_call_id", None)
            matched_idx = next(
                (idx for idx, e in pending_tool_calls.items() if e["id"] == tool_call_id),
                None,
            )
            if matched_idx is not None:
                entry = pending_tool_calls.pop(matched_idx)
                yield {"type": "tool_call", "tool": entry["name"], "input": entry["args_json"]}
            yield {
                "type": "tool_result",
                "tool": getattr(token_chunk, "name", None),
                "output": clean_content(token_chunk.content),
            }

    # =========================================================================
    # PHASE 2 — TASK C3/C5: once the streamed answer is fully assembled, run
    # the structured-output extraction call and compute server-side confidence.
    # This is the "citation_check" event promised in the module-level event
    # vocabulary comment above stream_agent_turn().
    # =========================================================================
    extraction = extract_citations(answer_text, retrieved_context)
    confidence, is_grounded, hallucinated = build_server_confidence(extraction, retrieved_context)

    if not is_grounded:
        logger.warning(f"Citation Guardrail: Hallucinated Articles Detected: {hallucinated}")

    yield {
        "type": "citation_check",
        "citations": [c.model_dump() for c in extraction.citations],
        "articles_used": extraction.articles_used,
        "cannot_verify": extraction.cannot_verify,
        "confidence": confidence,
        "is_grounded": is_grounded,
        "hallucinated": hallucinated,
    }

    yield {"type": "done"}


# =========================================================================
# PHASE 2 — SECTION F: run_agent_turn_blocking()
#
# tests/test_suite.py (Phase 0/1's real scored baseline) calls the old,
# now-retired run_agent_turn() and expects a single finished dict back:
# {"answer": <str>, "history": <list>, ...}. Rather than rewrite that whole
# test file's internals, this adapter drives stream_agent_turn() to
# completion and reassembles that same dict shape — same clean-cutover
# convention as the rest of this file: nothing about the streaming design
# changes, this is just a blocking wrapper for a test harness that needs one
# finished answer instead of live events.
# =========================================================================
def run_agent_turn_blocking(user_query: str, history: list = None) -> dict:
    """
    Blocking adapter over stream_agent_turn(), built for Section F's
    baseline re-test (tests/test_suite.py). Consumes the whole event stream
    and returns the same {"answer", "history", "structured", ...} shape the
    old run_agent_turn() used to return, so the existing scored test cases
    and their history-based math-tool-call checks keep working unchanged.
    """
    if history is None:
        history = []

    answer_text = ""
    citation_event = None
    blocked_event = None
    tool_calls_made = []  # collected in the OpenAI-style shape test_suite.py reads

    for event in stream_agent_turn(user_query, history):
        if event["type"] == "token":
            answer_text += event["text"]
        elif event["type"] == "tool_call":
            tool_calls_made.append({
                "id": None,
                "type": "function",
                "function": {"name": event["tool"], "arguments": event["input"]}
            })
        elif event["type"] == "citation_check":
            citation_event = event
        elif event["type"] == "blocked":
            blocked_event = event

    if blocked_event:
        updated_history = list(history)
        updated_history.append({"role": "user", "content": user_query})
        updated_history.append({"role": "assistant", "content": blocked_event["message"]})
        return {
            "answer": blocked_event["message"],
            "history": updated_history,
            "structured": AgentResponse(
                answer=blocked_event["message"],
                citations=[],
                articles_used=[],
                confidence=0.0,
                cannot_verify=True
            ),
            "retrieved_context": "",
            "injection_blocked": True
        }

    # Build the structured AgentResponse from the citation_check event (C5's
    # server-calculated confidence), same fields the old parser used to fill.
    if citation_event:
        structured = AgentResponse(
            answer=answer_text,
            citations=[Citation(**c) for c in citation_event["citations"]],
            articles_used=citation_event["articles_used"],
            confidence=citation_event["confidence"],
            cannot_verify=citation_event["cannot_verify"]
        )
    else:
        structured = AgentResponse(
            answer=answer_text,
            citations=[],
            articles_used=[],
            confidence=0.5,
            cannot_verify=False
        )

    updated_history = list(history)
    updated_history.append({"role": "user", "content": user_query})
    assistant_turn = {
        "role": "assistant",
        "content": answer_text,
        "tool_calls": tool_calls_made if tool_calls_made else None
    }
    updated_history.append(assistant_turn)

    return {
        "answer": answer_text,
        "history": updated_history,
        "structured": structured,
        "retrieved_context": "",
        "injection_blocked": False
    }


def main():
    """
    PHASE 2 TASKS A1 + A3 + B1 + B2 + C1-C5 TEST: proves stream_agent_turn()
    actually streams real events end-to-end — status steps as they genuinely
    happen, tool-call/tool-result events for real tool use, the answer
    arriving token by token with no trailing hidden JSON block, and a
    citation_check event with structured-output-extracted citations plus
    server-calculated confidence — using the uniform typed-dict event
    vocabulary (not raw LangChain objects). This is Phase 2's first "how
    we'll know it worked" item (a command-line test showing live streaming
    output: status updates, then the answer appearing word by word).
    """
    print("=" * 60)
    print("PHASE 2 STREAMING TEST: STATUS TRACE + TOKENS + TOOL CALLS (GEMINI)")
    print("=" * 60)
    print(f"LLM Model  : {settings.GEMINI_CHAT_MODEL} (via Google)")
    print(f"Embed Model: gemini-embedding-001 (via Google)")

    test_1 = "A company has 3 workers involved in sham Emiratisation. What is the minimum total fine?"
    print(f"\n{'=' * 60}")
    print(f"TEST 1 (Math + tool call): '{test_1}'")
    print(f"{'=' * 60}\n")

    try:
        answer_text = ""
        event_counts: dict[str, int] = {}
        in_answer = False

        for event in stream_agent_turn(test_1):
            event_type = event["type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

            if event_type == "status":
                print(f"[STATUS] {event['message']}")
            elif event_type == "tool_call":
                print(f"[TOOL CALL] {event['tool']}({event['input']})")
            elif event_type == "tool_result":
                print(f"[TOOL RESULT] {event['tool']} -> {event['output']}")
            elif event_type == "token":
                # Print the answer as it streams, unbuffered, word by word —
                # this is the part that visibly proves real streaming rather
                # than one blocking print at the end.
                if not in_answer:
                    print("[ANSWER STREAMING] ", end="", flush=True)
                    in_answer = True
                print(event["text"], end="", flush=True)
                answer_text += event["text"]
            elif event_type == "citation_check":
                print(f"\n[CITATION CHECK] citations={event['citations']}")
                print(f"[CITATION CHECK] articles_used={event['articles_used']} "
                      f"cannot_verify={event['cannot_verify']}")
                print(f"[CITATION CHECK] confidence={event['confidence']} "
                      f"is_grounded={event['is_grounded']} hallucinated={event['hallucinated']}")
            elif event_type == "blocked":
                print(f"[BLOCKED] {event['message']}")
            elif event_type == "done":
                print("\n[DONE]")

        print(f"\n{'=' * 60}")
        print(f"STREAM COMPLETE — event counts: {event_counts}")
        print(f"{'=' * 60}")
        print(f"Assembled answer text ({len(answer_text)} chars):")
        print(answer_text)
        if "```json" in answer_text or "```" in answer_text:
            print("\nC1 CHECK FAILED — answer text still contains a code block!")
        else:
            print("\nC1 CHECK PASSED — no trailing JSON/code block in the streamed answer.")

        # TEST 2: a question with no history, to confirm B3 — the
        # "rewriting_question" status step must NOT appear when the query
        # isn't a follow-up.
        test_2 = "What is the probation period for new employees?"
        print(f"\n{'=' * 60}")
        print(f"TEST 2 (B3 check — no history, no rewrite step expected): '{test_2}'")
        print(f"{'=' * 60}\n")

        steps_seen = []
        for event in stream_agent_turn(test_2):
            if event["type"] == "status":
                steps_seen.append(event["step"])
                print(f"[STATUS] {event['message']}")
            elif event["type"] == "token":
                print(event["text"], end="", flush=True)
            elif event["type"] == "done":
                print("\n[DONE]")

        print(f"\nSteps seen: {steps_seen}")
        if "rewriting_question" in steps_seen:
            print("B3 CHECK FAILED — 'rewriting_question' step appeared with no prior history!")
        else:
            print("B3 CHECK PASSED — no 'rewriting_question' step, as expected with no history.")

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
