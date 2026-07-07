import os
import sys
import time
import json
from dotenv import load_dotenv
from google import genai
from rapidfuzz import fuzz

# Try importing OpenAI to allow toggling models easily
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Add the project root directory to Python's path so we can run scripts from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent import run_agent_turn
from langsmith import evaluate
from langsmith.schemas import Example, Run

# Load environment variables (API keys)
load_dotenv()

def predict(inputs: dict) -> dict:
    """
    Wrapper function that maps LangSmith inputs to our agent runner.
    
    UPGRADED: Now accepts dictionary output from run_agent_turn and extracts
    retrieved_context and structured AgentResponse for downstream evaluation.
    """
    query = inputs["query"]
    is_multi_turn = inputs.get("is_multi_turn", False)
    setup_queries = inputs.get("setup_queries", [])
    
    history = []
    
    # Setup prior conversation turns if this is a multi-turn scenario
    if is_multi_turn and setup_queries:
        print(f"\n[Multi-Turn Prep] Running {len(setup_queries)} pre-queries to establish history...")
        for sq in setup_queries:
            # Sleep 1.5s between turns to avoid hitting rate limits
            time.sleep(1.5)
            result = run_agent_turn(sq, history)
            history = result["history"]
        print("[Multi-Turn Prep] History established. Running final evaluation question...")
        # Sleep before the target turn
        time.sleep(1.5)
    
    # Sleep 3.0s between evaluation cases to stay within Free Tier 15 RPM limits
    time.sleep(3.0)
    
    for attempt in range(4):
        try:
            # Run the main query to test
            result = run_agent_turn(query, history)
            
            # Return outputs to be checked by our custom evaluators
            return {
                "answer": result["answer"],
                "history": result["history"],
                "retrieved_context": result.get("retrieved_context", ""),
                "structured": result.get("structured").model_dump() if result.get("structured") else {}
            }
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                delay = 5.0 * (2 ** attempt)
                print(f"[predict] Rate limit hit. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise e
    
    # Final fallback if it completely fails
    return {
        "answer": "Failed due to rate limits.",
        "history": [],
        "retrieved_context": "",
        "structured": {}
    }

# --- CUSTOM DETERMINISTIC EVALUATORS (TOKEN-FREE) ---

from src.test_suite import (
    normalize_text,
    extract_non_citation_text,
    check_negation
)

def normalize_number_words(text: str) -> str:
    """Converts common English number words to digits for robust comparison."""
    mapping = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
    }
    cleaned = text.lower()
    for word, digit in mapping.items():
        # Replace word with digit (with spacing boundary checks)
        cleaned = cleaned.replace(f" {word} ", f" {digit} ")
        cleaned = cleaned.replace(f"({word})", f"({digit})")
        if cleaned.startswith(word + " "):
            cleaned = cleaned.replace(word + " ", digit + " ", 1)
        if cleaned.endswith(" " + word):
            cleaned = cleaned.replace(" " + word, " " + digit)
    return cleaned

def phrase_matches_answer(phrase: str, answer: str, threshold: float = 0.8) -> bool:
    """
    Returns True if the phrase is present in the answer text with a high similarity.
    Uses rapidfuzz partial ratio.
    """
    phrase_norm = normalize_number_words(normalize_text(phrase))
    answer_norm = normalize_number_words(normalize_text(answer))
    
    # 1. Fast exact path
    if phrase_norm in answer_norm:
        return True
        
    # 2. Fuzzy partial match (allows matching phrases embedded in text)
    score = fuzz.partial_ratio(phrase_norm, answer_norm)
    return (score / 100.0) >= threshold

def citation_evaluator(run: Run, example: Example) -> dict:
    """
    Checks if all expected legal document and article citations are present in the response.
    
    UPGRADED: Now uses rapidfuzz for smart fuzzy comparison.
    """
    predicted = run.outputs or {}
    answer = predicted.get("answer", "") or ""
    
    reference = example.outputs or {}
    expected_citations = reference.get("expected_citations", [])
    
    errors = []
    for citation in expected_citations:
        # Match using fuzzy ratio comparison
        if not phrase_matches_answer(citation, answer, threshold=0.8):
            errors.append(f"Missing citation: '{citation}'")
            
    return {
        "key": "citation_score",
        "score": 1.0 if not errors else 0.0,
        "comment": "; ".join(errors) if errors else "Passed citation check."
    }

def math_evaluator(run: Run, example: Example) -> dict:
    """
    Checks if the agent correctly triggered the 'math_calculator' tool
    with the expected arguments OR produced the correct expected final value.
    
    UPGRADED: Now checks for expected final value as a flexible alternative to exact formula matching.
    """
    predicted = run.outputs or {}
    history = predicted.get("history", []) or []
    
    reference = example.outputs or {}
    expected_math_tokens = reference.get("expected_math_tokens", [])
    expected_final_value = reference.get("expected_final_value", None)
    
    # 1. If we have expected final value, check if any tool calculated it
    if expected_final_value is not None:
        final_val_str = normalize_text(str(expected_final_value))
        
        # Check all tool outputs in history
        tool_results = []
        for msg in history:
            if msg.get("role") == "tool" and msg.get("content"):
                tool_results.append(normalize_text(msg.get("content")))
                
        # If the expected final value matches any tool output, we count it as correct
        if any(final_val_str in res for res in tool_results):
            return {
                "key": "math_score",
                "score": 1.0,
                "comment": f"Correct final value {expected_final_value} calculated by tool."
            }
            
    # 2. Backward compatibility: Fallback to token-checking on calculator call expressions
    if not expected_math_tokens:
        return {
            "key": "math_score",
            "score": 1.0,
            "comment": "No math expected."
        }
    
    # Extract all math calculator tool calls made during execution
    math_calls_made = []
    for msg in history:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc_call in msg["tool_calls"]:
                if tc_call.get("function", {}).get("name") == "math_calculator":
                    math_calls_made.append(tc_call)
                    
    errors = []
    for tokens in expected_math_tokens:
        matched = False
        for mc in math_calls_made:
            raw_args = mc.get("function", {}).get("arguments", "")
            
            # Robustly parse both pre-parsed dictionaries and stringified JSON
            if isinstance(raw_args, dict):
                expr = raw_args.get("expression", str(raw_args))
            elif isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                    expr = parsed.get("expression", raw_args)
                except (json.JSONDecodeError, AttributeError):
                    expr = raw_args
            else:
                expr = str(raw_args)
                
            # Clean up spacing and casing for reliable matching
            expr_clean = expr.replace(" ", "").lower()
            
            # Verify that all expected tokens in this group exist in the formula
            if all(tok.replace(" ", "").lower() in expr_clean for tok in tokens):
                matched = True
                break
        if not matched:
            errors.append(f"Missing calculator call containing: {tokens}")
            
    return {
        "key": "math_score",
        "score": 1.0 if not errors else 0.0,
        "comment": "; ".join(errors) if errors else "Passed math check."
    }

def accuracy_evaluator(run: Run, example: Example) -> dict:
    """
    Checks if key phrases (numbers, rules) are present and forbidden terms are absent.
    Also verifies the 'cannot verify' boundary logic if data is missing.
    
    UPGRADED: Now uses rapidfuzz fuzzy matching to prevent phrasal false negatives.
    """
    predicted = run.outputs or {}
    answer = predicted.get("answer", "") or ""
    answer_normalized = normalize_text(answer)
    answer_no_citations = normalize_text(extract_non_citation_text(answer))
    
    reference = example.outputs or {}
    expected_key_phrases = reference.get("expected_key_phrases", [])
    forbidden_terms = reference.get("forbidden_terms", [])
    expect_cannot_verify = reference.get("expect_cannot_verify", False)
    
    errors = []
    
    # Check key phrases (using fuzzy matching ratio)
    for phrase in expected_key_phrases:
        if not phrase_matches_answer(phrase, answer, threshold=0.8):
            errors.append(f"Missing expected phrase: '{phrase}'")
            
    # Check forbidden terms (citation-safe, negation-safe)
    for term in forbidden_terms:
        term_normalized = normalize_text(term)
        if check_negation(answer_no_citations, term_normalized):
            errors.append(f"Found forbidden term: '{term}'")
            
    # Check boundary condition statement (cannot-verify refusal)
    if expect_cannot_verify:
        cannot_verify_phrases = [
            "cannot verify", "cannot find", "not found", "unable to verify",
            "not in the retrieved", "do not contain", "cannot locate",
            "i cannot", "not available", "no information"
        ]
        found_cv = any(p in answer_normalized for p in cannot_verify_phrases)
        if not found_cv:
            errors.append("Expected 'cannot verify' message for missing information, but none matched.")
            
    return {
        "key": "accuracy_score",
        "score": 1.0 if not errors else 0.0,
        "comment": "; ".join(errors) if errors else "Passed accuracy check."
    }

# ==============================================================================
# LLM-AS-A-JUDGE: CONFIGURATION & TOGGLE (GEMINI VS OPENAI)
# ==============================================================================

# TOGGLE FLAG: Set to True to use OpenAI (gpt-4o-mini). Set to False to revert to Gemini.
USE_OPENAI = True

# Initialize Gemini Client using your free-tier key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini client for evaluator: {e}")

# Initialize OpenAI Client using your env key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OpenAI and OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize OpenAI client for evaluator: {e}")

def run_openai_judge(prompt: str, evaluation_key: str) -> dict:
    """Helper to run an OpenAI judge query (gpt-4o-mini) with exponential backoff retry."""
    if not openai_client:
        return {
            "key": evaluation_key,
            "score": 0.0,
            "comment": "OpenAI client not initialized."
        }

    delay = 2.0
    for attempt in range(5):
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_text = response.choices[0].message.content.strip()
            
            parsed = json.loads(raw_text)
            score = float(parsed.get("score", 0.0))
            rationale = parsed.get("rationale", "No rationale provided.")
            
            return {
                "key": evaluation_key,
                "score": max(0.0, min(1.0, score)),
                "comment": rationale
            }
            
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate_limit" in error_str or "quota" in error_str:
                print(f"-> OpenAI Judge Rate Limit (429). Attempt {attempt + 1}/5. Waiting {delay}s...")
                time.sleep(delay)
                delay *= 2.0
            else:
                return {
                    "key": evaluation_key,
                    "score": 0.0,
                    "comment": f"OpenAI semantic auditor failed: {str(e)}"
                }
                
    return {
        "key": evaluation_key,
        "score": 0.0,
        "comment": "Exceeded maximum retries for OpenAI Judge due to rate limits."
    }

def run_gemini_judge(prompt: str, evaluation_key: str) -> dict:
    """Helper to run a Gemini judge query with exponential backoff retry."""
    if not gemini_client:
        return {
            "key": evaluation_key,
            "score": 0.0,
            "comment": "Gemini client not initialized."
        }

    delay = 2.0
    for attempt in range(5):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            raw_text = response.text.strip()
            
            # Clean markdown JSON block wrappers
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()
                
            parsed = json.loads(raw_text)
            score = float(parsed.get("score", 0.0))
            rationale = parsed.get("rationale", "No rationale provided.")
            
            return {
                "key": evaluation_key,
                "score": max(0.0, min(1.0, score)),
                "comment": rationale
            }
            
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
                print(f"-> Gemini Judge Rate Limit (429). Attempt {attempt + 1}/5. Waiting {delay}s...")
                time.sleep(delay)
                delay *= 2.0
            else:
                return {
                    "key": evaluation_key,
                    "score": 0.0,
                    "comment": f"Semantic auditor failed: {str(e)}"
                }
                
    return {
        "key": evaluation_key,
        "score": 0.0,
        "comment": "Exceeded maximum retries for Gemini Judge due to rate limits."
    }

def gemini_semantic_evaluator(run: Run, example: Example) -> dict:
    """
    Semantic Compliance Evaluator using Gemini.
    Acts as an independent auditor to grade the agent's answer against compliance rules,
    handling semantic variance (different wording, professional phrasing).
    """
    user_query = run.inputs.get("query", "")
    agent_answer = (run.outputs or {}).get("answer", "")
    
    reference_data = example.outputs or {}
    expected_citations = reference_data.get("expected_citations", [])
    expected_key_phrases = reference_data.get("expected_key_phrases", [])
    forbidden_terms = reference_data.get("forbidden_terms", [])
    expect_cannot_verify = reference_data.get("expect_cannot_verify", False)

    prompt = f"""You are a strict legal auditor reviewing a compliance RAG copilot for UAE Labour Law and Nafis regulations.
Evaluate the semantic correctness and compliance of the Agent's Answer.

---
USER QUERY:
"{user_query}"

---
AGENT'S ANSWER:
"{agent_answer}"

---
COMPLIANCE CRITERIA:
1. Expected Citations (must be referenced or named): {expected_citations}
2. Expected Key Details/Numbers (must be present in correct context): {expected_key_phrases}
3. Forbidden Terms/Numbers (must NOT be stated as facts in the answer): {forbidden_terms}
4. Should Refuse to Answer (expect_cannot_verify): {expect_cannot_verify} (If True, the agent must state it cannot verify or locate the rule in its retrieved database, and must NOT make up an answer).

---
INSTRUCTIONS:
- Analyze the semantic meaning of the answer. If the agent explains a rule correctly but uses slightly different wording, grade it as correct. A brief, precise, correct answer is a perfect answer. Do not penalize for brevity or style variation as long as the facts, numbers, and citations are correct.
- If the agent misses required citations, penalize the score. (Note: Accept either Article X or Article (X) formats).
- If the agent states a forbidden term/number as a fact, penalize the score. (Note: if it mentions the forbidden number to explicitly deny it, e.g. "the fine is NOT 100,000", that is acceptable).
- If the agent is supposed to refuse (expect_cannot_verify is True):
  * If it successfully states that it cannot verify or locate the rule, give a score of 1.0. Do not penalize it for missing citations or key details.
  * If it invents numbers, guesses, or answers the question as if the rule exists, give a score of 0.0.
- Provide a score between 0.0 (completely wrong/non-compliant) and 1.0 (perfect compliance).
- Provide a brief 1-sentence rationale for your score.

---
OUTPUT FORMAT:
Output your audit report strictly in the following JSON format:
{{
  "score": <float between 0.0 and 1.0>,
  "rationale": "<1-sentence explanation of the score>"
}}
Do NOT output any markdown blocks, introductory text, or concluding text. Output raw JSON only.
"""
    # Route to selected judge model based on toggle
    if USE_OPENAI:
        return run_openai_judge(prompt, "semantic_accuracy")
    else:
        return run_gemini_judge(prompt, "semantic_accuracy")

def gemini_faithfulness_evaluator(run: Run, example: Example) -> dict:
    """
    Faithfulness Evaluator (Hallucination Detector) using Gemini.
    Checks whether the agent's answer is strictly grounded in the retrieved context
    without adding fabricated facts from general training knowledge.
    """
    user_query = run.inputs.get("query", "")
    predicted = run.outputs or {}
    agent_answer = predicted.get("answer", "")
    retrieved_context = predicted.get("retrieved_context", "")

    if not retrieved_context:
        return {
            "key": "faithfulness",
            "score": 1.0,
            "comment": "No retrieved context (e.g. blocked query)."
        }

    prompt = f"""You are a strict legal compliance auditor. Evaluate if the Agent's Answer is strictly faithful to the Retrieved Context and grounded in the User Query inputs.
Verify that the Agent did not hallucinate rules, article numbers, or fines not explicitly found in the context. Note that the Agent is expected to perform mathematical calculations (like daily wages, notice compensation, or total fines) based on the numbers provided in the User Query.

---
USER QUERY (INPUTS):
"{user_query}"

---
RETRIEVED CONTEXT (LAWS):
"{retrieved_context}"

---
AGENT'S ANSWER (OUTPUT):
"{agent_answer}"

---
INSTRUCTIONS:
- Assign 1.0 (Faithful) if every factual claim, rule, citation, and number in the answer is directly supported by the context and the user query inputs.
- Assign 0.0 (Not Faithful) if the agent introduces external legal facts, numbers, or articles not explicitly stated in the context or derived from the user query inputs.
- If the agent stated it could not verify the information (because it wasn't in the context), assign 1.0.
- Provide a brief 1-sentence rationale for your score.

---
OUTPUT FORMAT:
Output your audit report strictly in the following JSON format:
{{
  "score": <0.0 or 1.0>,
  "rationale": "<1-sentence explanation of the score>"
}}
Do NOT output any markdown blocks. Output raw JSON only.
"""
    # Route to selected judge model based on toggle
    if USE_OPENAI:
        return run_openai_judge(prompt, "faithfulness")
    else:
        return run_gemini_judge(prompt, "faithfulness")

def gemini_relevance_evaluator(run: Run, example: Example) -> dict:
    """
    Retrieval Relevance Evaluator using Gemini.
    Evaluates whether the retrieved context passages are relevant to answering the query.
    """
    user_query = run.inputs.get("query", "")
    predicted = run.outputs or {}
    retrieved_context = predicted.get("retrieved_context", "")

    if not retrieved_context:
        return {
            "key": "retrieval_relevance",
            "score": 0.0,
            "comment": "No context retrieved."
        }

    prompt = f"""You are an information retrieval expert. Evaluate if the Retrieved Context contains relevant legal rules to address the User Query.

---
USER QUERY:
"{user_query}"

---
RETRIEVED CONTEXT:
"{retrieved_context}"

---
INSTRUCTIONS:
- Assign a score from 0.0 (completely irrelevant context) to 1.0 (contains the exact regulations/rules needed to answer).
- If the context contains background laws but misses the specific target rule, assign a partial score (e.g. 0.5).
- Provide a brief 1-sentence rationale for your score.

---
OUTPUT FORMAT:
Output your audit report strictly in the following JSON format:
{{
  "score": <float between 0.0 and 1.0>,
  "rationale": "<1-sentence explanation of the score>"
}}
Do NOT output any markdown blocks. Output raw JSON only.
"""
    # Route to selected judge model based on toggle
    if USE_OPENAI:
        return run_openai_judge(prompt, "retrieval_relevance")
    else:
        return run_gemini_judge(prompt, "retrieval_relevance")

# ==============================================================================
# MAIN RUNNER
# ==============================================================================

def run_evaluations():
    print("=" * 60)
    print("STARTING LANGSMITH AUTOMATED COMPLIANCE EVALUATION SUITE")
    print("=" * 60)
    
    dataset_name = "uae-hr-compliance-suite"
    
    try:
        results = evaluate(
            predict,
            data=dataset_name,
            evaluators=[
                citation_evaluator, 
                math_evaluator, 
                accuracy_evaluator,
                gemini_semantic_evaluator,
                gemini_faithfulness_evaluator,   # NEW
                gemini_relevance_evaluator       # NEW
            ],
            experiment_prefix="agent-hardening-run",
            max_concurrency=1
        )
        print("\n" + "=" * 60)
        print("EVALUATION RUN COMPLETE!")
        print("Check the results on your LangSmith dashboard.")
        print("=" * 60)
    except Exception as e:
        print(f"\nEvaluation failed with error: {e}")
        print("Ensure you have set LANGCHAIN_API_KEY and LANGCHAIN_TRACING_V2=true in your .env file.")

if __name__ == "__main__":
    run_evaluations()
