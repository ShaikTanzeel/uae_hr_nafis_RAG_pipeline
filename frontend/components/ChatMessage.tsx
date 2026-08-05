"use client";

// components/ChatMessage.tsx
// User and AI chat bubbles with asymmetric rounding (from Stitch spec)
// AI bubbles include ReasoningAccordion + CitationCards

import type { DisplayMessage, Citation } from "@/types/chat";
import ReasoningAccordion from "./ReasoningAccordion";
import CitationCard from "./CitationCard";

interface ChatMessageProps {
  message: DisplayMessage;
  onCitationView?: (citation: Citation) => void;
}

function buildReasoningSteps(message: DisplayMessage) {
  const steps = [];
  steps.push({ text: "> Sanitizing input — prompt injection check..." });
  steps.push({ text: "> Phase A: Querying Qdrant vector database..." });
  steps.push({
    text: "> Rewriting query for multi-turn context (LLM)...",
  });
  steps.push({ text: "> Retrieving top-5 law article chunks..." });
  if (message.citations && message.citations.length > 0) {
    for (const c of message.citations) {
      steps.push({
        text: `> Match: ${c.article_number} — ${c.source_document.split(" (")[0]}`,
        type: "match" as const,
      });
    }
  }
  steps.push({ text: "> Phase B: LangGraph agent reasoning...", type: "system" as const });
  steps.push({ text: "> Phase C: Citation verification guardrail...", type: "system" as const });
  if (message.cannot_verify) {
    steps.push({
      text: "> WARNING: Could not verify claims in retrieved context.",
      type: "system" as const,
    });
  } else {
    steps.push({ text: "> Guardrail PASSED — citations verified.", type: "system" as const });
  }
  return steps;
}

export default function ChatMessage({ message, onCitationView }: ChatMessageProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="bubble-user p-5 max-w-2xl shadow-sm"
          style={{
            background: "var(--color-surface-container-lowest)",
            border: "1px solid var(--color-outline-variant)",
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <span
              style={{
                fontSize: 11,
                fontFamily: "var(--font-label)",
                fontWeight: 600,
                color: "var(--color-on-surface-variant)",
              }}
            >
              You
            </span>
          </div>
          <p
            style={{
              fontSize: 15,
              fontWeight: 300,
              color: "var(--color-on-surface)",
              lineHeight: 1.6,
            }}
          >
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  // ── AI Message ──────────────────────────────────────────────────────────────
  const steps = buildReasoningSteps(message);

  return (
    <div className="flex justify-start">
      <div
        className="bubble-agent p-5 max-w-3xl shadow-sm flex flex-col gap-4"
        style={{
          background: "var(--color-surface-container-lowest)",
          border: "1px solid var(--color-outline-variant)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2"
          style={{ color: "var(--color-primary-container)" }}
        >
          <span className="material-symbols-outlined filled" style={{ fontSize: 22 }}>
            smart_toy
          </span>
          <span
            style={{
              fontSize: 13,
              fontFamily: "var(--font-label)",
              fontWeight: 700,
            }}
          >
            HR Co-Pilot
          </span>
          {message.confidence !== undefined && (
            <span
              className="ml-auto rounded-full px-2 py-0.5"
              style={{
                fontSize: 10,
                fontFamily: "var(--font-label)",
                fontWeight: 600,
                background:
                  message.confidence >= 0.8
                    ? "rgba(34,197,94,0.1)"
                    : message.confidence >= 0.5
                    ? "rgba(234,179,8,0.1)"
                    : "rgba(239,68,68,0.1)",
                color:
                  message.confidence >= 0.8
                    ? "#16a34a"
                    : message.confidence >= 0.5
                    ? "#d97706"
                    : "#dc2626",
                border: `1px solid ${
                  message.confidence >= 0.8
                    ? "rgba(34,197,94,0.3)"
                    : message.confidence >= 0.5
                    ? "rgba(234,179,8,0.3)"
                    : "rgba(239,68,68,0.3)"
                }`,
              }}
            >
              {Math.round((message.confidence ?? 0) * 100)}% confidence
            </span>
          )}
        </div>

        {/* Reasoning accordion */}
        <ReasoningAccordion
          steps={steps}
          toolExpression={message.tool_expression}
          toolResult={message.tool_result}
        />

        {/* Answer text */}
        <div
          style={{
            fontSize: 15,
            fontWeight: 300,
            color: "var(--color-on-surface)",
            lineHeight: 1.65,
            whiteSpace: "pre-wrap",
          }}
        >
          {message.content}
        </div>

        {/* Cannot-verify warning */}
        {message.cannot_verify && (
          <div
            className="rounded-xl p-3 flex items-start gap-2"
            style={{
              background: "rgba(186,26,26,0.06)",
              border: "1px solid rgba(186,26,26,0.2)",
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 16, color: "var(--color-error)", flexShrink: 0 }}
            >
              warning
            </span>
            <p
              style={{
                fontSize: 12,
                fontFamily: "var(--font-label)",
                color: "var(--color-error)",
                fontWeight: 500,
              }}
            >
              This response could not be fully verified against the retrieved law articles.
            </p>
          </div>
        )}

        {/* Citation cards */}
        {message.citations && message.citations.length > 0 && (
          <div>
            <h4
              style={{
                fontSize: 9,
                fontFamily: "var(--font-label)",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.8px",
                color: "var(--color-on-surface-variant)",
                marginBottom: 8,
              }}
            >
              Source Citations
            </h4>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((c, i) => (
                <CitationCard key={i} citation={c} onView={onCitationView} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
