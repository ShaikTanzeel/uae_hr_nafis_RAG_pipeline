"""
schemas.py — Structured Output Contracts for the UAE HR & Nafis Copilot

WHY THIS FILE EXISTS:
  The agent's raw text answer is great for humans but impossible for code to
  reliably work with. This file defines a strict "form" (a Pydantic schema)
  that the agent must fill in alongside every text answer.

  Every downstream system — the UI, the evaluators, the guardrails — reads
  from this structured form instead of trying to regex-scrape the text.

WHAT IS PYDANTIC?
  Pydantic is a Python library that lets you define a "template" for data.
  If the data doesn't match the template (e.g., confidence is a string
  instead of a number), Pydantic raises a clear error immediately.
  Think of it as a strict form validator.
"""

from pydantic import BaseModel, Field
from typing import Optional


class Citation(BaseModel):
    """
    Represents a single legal citation made by the agent.

    Example:
        Citation(
            article_number="Article 9",
            source_document="Federal Decree by Law No. (33) of 2021"
        )
    """
    article_number: str = Field(
        description="The article number as cited, e.g. 'Article 9' or 'Article 2'"
    )
    source_document: str = Field(
        description="The full name of the source law document, e.g. 'Federal Decree by Law No. (33) of 2021'"
    )


class AgentResponse(BaseModel):
    """
    The complete structured output from a single agent turn.

    This is the 'form' the agent fills in at the end of every response.
    It sits ALONGSIDE the human-readable text answer — not replacing it.

    Fields:
        answer        — The full text answer shown to the user.
        citations     — List of legal citations used (structured, not just text).
        articles_used — Flat list of article numbers for quick lookup.
        confidence    — How confident the agent is (0.0 = guessing, 1.0 = certain).
        cannot_verify — True if the agent couldn't find the rule in retrieved articles.
    """
    answer: str = Field(
        default="",
        description="The full human-readable answer text."
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Structured list of all legal citations made in the answer."
    )
    articles_used: list[str] = Field(
        default_factory=list,
        description="Flat list of article numbers for quick lookup, e.g. ['Article 9', 'Article 30']."
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,   # Must be >= 0.0
        le=1.0,   # Must be <= 1.0
        description="Agent's confidence score from 0.0 (no match) to 1.0 (perfect match)."
    )
    cannot_verify: bool = Field(
        default=False,
        description="True if the agent could not locate the relevant rule in the retrieved articles."
    )


# ==============================================================================
# QUICK SELF-TEST — run this file directly to confirm Pydantic is working
# python src/schemas.py
# ==============================================================================
if __name__ == "__main__":
    print("Testing AgentResponse schema...")

    # Test 1: Valid response
    valid = AgentResponse(
        answer="The probation period is 6 months under UAE Labour Law.",
        citations=[
            Citation(
                article_number="Article 9",
                source_document="Federal Decree by Law No. (33) of 2021"
            )
        ],
        articles_used=["Article 9"],
        confidence=0.92,
        cannot_verify=False
    )
    print(f"  Test 1 (valid): PASSED — {valid.model_dump()}")

    # Test 2: Cannot-verify scenario
    no_match = AgentResponse(
        answer="I cannot verify this in the retrieved articles.",
        citations=[],
        articles_used=[],
        confidence=0.0,
        cannot_verify=True
    )
    print(f"  Test 2 (cannot_verify): PASSED — {no_match.model_dump()}")

    # Test 3: Invalid confidence value (should raise ValidationError)
    try:
        bad = AgentResponse(
            answer="Test",
            citations=[],
            articles_used=[],
            confidence=1.5,  # INVALID: must be <= 1.0
            cannot_verify=False
        )
        print("  Test 3 (bad confidence): FAILED — should have raised an error!")
    except Exception as e:
        print(f"  Test 3 (bad confidence): CORRECTLY raised error — {type(e).__name__}")

    print("\nAll schema tests complete.")
