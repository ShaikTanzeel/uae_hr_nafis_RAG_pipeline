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


class CitationExtraction(BaseModel):
    """
    PHASE 2 — TASK C2: the small schema used by the post-stream structured-output
    extraction call (see stream_agent_turn's citation_check step in src/agent.py).

    This is deliberately NOT the same shape as AgentResponse. The streamed answer
    text already exists by the time this runs, so there's no 'answer' field here —
    and confidence is always calculated by the server from verify_citations(), so
    it's not here either. This schema's only job is: given a finished answer and
    the retrieved context, tell us exactly which citations and articles were used.

    Example:
        CitationExtraction(
            citations=[Citation(article_number="Article 9", source_document="Federal Decree by Law No. (33) of 2021")],
            articles_used=["Article 9"],
            cannot_verify=False
        )
    """
    citations: list[Citation] = Field(
        default_factory=list,
        description="Structured list of all legal citations made in the answer text."
    )
    articles_used: list[str] = Field(
        default_factory=list,
        description="Flat list of article numbers actually cited in the answer, e.g. ['Article 9', 'Article 30']."
    )
    cannot_verify: bool = Field(
        default=False,
        description="True if the answer text says the rule could not be verified in the retrieved articles."
    )


class AgentResponse(BaseModel):
    """
    The complete structured result of a single agent turn, assembled AFTER the
    fact from three separate sources (PHASE 2 — TASK C6, replacing the old
    single hidden-JSON-block design):

      - answer: the full text streamed to the user (Section A).
      - citations / articles_used: pulled from the finished answer by the
        CitationExtraction structured-output call (Section C2/C3), not written
        by the model itself as a trailing JSON block anymore.
      - confidence: calculated entirely server-side from verify_citations()
        (Section C5) — never a number the model reports about itself.

    Fields:
        answer        — The full text answer shown to the user.
        citations     — List of legal citations used (structured, not just text).
        articles_used — Flat list of article numbers for quick lookup.
        confidence    — Server-calculated confidence (0.0 = unverified, 1.0 = fully grounded).
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
