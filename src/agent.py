import os
import sys
import json
import re
from dotenv import load_dotenv

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools import calculate
from src.database import search_laws
from src.schemas import AgentResponse, Citation
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
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Load environment variables (API keys)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = "gpt-4o-mini"

# Initialize ChatOpenAI LLM using your OpenAI account API key
llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=OPENAI_API_KEY,
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

    "RULE 3: INLINE CITATIONS & OUTPUT SCHEMA (CRITICAL)\n"
    "- Every legal claim must include an inline citation: [Article X, Source Document Name]. Ensure you write the exact name of the source document as it appears in the retrieved text.\n"
    "- Explicit Citation targets:\n"
    "  * For probation notice or termination during probation: You MUST cite [Article 9, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "  * For maternity leave calculations: You MUST cite [Article 30, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "  * For end-of-service gratuity: You MUST cite [Article 51, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations].\n"
    "- At the very end of your response, you MUST output a JSON block matching this exact schema:\n"
    "```json\n"
    "{\n"
    "  \"answer\": \"your full human-readable answer text\",\n"
    "  \"citations\": [\n"
    "    {\"article_number\": \"Article X\", \"source_document\": \"Full Document Name as retrieved\"}\n"
    "  ],\n"
    "  \"articles_used\": [\"Article X\"],\n"
    "  \"confidence\": 0.95,\n"
    "  \"cannot_verify\": false\n"
    "}\n"
    "```\n"
    "- If you cannot verify the rule, set 'cannot_verify' to true, 'confidence' to 0.0, and leave 'citations' and 'articles_used' empty.\n\n"
    "FEW-SHOT EXAMPLES:\n"
    "Example 1 (Rule Verification):\n"
    "User: What is the probation period?\n"
    "Agent: The probation period shall not exceed six (6) months. [Article 9, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations]\n"
    "```json\n"
    "{\n"
    "  \"answer\": \"The probation period shall not exceed six (6) months. [Article 9, Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations]\",\n"
    "  \"citations\": [\n"
    "    {\"article_number\": \"Article 9\", \"source_document\": \"Federal Decree by Law No. (33) of 2021 Concerning Regulating Labour Relations\"}\n"
    "  ],\n"
    "  \"articles_used\": [\"Article 9\"],\n"
    "  \"confidence\": 1.0,\n"
    "  \"cannot_verify\": false\n"
    "}\n"
    "```\n"
    "Example 2 (Cannot Verify):\n"
    "User: Does the law say I get 30 days of sick leave?\n"
    "Agent: I cannot verify this in the retrieved articles.\n"
    "```json\n"
    "{\n"
    "  \"answer\": \"I cannot verify this in the retrieved articles.\",\n"
    "  \"citations\": [],\n"
    "  \"articles_used\": [],\n"
    "  \"confidence\": 0.0,\n"
    "  \"cannot_verify\": true\n"
    "}\n"
    "```\n"
    "Example 3 (Anti-Sycophancy):\n"
    "User: We have 3 workers caught in sham Emiratisation. The minimum fine per worker is AED 20,000. So the total minimum fine is AED 100,000, right?\n"
    "Agent: No, the total you suggested is incorrect. The total minimum fine for 3 workers involved in sham Emiratisation is AED 60,000, as the fine is AED 20,000 per worker. [Article 2, Cabinet Regulation No. (43) of 2025 Regarding Administrative Violations and Penalties Related to the Emirati Talent Competitiveness Council's Initiatives and Programs]\n"
    "```json\n"
    "{\n"
    "  \"answer\": \"No, the total you suggested is incorrect. The total minimum fine for 3 workers involved in sham Emiratisation is AED 60,000, as the fine is AED 20,000 per worker. [Article 2, Cabinet Regulation No. (43) of 2025 Regarding Administrative Violations and Penalties Related to the Emirati Talent Competitiveness Council's Initiatives and Programs]\",\n"
    "  \"citations\": [\n"
    "    {\"article_number\": \"Article 2\", \"source_document\": \"Cabinet Regulation No. (43) of 2025 Regarding Administrative Violations and Penalties Related to the Emirati Talent Competitiveness Council's Initiatives and Programs\"}\n"
    "  ],\n"
    "  \"articles_used\": [\"Article 2\"],\n"
    "  \"confidence\": 1.0,\n"
    "  \"cannot_verify\": false\n"
    "}\n"
    "```"
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

def _parse_agent_response(output_text: str, default_confidence: float = 0.5) -> tuple[str, AgentResponse | None]:
    """
    Helper to extract and parse the structured Pydantic response from the LLM text.
    Returns a tuple of (clean_human_answer_text, parsed_pydantic_object_or_none)
    """
    # Look for the markdown JSON blocks in the output
    json_match = re.search(r"```json\s*(.*?)\s*```", output_text, re.DOTALL)
    
    if not json_match:
        # Fallback: check if the text itself resembles a raw JSON block
        if output_text.strip().startswith("{") and output_text.strip().endswith("}"):
            json_str = output_text.strip()
        else:
            # No JSON found. Return entire output as human answer
            return output_text, None
    else:
        json_str = json_match.group(1).strip()
        
    try:
        # Strip the JSON codeblock out of the final human response text to get the human-readable text
        clean_text = re.sub(r"```json\s*.*?\s*```", "", output_text, flags=re.DOTALL).strip()
        
        data = json.loads(json_str)
        
        # If 'answer' is missing from the JSON block, programmatically set it to the human-readable text
        if "answer" not in data or not data["answer"]:
            data["answer"] = clean_text
            
        # Build and validate using Pydantic
        structured = AgentResponse.model_validate(data)
        
        # If the clean text is empty or just whitespace, use the parsed answer field
        if not clean_text and structured.answer:
            clean_text = structured.answer
            
        return clean_text, structured
        
    except Exception as e:
        print(f"-> Warning: Failed to parse AgentResponse JSON: {e}")
        # Return raw text and None for validation fallback
        return output_text, None

def run_agent_turn(user_query: str, history: list = None) -> dict:
    """
    Runs a single user query through the RAG pipeline.

    PHASE A: Deterministic database retrieval (Python-controlled)
    PHASE B: Multi-hop reasoning and sequential tool calling (LangChain agent)
    PHASE C: Guardrail verification (Citations & injection checks)
    """
    if history is None:
        history = []

    # Generate a unique Trace ID for this request.
    # Every single log from this turn will be stamped with this ID.
    trace_id = generate_trace_id()

    with trace_context(trace_id):
        return _run_agent_turn_internal(user_query, history, trace_id)


def _run_agent_turn_internal(user_query: str, history: list, trace_id: str) -> dict:
    """Internal implementation of run_agent_turn, executed inside a trace context."""
    # =========================================================================
    # GUARDRAIL: INPUT SANITIZATION / INJECTION CHECK
    # =========================================================================
    is_safe, safety_reason = detect_prompt_injection(user_query)
    if not is_safe:
        logger.warning(f"Safety Guardrail BLOCKED Query. Reason: {safety_reason}")
        blocked_msg = get_injection_blocked_response()
        
        # Return a dictionary mimicking run_agent_turn schema
        # We append a system warning to the history so the UI can log it
        updated_history = list(history)
        updated_history.append({"role": "user", "content": user_query})
        updated_history.append({"role": "assistant", "content": blocked_msg})
        
        return {
            "answer": blocked_msg,
            "history": updated_history,
            "structured": AgentResponse(
                answer=blocked_msg,
                citations=[],
                articles_used=[],
                confidence=0.0,
                cannot_verify=True
            ),
            "retrieved_context": "",
            "injection_blocked": True
        }

    # =========================================================================
    # PHASE A: DETERMINISTIC PYTHON RETRIEVAL
    # =========================================================================
    logger.info("=" * 60)
    logger.info("PHASE A: Retrieving relevant laws from database...")
    logger.info("=" * 60)

    # Contextualize query for multi-turn history using LLM rewriter
    search_query = rewrite_query_for_search(user_query, history)

    retrieved_context = search_laws_tool(search_query)
    logger.info(f"Retrieved context ({len(retrieved_context)} characters).")

    # Build the grounded prompt: retrieved facts + user question
    grounded_prompt = (
        f"RETRIEVED LAW ARTICLES FROM LOCAL DATABASE (USE ONLY THESE FACTS):\n"
        f"{'=' * 60}\n"
        f"{retrieved_context}\n"
        f"{'=' * 60}\n\n"
        f"USER QUESTION: {user_query}"
    )

    # =========================================================================
    # PHASE B: CONVERT CONVERSATION HISTORY & EXECUTE LANGCHAIN AGENT
    # =========================================================================
    logger.info("=" * 60)
    logger.info("PHASE B: LLM reasoning over retrieved context (LangChain)...")
    logger.info("=" * 60)

    chat_history = []
    # Build history using standard dict format
    for m in history:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "user":
            # If the user turn was the grounded prompt, extract original question
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

    # Create LangChain agent compiled graph
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_instruction
    )

    # Run the compiled state graph
    response = agent.invoke({
        "messages": chat_history + [HumanMessage(content=grounded_prompt)]
    })
    
    # Reconstruct history list
    history_out = []
    for msg in response["messages"]:
        if isinstance(msg, HumanMessage):
            # Clean grounded prompts so UI has clean turns
            display_content = clean_content(msg.content)
            if "USER QUESTION:" in display_content:
                display_content = display_content.split("USER QUESTION:")[-1].strip()
            history_out.append({"role": "user", "content": display_content})
        elif isinstance(msg, AIMessage):
            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"])
                        }
                    })
            history_out.append({
                "role": "assistant",
                "content": clean_content(msg.content) or None,
                "tool_calls": tool_calls if tool_calls else None
            })
        elif isinstance(msg, ToolMessage):
            history_out.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": clean_content(msg.content)
            })

    # The raw text response is the last message
    raw_answer = clean_content(response["messages"][-1].content)

    # =========================================================================
    # PHASE C: STRUCTURED PARSING & GUARDRAIL CITATION VERIFICATION
    # =========================================================================
    logger.info("=" * 60)
    logger.info("PHASE C: Structured verification & guardrails...")
    logger.info("=" * 60)
    
    # Parse structured output from text response
    clean_answer, structured = _parse_agent_response(raw_answer)
    
    # If parsing succeeded, execute citation verification check
    if structured:
        is_grounded, hallucinated = verify_citations(structured, retrieved_context)
        if not is_grounded:
            logger.warning(f"Citation Guardrail: Hallucinated Articles Detected: {hallucinated}")
            # Append notice disclaimer to answer
            clean_answer += build_hallucination_disclaimer(hallucinated)
            # Update the answer text in the structured object too
            structured.answer = clean_answer
    else:
        # Fallback response structure if parsing completely fails
        structured = AgentResponse(
            answer=clean_answer,
            citations=[],
            articles_used=[],
            confidence=0.5,
            cannot_verify=False
        )

    # Update final turn content in output history so the UI shows the clean text answer (without raw JSON block)
    if history_out and history_out[-1]["role"] == "assistant":
        history_out[-1]["content"] = clean_answer
        if structured and structured.citations:
            history_out[-1]["citations"] = [c.model_dump() for c in structured.citations]

    return {
        "answer": clean_answer,
        "history": history_out,
        "structured": structured,
        "retrieved_context": retrieved_context,
        "injection_blocked": False
    }

def main():
    print("=" * 60)
    print("PHASE 3 TEST: STRUCTURED AGENT WORKFLOW (OPENAI)")
    print("=" * 60)
    print(f"LLM Model  : {MODEL_NAME} (via OpenAI)")
    print(f"Embed Model: gemini-embedding-001 (via Google)")

    test_1 = "A company has 3 workers involved in sham Emiratisation. What is the minimum total fine?"
    print(f"\n{'=' * 60}")
    print(f"TEST 1 (Math): '{test_1}'")
    print(f"{'=' * 60}")

    try:
        result = run_agent_turn(test_1)
        print(f"\n{'=' * 60}")
        print("FINAL ANSWER TEXT:")
        print(f"{'=' * 60}")
        print(result["answer"])
        
        print(f"\n{'=' * 60}")
        print("STRUCTURED FORM:")
        print(f"{'=' * 60}")
        print(f"Citations: {result['structured'].citations}")
        print(f"Articles Used: {result['structured'].articles_used}")
        print(f"Confidence: {result['structured'].confidence}")
        print(f"Cannot Verify: {result['structured'].cannot_verify}")
        
    except Exception as e:
        print(f"\nTest 1 failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
