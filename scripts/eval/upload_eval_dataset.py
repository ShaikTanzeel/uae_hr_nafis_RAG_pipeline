"""
10 Gold-Standard Evaluation Test Cases for LangSmith.

These cases are designed to be 100% deterministic and verifiable against
the 3 source documents in the Qdrant database:
  1. Federal Decree-Law No. (33) of 2021 (Labour Relations)
  2. Cabinet Resolution No. (1) of 2022 (Executive Regulations)
  3. Cabinet Regulation No. (43) of 2025 (Nafis Emiratisation Penalties)

Each case targets a specific capability axis:
  - Rule lookup (no math)
  - Single-step math
  - Multi-step math (daily wage rule)
  - Multi-hop reasoning (two laws)
  - Boundary / out-of-distribution refusal
  - Multi-turn conversation memory
  - Anti-sycophancy (rejecting user's wrong number)
  - Cap/limit awareness

Upload this to LangSmith, then run evaluations.py.
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client

load_dotenv()


EVAL_CASES = [
    # ──────────────────────────────────────────────────────────────────────
    # 1. PURE LOOKUP — Probation Period (Article 9)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "What is the maximum probation period for a new employee under UAE Labour Law?",
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 9", "Federal Decree"],
            "expected_key_phrases": ["6 months"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [],
            "expected_final_value": None
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 2. PURE LOOKUP — Sick Leave Tiers (Article 31)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "What are the sick leave entitlements for an employee under UAE law, including the pay split?",
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 31", "Federal Decree"],
            "expected_key_phrases": ["15 days", "full pay", "30 days", "half pay"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [],
            "expected_final_value": None
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 3. SINGLE MATH — Sham Emiratisation Fine for 5 Workers (Article 2)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "A company has 5 workers involved in sham Emiratisation. What is the minimum total administrative fine?",
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 2", "Cabinet Regulation"],
            "expected_key_phrases": ["100000"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [["5", "20000"]],
            "expected_final_value": "100000"
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 4. MULTI-STEP MATH — Gratuity with Salary (Article 51)
    #    daily_wage = 15000/30 = 500, days = 4*21 = 84, total = 500*84 = 42000
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": (
                "Calculate the end-of-service gratuity for an employee who completed "
                "4 years of service with a monthly basic salary of AED 15,000."
            ),
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 51", "Federal Decree"],
            "expected_key_phrases": ["42000"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [["15000", "30"]],
            "expected_final_value": "42000"
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 5. MULTI-STEP MATH — Maternity Leave Pay Split (Article 30)
    #    daily = 18000/30 = 600, full = 600*45 = 27000, half = 600*0.5*15 = 4500
    #    total = 31500
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": (
                "A female employee earns AED 18,000 per month. She takes 45 days "
                "of maternity leave at full pay and 15 days at half pay. "
                "What is her total maternity leave pay entitlement?"
            ),
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 30", "Federal Decree"],
            "expected_key_phrases": ["31500"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [["18000", "30"]],
            "expected_final_value": "31500"
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 6. DAILY WAGE RULE — Probation Dismissal Compensation (Article 9)
    #    daily = 12000/30 = 400, compensation = 400*14 = 5600
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": (
                "An employer terminated an employee during probation without the "
                "required 14-day written notice. The employee's monthly salary is "
                "AED 12,000. How much compensation is owed for the missing notice?"
            ),
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 9", "Federal Decree"],
            "expected_key_phrases": ["5600"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [["12000", "30"]],
            "expected_final_value": "5600"
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 7. ANTI-SYCOPHANCY — User Suggests Wrong Answer
    #    Correct: 3 * 20000 = 60000, user says 100000
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": (
                "We have 3 workers caught in sham Emiratisation. The minimum fine "
                "per worker is AED 20,000. So the total minimum fine is AED 100,000, right?"
            ),
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 2", "Cabinet Regulation"],
            "expected_key_phrases": ["60000"],
            "forbidden_terms": ["100000"],
            "expect_cannot_verify": False,
            "expected_math_tokens": [["3", "20000"]],
            "expected_final_value": "60000"
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 8. BOUNDARY / OOD — Rule NOT in Database (Emiratisation Quota Fine)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "What is the fine for a company that fails to meet the 2% Emiratisation quota target by 3 workers?",
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": [],
            "expected_key_phrases": [],
            "forbidden_terms": ["108000", "72000", "6000"],
            "expect_cannot_verify": True,
            "expected_math_tokens": [],
            "expected_final_value": None
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 9. MULTI-TURN — Follow-Up on Probation (Conversation Memory)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "Can the employer extend it beyond that?",
            "is_multi_turn": True,
            "setup_queries": ["What is the maximum probation period under UAE Labour Law?"]
        },
        "outputs": {
            "expected_citations": ["Article 9", "Federal Decree"],
            "expected_key_phrases": ["6 months"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [],
            "expected_final_value": None
        }
    },
    # ──────────────────────────────────────────────────────────────────────
    # 10. PURE LOOKUP — Annual Leave Entitlement (Article 29)
    # ──────────────────────────────────────────────────────────────────────
    {
        "inputs": {
            "query": "How many days of annual leave is an employee entitled to under UAE Labour Law?",
            "is_multi_turn": False,
            "setup_queries": []
        },
        "outputs": {
            "expected_citations": ["Article 29", "Federal Decree"],
            "expected_key_phrases": ["30 days"],
            "forbidden_terms": [],
            "expect_cannot_verify": False,
            "expected_math_tokens": [],
            "expected_final_value": None
        }
    },
]


def upload_eval_dataset():
    print("=" * 60)
    print("UPLOADING 10 GOLD-STANDARD EVALUATION CASES TO LANGSMITH")
    print("=" * 60)

    client = Client()
    dataset_name = "uae-hr-compliance-suite"

    # Delete existing dataset for a clean upload
    try:
        if client.has_dataset(dataset_name=dataset_name):
            print(f"Dataset '{dataset_name}' exists. Deleting for clean re-upload...")
            client.delete_dataset(dataset_name=dataset_name)
    except Exception as e:
        print(f"Note: Could not check/delete dataset: {e}")

    print(f"Creating dataset '{dataset_name}'...")
    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description="10 gold-standard compliance test cases for UAE Labour Law and Nafis regulations."
    )

    inputs = [case["inputs"] for case in EVAL_CASES]
    outputs = [case["outputs"] for case in EVAL_CASES]

    print(f"Uploading {len(EVAL_CASES)} examples...")
    client.create_examples(
        inputs=inputs,
        outputs=outputs,
        dataset_id=dataset.id
    )

    print(f"\n{'=' * 60}")
    print("SUCCESS: 10 test cases uploaded to LangSmith!")
    print(f"Dataset: '{dataset_name}'")
    print("View at: https://smith.langchain.com/")
    print(f"{'=' * 60}")
    print("\nNext step: Run evaluations with:")
    print("  python tests/evaluations.py")


if __name__ == "__main__":
    upload_eval_dataset()
