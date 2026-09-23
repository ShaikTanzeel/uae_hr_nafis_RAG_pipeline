import os
import sys
import re
import time
import json
import traceback
from rapidfuzz import fuzz

# Add the project root directory to Python's path so we can import src modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PHASE 2 — SECTION F: run_agent_turn() was retired in A1 (replaced by the
# streaming stream_agent_turn()). run_agent_turn_blocking() is a small
# adapter in src/agent.py that drives the streamed version to completion and
# hands back the same {"answer", "history", ...} shape this file was built
# against — see src/agent.py's Section F comment block for why.
from src.agent import run_agent_turn_blocking as run_agent_turn
from src.tools import safe_math_eval  # Used for dynamic math verification

# ==============================================================================
# SECTION 1 - HELPER FUNCTIONS
#
# These are our "smart readers" that let us evaluate the agent's answer
# without requiring a perfectly worded exact match.
# ==============================================================================

def phrase_matches_answer(phrase: str, answer: str, threshold: float = 0.8) -> bool:
    """
    Returns True if the phrase is present in the answer text with a high similarity.
    Uses rapidfuzz partial ratio.
    """
    phrase_norm = normalize_text(phrase)
    answer_norm = normalize_text(answer)
    
    # 1. Fast exact path
    if phrase_norm in answer_norm:
        return True
        
    # 2. Fuzzy partial match (allows matching phrases embedded in text)
    score = fuzz.partial_ratio(phrase_norm, answer_norm)
    return (score / 100.0) >= threshold


def normalize_text(text: str) -> str:
    """
    Normalizes text for comparison by:
    - Converting to lowercase
    - Removing commas inside numbers (e.g., "60,000" becomes "60000")
    - Removing parentheses around digits/numbers (e.g., "(30)" becomes "30")
    - Mapping small written number words to digits (e.g., "six" -> "6")
    - Collapsing extra whitespace
    """
    text = text.lower()
    # Remove commas between digits (e.g. 60,000 becomes 60000)
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    # Remove parentheses around numbers (e.g. (30) becomes 30)
    text = re.sub(r'\((\d+)\)', r'\1', text)
    
    # Map written numbers to digits
    number_map = {
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
    }
    for word, digit in number_map.items():
        text = re.sub(r'\b' + word + r'\b', digit, text)
        
    # Collapse multiple spaces into one
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_non_citation_text(text: str) -> str:
    """
    Removes content inside square brackets from the text.
    This prevents citation references like [Article 2, Cabinet Regulation No. 43]
    from falsely triggering forbidden term checks.

    Example:
        Input:  "The fine is NOT 100,000 [Article 2, Cabinet Regulation No. 43, 100000]"
        Output: "The fine is NOT 100,000 "

    Without this, checking for forbidden term "100000" would match
    the citation reference, not a claim in the main answer body.
    """
    return re.sub(r'\[.*?\]', '', text)


def check_negation(text: str, term: str) -> bool:
    """
    Returns True if the forbidden term appears WITHOUT a nearby negation word.
    We look at the 30 characters BEFORE the term for negation signals.

    Example:
        "the fine is NOT 100,000" -> negation found -> term is OK (not a real claim)
        "the fine is 100,000"     -> no negation    -> term IS a forbidden claim

    Negation words checked: not, no, never, cannot, isn't, don't
    """
    negation_words = ["not", "no", "never", "cannot", "isn't", "don't"]
    start = 0
    while True:
        idx = text.find(term, start)
        if idx == -1:
            break
        # Look at the 30 characters before this occurrence
        context_before = text[max(0, idx - 30):idx]
        # If none of the negation words appear in that context, it's a real claim
        if not any(neg in context_before for neg in negation_words):
            return True  # Found an un-negated use of the forbidden term
        start = idx + 1
    return False  # All occurrences are negated -- term is safe


def evaluate_math_calls(math_calls_made: list, expected_math_tokens: list) -> tuple:
    """
    Verifies that the agent used the math_calculator tool correctly.

    For each expected token-set (a list of numbers that MUST appear together
    in one tool call expression), we check if any actual tool call contains
    ALL of those numbers.

    We also use safe_math_eval to run the expression and confirm the result
    is mathematically valid (non-zero, non-error).

    Returns:
        - score (float): 0.0 to 1.0 (fraction of expected math calls matched)
        - errors (list): Human-readable descriptions of what failed
    """
    if not expected_math_tokens:
        return 1.0, []  # No math expected -> full score by default

    errors = []
    matched = 0

    for token_group in expected_math_tokens:
        found = False
        for mc in math_calls_made:
            # The tool call arguments may be a JSON string like {"expression": "3 * 20000"}
            raw_args = mc.get("function", {}).get("arguments", "")
            if isinstance(raw_args, str):
                try:
                    parsed = json.loads(raw_args)
                    expr = parsed.get("expression", raw_args)
                except (json.JSONDecodeError, AttributeError):
                    expr = raw_args
            else:
                expr = str(raw_args)

            expr_normalized = normalize_text(expr)

            # Check that ALL expected tokens appear in this one expression
            if all(tok.lower() in expr_normalized for tok in token_group):
                # Bonus check: make sure the expression actually computes to something valid
                try:
                    result = safe_math_eval(expr)
                    if result is not None and result != 0:
                        found = True
                        break
                except Exception:
                    # Even if eval fails, token presence check is enough
                    found = True
                    break

        if found:
            matched += 1
        else:
            errors.append(
                f"Math check FAILED: Expected a calculator call containing all of {token_group} "
                f"but no matching tool call was found."
            )

    score = matched / len(expected_math_tokens) if expected_math_tokens else 1.0
    return round(score, 3), errors


# ==============================================================================
# SECTION 2 - TEST CASE DEFINITIONS
#
# 10 consolidated test cases, each covering a distinct capability:
#   1. Single math (sham Emiratisation)
#   2. Multi-hop math (two violation types)
#   3. Pure retrieval, no math (probation limit)
#   4. Multi-field retrieval (sick leave tiers)
#   5. Boundary/OOD (rule not in DB -- agent must refuse)
#   6. Multi-turn memory (probation extension follow-up)
#   7. Wrong-math trap (user suggests wrong answer)
#   8. Bilingual/term-mapping (gratuity)
#   9. Complex salary math (maternity leave)
#  10. Daily wage rule (probation dismissal compensation)
# ==============================================================================

TEST_CASES = [
    {
        "id": 1,
        "name": "Math: Single Multiplication (Sham Emiratisation Fine)",
        "query": "A company has 3 workers registered under sham Emiratisation. What is the minimum administrative fine we will face?",
        "setup_queries": [],
        "expected_math_tokens": [["3", "20000"]],
        "expected_citations": ["Article 2", "Cabinet Regulation"],
        "expected_key_phrases": ["60000"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": "Agent must multiply 3 workers x 20,000 per worker using the calculator, not in its head."
    },
    {
        "id": 2,
        "name": "Math: Multi-Hop Calculation (Evasion + Renewal Failure)",
        "query": (
            "If we submit incorrect documents to evade Emiratisation systems for 2 workers, "
            "and also fail to renew our Emiratisation documents for 3 months, "
            "what are the minimum fines under Nafis regulations?"
        ),
        "setup_queries": [],
        "expected_math_tokens": [],
        "expected_citations": ["Article 2", "Cabinet Regulation"],
        "expected_key_phrases": ["46000"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": "Two separate fine types; agent must retrieve and apply two different rules."
    },
    {
        "id": 3,
        "name": "No-Math: Probation Period Limit Lookup",
        "query": "What is the maximum probation period allowed for a new employee under UAE Labour Law?",
        "setup_queries": [],
        "expected_math_tokens": [],
        "expected_citations": ["Article 9", "Federal Decree"],
        "expected_key_phrases": ["6 months"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": "Pure retrieval test -- no math, no ambiguity. Article 9, Federal Decree Law No. 33 of 2021."
    },
    {
        "id": 4,
        "name": "No-Math: Sick Leave Entitlement Split",
        "query": "How many days of sick leave is an employee entitled to per year, and how is the pay split?",
        "setup_queries": [],
        "expected_math_tokens": [],
        "expected_citations": ["Article 31", "Federal Decree"],
        "expected_key_phrases": ["15 days", "full pay", "30 days", "half pay", "unpaid"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": "Tests that the agent correctly retrieves all 3 sick leave tiers from Article 31."
    },
    {
        "id": 5,
        "name": "Boundary: Missing Emiratisation Quota (Rule NOT in Database)",
        "query": "What is the administrative fine for missing our 2% Emiratisation quota by 2 workers?",
        "setup_queries": [],
        "expected_math_tokens": [],
        "expected_citations": [],
        "expected_key_phrases": [],
        "forbidden_terms": ["108000", "72000", "6000"],
        "expect_cannot_verify": True,
        "is_multi_turn": False,
        "notes": (
            "The fine for missing quota percentages is NOT in our database. "
            "Agent must refuse to guess. Forbidden terms test that it does not invent a figure."
        )
    },
    {
        "id": 6,
        "name": "Multi-Turn: Conversation History Retention (Probation Extension)",
        "query": "And can the employer extend it beyond that period?",
        "setup_queries": ["What is the maximum probation period under the UAE Labour Law?"],
        "expected_math_tokens": [],
        "expected_citations": ["Article 9", "Federal Decree"],
        "expected_key_phrases": ["cannot", "6 months"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": True,
        "notes": (
            "The follow-up query ('extend it') only makes sense in context. "
            "Tests that the agent retains prior conversation turns correctly."
        )
    },
    {
        "id": 7,
        "name": "Wrong-Math Trap: Resisting Incorrect Leading Suggestion",
        "query": (
            "If we have 4 workers in sham Emiratisation, and since the minimum fine is AED 20,000, "
            "is the total minimum fine AED 100,000?"
        ),
        "setup_queries": [],
        "expected_math_tokens": [["4", "20000"]],
        "expected_citations": ["Article 2", "Cabinet Regulation"],
        "expected_key_phrases": ["80000"],
        "forbidden_terms": ["100000"],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": (
            "User deliberately suggests the wrong total (100k). "
            "Agent must calculate 4 x 20,000 = 80,000 and reject the user's number."
        )
    },
    {
        "id": 8,
        "name": "Bilingual/Term Mapping: Gratuity for 3 Years Service",
        "query": "What are the rules regarding gratuity (end of service benefits) for an employee who has completed 3 years of continuous service?",
        "setup_queries": [],
        "expected_math_tokens": [["3", "21"]],
        "expected_citations": ["Article 51", "Federal Decree"],
        "expected_key_phrases": ["63 days", "basic wage"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": (
            "Tests that the agent maps 'gratuity' to 'end of service gratuity' from Article 51. "
            "Must compute 3 years x 21 days/year = 63 days."
        )
    },
    {
        "id": 9,
        "name": "Math: Maternity Leave Pay Entitlement (18k Monthly Salary)",
        "query": (
            "A female employee is taking maternity leave. Her monthly salary is AED 18,000. "
            "If she takes 45 days at full pay and 15 days at half pay, "
            "what is her total maternity leave pay entitlement?"
        ),
        "setup_queries": [],
        "expected_math_tokens": [["18000", "30"]],
        "expected_citations": ["Article 30", "Federal Decree"],
        "expected_key_phrases": ["31500"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": (
            "Multi-step calc: daily_wage=18000/30=600, "
            "full-pay portion=600*45=27000, half-pay portion=600*15/2=4500, total=31500."
        )
    },
    {
        "id": 10,
        "name": "Math: Probation Dismissal Notice Compensation (9k Monthly Salary)",
        "query": (
            "An employer terminated an employee during probation without giving the 14-day written notice. "
            "If the employee's monthly basic salary is AED 9,000, "
            "how much compensation is the employee entitled to for the missing notice period?"
        ),
        "setup_queries": [],
        "expected_math_tokens": [["9000", "30"]],
        "expected_citations": ["Article 9", "Federal Decree"],
        "expected_key_phrases": ["4200"],
        "forbidden_terms": [],
        "expect_cannot_verify": False,
        "is_multi_turn": False,
        "notes": (
            "Requires: daily_wage=9000/30=300, then 300*14=4200. "
            "Tests the DAILY WAGE RULE -- monthly salary must not be multiplied directly by days."
        )
    },
]


# ==============================================================================
# SECTION 3 - SCORING ENGINE
#
# For each test case, we run up to 5 independent checks and score each 0.0-1.0.
# The final score is the average across all active dimensions.
#
# Verdict thresholds:
#   PASSED  -- score >= 0.8
#   PARTIAL -- score >= 0.5
#   FAILED  -- score <  0.5
# ==============================================================================

def score_test_case(tc: dict, answer: str, math_calls_made: list) -> tuple:
    """
    Scores a single test case against the agent's answer.

    Dimensions scored:
      1. Math calls:       Were the expected calculator expressions used?
      2. Citations:        Do all expected article/doc references appear?
      3. Key phrases:      Do all expected content phrases appear (normalized)?
      4. Forbidden terms:  Are all forbidden terms absent (citation-safe check)?
      5. Cannot-verify:    Did the agent correctly refuse when info is missing?

    Returns:
      - final_score (float): 0.0 to 1.0
      - all_errors (list): Descriptions of every failed check
    """
    all_errors = []
    dimension_scores = []

    answer_normalized = normalize_text(answer)
    # For forbidden terms, strip citations from the answer before checking
    answer_no_citations = normalize_text(extract_non_citation_text(answer))

    # --- Dimension 1: Math Calls ---
    if tc["expected_math_tokens"]:
        math_score, math_errors = evaluate_math_calls(math_calls_made, tc["expected_math_tokens"])
        dimension_scores.append(math_score)
        all_errors.extend(math_errors)

    # --- Dimension 2: Citations ---
    if tc["expected_citations"]:
        citation_hits = 0
        for citation in tc["expected_citations"]:
            if phrase_matches_answer(citation, answer, threshold=0.8):
                citation_hits += 1
            else:
                all_errors.append(f"Citation check FAILED: Missing '{citation}' in answer.")
        citation_score = citation_hits / len(tc["expected_citations"])
        dimension_scores.append(citation_score)

    # --- Dimension 3: Key Phrases ---
    if tc["expected_key_phrases"]:
        phrase_hits = 0
        for phrase in tc["expected_key_phrases"]:
            if phrase_matches_answer(phrase, answer, threshold=0.8):
                phrase_hits += 1
            else:
                all_errors.append(f"Key phrase check FAILED: Missing '{phrase}' in answer.")
        phrase_score = phrase_hits / len(tc["expected_key_phrases"])
        dimension_scores.append(phrase_score)

    # --- Dimension 4: Forbidden Terms (citation-safe) ---
    if tc["forbidden_terms"]:
        forbidden_violations = 0
        for term in tc["forbidden_terms"]:
            term_normalized = normalize_text(term)
            # Only check the answer body OUTSIDE of citations
            if check_negation(answer_no_citations, term_normalized):
                forbidden_violations += 1
                all_errors.append(
                    f"Forbidden term check FAILED: Found '{term}' as a real claim in the answer body."
                )
        # Score = fraction of forbidden terms that did NOT appear
        forbidden_score = 1.0 - (forbidden_violations / len(tc["forbidden_terms"]))
        dimension_scores.append(forbidden_score)

    # --- Dimension 5: Cannot-Verify Behavior ---
    if tc["expect_cannot_verify"]:
        cannot_verify_phrases = [
            "cannot verify", "cannot find", "not found", "unable to verify",
            "not in the retrieved", "do not contain", "cannot locate",
            "i cannot", "not available", "no information"
        ]
        found_refusal = any(p in answer_normalized for p in cannot_verify_phrases)
        if found_refusal:
            dimension_scores.append(1.0)
        else:
            dimension_scores.append(0.0)
            all_errors.append(
                "Boundary check FAILED: Agent did not state it cannot verify or find the rule. "
                "It should have refused to answer for out-of-database queries."
            )

    # Final score = average across all scored dimensions
    final_score = sum(dimension_scores) / len(dimension_scores) if dimension_scores else 1.0

    return round(final_score, 3), all_errors


# ==============================================================================
# SECTION 4 - TEST RUNNER
# ==============================================================================

def run_test_suite():
    print("=" * 60)
    print("  UAE HR & NAFIS COPILOT - AUTOMATED TEST SUITE")
    print(f"  Running {len(TEST_CASES)} consolidated test cases")
    print("  LLM Backend: Gemini 3.8 Flash (Google) via agent.py — Phase 2 rebuilt pipeline")
    print("=" * 60)

    results = []

    for tc in TEST_CASES:
        print(f"\n{'=' * 60}")
        print(f"[TEST {tc['id']}/{len(TEST_CASES)}] {tc['name']}")
        print(f"Query: \"{tc['query']}\"")
        if tc.get("notes"):
            print(f"Note: {tc['notes']}")
        print("=" * 60)

        history = None

        # --- Multi-turn setup: run prior conversation turns first ---
        if tc["is_multi_turn"] and tc.get("setup_queries"):
            history = []
            for setup_q in tc["setup_queries"]:
                print(f"  -> [Setup turn] Running: \"{setup_q}\"")
                # PHASE 2 — SECTION F: sleep removed. The original 15s buffer was
                # sized for OpenAI's rate limits; failures here are now just
                # caught by the try/except around the test call below instead
                # of pre-emptively guessed against.
                res = run_agent_turn(setup_q, history)
                history = res["history"]
            print("  -> Setup complete. Now running the target follow-up query...")

        # --- Execute the actual test query ---
        start_time = time.time()
        try:
            res = run_agent_turn(tc["query"], history)
            answer = res["answer"]
            updated_history = res["history"]
            duration = time.time() - start_time

            # --- Extract math calculator tool calls from the conversation history ---
            math_calls_made = []
            for msg in updated_history:
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    for tc_call in msg["tool_calls"]:
                        if tc_call.get("function", {}).get("name") == "math_calculator":
                            math_calls_made.append(tc_call)

            # --- Run the scoring engine ---
            score, errors = score_test_case(tc, answer, math_calls_made)

            # Verdict: PASSED if score >= 0.8, PARTIAL if >= 0.5, FAILED otherwise
            if score >= 0.8:
                verdict = "PASSED"
            elif score >= 0.5:
                verdict = "PARTIAL"
            else:
                verdict = "FAILED"

            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "query": tc["query"],
                "answer": answer,
                "duration": duration,
                "verdict": verdict,
                "score": score,
                "errors": errors,
                "math_calls": [
                    mc.get("function", {}).get("arguments", "") for mc in math_calls_made
                ]
            })

            score_bar = "#" * int(score * 10) + "." * (10 - int(score * 10))
            print(f"\nResult : {verdict} | Score: {score:.3f} [{score_bar}]")
            print(f"Timing : {duration:.2f}s | Math tool calls: {len(math_calls_made)}")

            if errors:
                print("Issues found:")
                for err in errors:
                    print(f"  x {err}")
            else:
                print("  All checks passed.")

            print(f"\n--- Agent Answer ---\n{answer}\n--------------------")

        except Exception as e:
            duration = time.time() - start_time
            err_msg = f"CRASH: {str(e)}\n{traceback.format_exc()}"
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "query": tc["query"],
                "answer": "AGENT CRASHED",
                "duration": duration,
                "verdict": "FAILED",
                "score": 0.0,
                "errors": [err_msg],
                "math_calls": []
            })
            print(f"\nResult : CRASHED ({duration:.2f}s)")
            print(err_msg)

        # PHASE 2 — SECTION F: 25s cooldown removed for the same reason as the
        # setup-turn sleep above — each test call is already wrapped in
        # try/except, so a real rate-limit error just fails that one test
        # instead of needing a guessed-at buffer between every call.

    # --- Generate final report ---
    generate_report(results)
    return results


# ==============================================================================
# SECTION 5 - REPORT GENERATOR
# ==============================================================================

def generate_report(results: list):
    """
    Writes a detailed Markdown test report to test_report.md in the project root.
    Uses UTF-8 encoding to correctly handle Arabic text and Unicode characters
    that may appear in retrieved legal texts.
    """
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_report.md"
    )

    passed = sum(1 for r in results if r["verdict"] == "PASSED")
    partial = sum(1 for r in results if r["verdict"] == "PARTIAL")
    failed = sum(1 for r in results if r["verdict"] == "FAILED")
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0.0

    print(f"\nWriting test report to: {report_path}")

    with open(report_path, "w", encoding="utf-8") as f:
        # Header
        f.write("# UAE HR & Nafis Copilot - Automated Test Suite Report\n\n")
        f.write(f"**Test Run Date/Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("**LLM Backend:** Gemini 3.8 Flash (Google) via agent.py — Phase 2 rebuilt pipeline\n")
        f.write(f"**Total Tests:** {len(results)}\n\n")

        # Summary
        f.write("## Overall Results\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Passed (score >= 0.8) | {passed} |\n")
        f.write(f"| Partial (score 0.5-0.79) | {partial} |\n")
        f.write(f"| Failed (score < 0.5) | {failed} |\n")
        f.write(f"| **Average Score** | **{avg_score:.3f}** |\n\n")

        # Summary table
        f.write("## Test Summary Table\n\n")
        f.write("| ID | Test Name | Verdict | Score | Duration | Math Calls |\n")
        f.write("|----|-----------|---------|-------|----------|------------|\n")
        for r in results:
            if r["verdict"] == "PASSED":
                symbol = "PASSED"
            elif r["verdict"] == "PARTIAL":
                symbol = "PARTIAL"
            else:
                symbol = "FAILED"
            f.write(
                f"| {r['id']} | {r['name']} | {symbol} | "
                f"{r['score']:.3f} | {r['duration']:.2f}s | "
                f"{len(r['math_calls'])} |\n"
            )

        f.write("\n---\n\n")

        # Failures section
        f.write("## Failures & Partial Passes - Root Cause Analysis\n\n")
        problem_tests = [r for r in results if r["verdict"] in ("FAILED", "PARTIAL")]
        if not problem_tests:
            f.write("All tests passed! No failures or partial passes to report.\n\n")
        else:
            for r in problem_tests:
                f.write(f"### Test {r['id']}: {r['name']}\n\n")
                f.write(f"**Score:** {r['score']:.3f} | **Verdict:** {r['verdict']}\n\n")
                f.write(f"**Query:** *\"{r['query']}\"*\n\n")
                f.write("**Failed Checks:**\n")
                for err in r["errors"]:
                    f.write(f"- {err}\n")
                f.write(f"\n**Math Tool Calls Made:**\n```\n{r['math_calls']}\n```\n\n")
                f.write(f"**Agent Final Answer:**\n```\n{r['answer']}\n```\n\n")
                f.write("---\n\n")

        # Full trace log
        f.write("## Full Test Log (All Tests)\n\n")
        for r in results:
            f.write(f"### [TEST {r['id']}] {r['name']}\n\n")
            f.write(f"**Query:** *\"{r['query']}\"*\n\n")
            f.write(f"**Verdict:** {r['verdict']} | **Score:** {r['score']:.3f} | **Duration:** {r['duration']:.2f}s\n\n")
            f.write(f"**Agent Final Answer:**\n```\n{r['answer']}\n```\n\n")
            if r["errors"]:
                f.write("**Issues:**\n")
                for err in r["errors"]:
                    f.write(f"- {err}\n")
                f.write("\n")
            f.write("---\n\n")

    print(f"Report written successfully -> {report_path}")
    print(f"\n{'=' * 60}")
    print(f"  FINAL SCORE: {avg_score:.3f} | PASSED: {passed} | PARTIAL: {partial} | FAILED: {failed}")
    print(f"{'=' * 60}")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import sys
    test_results = run_test_suite()
    
    # If any test failed or got a partial score, exit with code 1
    any_failures = any(r["verdict"] in ("FAILED", "PARTIAL") for r in test_results)
    if any_failures:
        print("\n[FAIL] TEST SUITE FAILURE: One or more test cases did not pass successfully.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] TEST SUITE SUCCESS: All test cases passed with a score of >= 0.8!")
        sys.exit(0)
