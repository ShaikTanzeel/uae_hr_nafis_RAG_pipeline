"use client";

// components/ReasoningAccordion.tsx
// Collapsible "System Reasoning" section showing RAG pipeline phases
// Design source: Stitch — <details> monospace accordion with bg-surface-container-low

import { useState } from "react";

interface Step {
  text: string;
  type?: "info" | "match" | "system";
}

interface ReasoningAccordionProps {
  steps: Step[];
  toolExpression?: string;
  toolResult?: string;
}

export default function ReasoningAccordion({
  steps,
  toolExpression,
  toolResult,
}: ReasoningAccordionProps) {
  const [open, setOpen] = useState(false);

  return (
    <div
      className="rounded-2xl overflow-hidden my-2"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-outline-variant)",
      }}
    >
      <button
        className="w-full flex justify-between items-center px-4 py-3 transition-colors"
        style={{
          background: open
            ? "var(--color-surface-container-high)"
            : "var(--color-surface-container-low)",
          cursor: "pointer",
          borderBottom: open ? "1px solid var(--color-outline-variant)" : "none",
        }}
        onClick={() => setOpen(!open)}
        onMouseEnter={(e) =>
          ((e.currentTarget as HTMLElement).style.background =
            "var(--color-surface-container-high)")
        }
        onMouseLeave={(e) =>
          ((e.currentTarget as HTMLElement).style.background = open
            ? "var(--color-surface-container-high)"
            : "var(--color-surface-container-low)")
        }
      >
        <div
          className="flex items-center gap-2"
          style={{ color: "var(--color-on-surface-variant)" }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
            account_tree
          </span>
          <span
            style={{
              fontSize: 12,
              fontFamily: "var(--font-label)",
              fontWeight: 600,
            }}
          >
            System Reasoning
          </span>
        </div>
        <span
          className="material-symbols-outlined"
          style={{
            fontSize: 20,
            color: "var(--color-on-surface-variant)",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        >
          expand_more
        </span>
      </button>

      {open && (
        <div className="p-4 space-y-1.5" style={{ background: "var(--color-surface)" }}>
          {steps.map((step, i) => (
            <p
              key={i}
              className="reasoning-mono opacity-80"
              style={{
                color:
                  step.type === "match"
                    ? "var(--color-secondary)"
                    : step.type === "system"
                    ? "var(--color-on-primary-container)"
                    : "var(--color-on-surface-variant)",
                fontWeight: step.type === "system" ? 600 : 400,
              }}
            >
              {step.text}
            </p>
          ))}

          {/* Math tool call display */}
          {toolExpression && toolResult && (
            <div
              className="mt-3 p-3 rounded-xl"
              style={{
                background: "var(--color-primary-fixed)",
                border: "1px solid var(--color-primary-fixed-dim)",
              }}
            >
              <p
                style={{
                  fontSize: 10,
                  fontFamily: "var(--font-label)",
                  fontWeight: 600,
                  letterSpacing: "0.5px",
                  textTransform: "uppercase",
                  color: "var(--color-on-primary-fixed)",
                  marginBottom: 4,
                }}
              >
                📊 AST Calculator
              </p>
              <code
                className="reasoning-mono"
                style={{
                  color: "var(--color-on-primary-fixed)",
                  display: "block",
                }}
              >
                {toolExpression} → <strong>{toolResult}</strong>
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
