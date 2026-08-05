"use client";

// app/page.tsx — Main HR Co-Pilot Chat Page
// Wires Sidebar, TopNav, ChatMessage, ChatInput, DocumentPreview
// All state management for chat history + API calls lives here

import { useState, useEffect, useRef, useCallback } from "react";
import type { DisplayMessage, ChatMessage, Citation, HealthResponse, LawDocument } from "@/types/chat";
import { sendChat, fetchHealth, fetchLaws } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import ChatMessage_Component from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import DocumentPreview from "@/components/DocumentPreview";

let msgIdCounter = 0;
function newId() {
  return `msg-${Date.now()}-${msgIdCounter++}`;
}

// Welcome message shown when chat is empty
const WELCOME: DisplayMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "**Welcome to the UAE Federal HR & Nafis Copilot**\n\n" +
    "I am a regulatory compliance assistant grounded in the official federal database. I can help you with:\n\n" +
    "• **End-of-Service Gratuity** — Contract terms, service duration, salary-based calculations\n" +
    "• **Emiratisation & Nafis Fines** — Sham Emiratisation penalties, quota violations\n" +
    "• **Probation & Notice Periods** — Federal Decree-Law No. 33 of 2021 constraints\n" +
    "• **Leave Entitlements** — Annual, sick, and maternity leave rules\n\n" +
    "Type your question below to begin.",
  citations: [],
  cannot_verify: false,
  confidence: 1.0,
  timestamp: new Date(),
};

export default function HomePage() {
  const [messages, setMessages] = useState<DisplayMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Raw API history used for multi-turn context
  const [apiHistory, setApiHistory] = useState<ChatMessage[]>([]);

  // Right panel — selected citation preview
  const [previewCitation, setPreviewCitation] = useState<Citation | null>(null);
  const [previewContext, setPreviewContext] = useState<string | undefined>();

  // System status
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [laws, setLaws] = useState<LawDocument[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load system status once on mount
  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
    fetchLaws()
      .then(setLaws)
      .catch(() => setLaws([]));
  }, []);

  const handleNewConsultation = useCallback(() => {
    setMessages([WELCOME]);
    setApiHistory([]);
    setInput("");
    setError(null);
    setPreviewCitation(null);
    setPreviewContext(undefined);
  }, []);

  const handleSubmit = useCallback(async () => {
    const query = input.trim();
    if (!query || loading) return;

    setInput("");
    setError(null);

    // Optimistically add user message
    const userMsg: DisplayMessage = {
      id: newId(),
      role: "user",
      content: query,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await sendChat({ query, history: apiHistory });

      // Find tool call expression/result from API history output
      let toolExpression: string | undefined;
      let toolResult: string | undefined;
      const outHistory = response.history;
      for (let i = 0; i < outHistory.length; i++) {
        const msg = outHistory[i];
        if (
          msg.role === "assistant" &&
          msg.tool_calls &&
          msg.tool_calls.length > 0
        ) {
          try {
            const args = JSON.parse(msg.tool_calls[0].function.arguments);
            toolExpression = args.expression ?? undefined;
          } catch {
            toolExpression = msg.tool_calls[0].function.arguments;
          }
          // Look for tool result in the next message
          if (i + 1 < outHistory.length && outHistory[i + 1].role === "tool") {
            toolResult = outHistory[i + 1].content ?? undefined;
          }
        }
      }

      const agentMsg: DisplayMessage = {
        id: newId(),
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        retrieved_context: response.retrieved_context,
        cannot_verify: response.cannot_verify,
        confidence: response.confidence,
        tool_expression: toolExpression,
        tool_result: toolResult,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, agentMsg]);
      setApiHistory(response.history as ChatMessage[]);

      // If injection blocked, show a persistent error
      if (response.injection_blocked) {
        setError("⚠️ Query was blocked by the security guardrail.");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(`Failed to reach the backend: ${message}`);
    } finally {
      setLoading(false);
    }
  }, [input, loading, apiHistory]);

  const handleCitationView = useCallback(
    (citation: Citation) => {
      setPreviewCitation(citation);
      // Find the last agent message that has retrieved_context
      const lastAgentMsg = [...messages]
        .reverse()
        .find((m) => m.role === "assistant" && m.retrieved_context);
      setPreviewContext(lastAgentMsg?.retrieved_context);
    },
    [messages]
  );

  const showPreview = previewCitation !== null;

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--color-surface)" }}>
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <Sidebar
        onNewConsultation={handleNewConsultation}
        health={health}
        laws={laws}
      />

      {/* ── Main area (offset by sidebar width) ─────────────────── */}
      <main
        className="flex flex-col h-full overflow-hidden"
        style={{ marginLeft: "var(--spacing-sidebar)", flex: 1 }}
      >
        {/* Top nav */}
        <TopNav onClearChat={handleNewConsultation} />

        {/* Chat workspace + document preview */}
        <div className="flex flex-1 overflow-hidden">
          {/* Chat column */}
          <div
            className="flex flex-col overflow-hidden relative"
            style={{
              flex: 1,
              borderRight: showPreview ? "1px solid var(--color-outline-variant)" : "none",
            }}
          >
            {/* Scrollable message list */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {messages.map((msg) => (
                <ChatMessage_Component
                  key={msg.id}
                  message={msg}
                  onCitationView={handleCitationView}
                />
              ))}

              {/* Loading indicator */}
              {loading && (
                <div className="flex justify-start">
                  <div
                    className="bubble-agent p-4 flex items-center gap-3"
                    style={{
                      background: "var(--color-surface-container-lowest)",
                      border: "1px solid var(--color-outline-variant)",
                    }}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{
                        fontSize: 20,
                        color: "var(--color-primary-container)",
                        animation: "spin 1s linear infinite",
                      }}
                    >
                      progress_activity
                    </span>
                    <span
                      style={{
                        fontSize: 13,
                        fontFamily: "var(--font-label)",
                        color: "var(--color-on-surface-variant)",
                      }}
                    >
                      Retrieving federal articles from Qdrant…
                    </span>
                  </div>
                </div>
              )}

              {/* Error banner */}
              {error && (
                <div
                  className="rounded-xl p-4 flex items-start gap-3"
                  style={{
                    background: "rgba(186,26,26,0.06)",
                    border: "1px solid rgba(186,26,26,0.2)",
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 18, color: "var(--color-error)", flexShrink: 0 }}
                  >
                    error
                  </span>
                  <div>
                    <p
                      style={{
                        fontSize: 13,
                        fontFamily: "var(--font-label)",
                        fontWeight: 600,
                        color: "var(--color-error)",
                        marginBottom: 2,
                      }}
                    >
                      Error
                    </p>
                    <p
                      style={{
                        fontSize: 13,
                        color: "var(--color-on-surface)",
                        lineHeight: 1.5,
                      }}
                    >
                      {error}
                    </p>
                  </div>
                  <button
                    onClick={() => setError(null)}
                    style={{ marginLeft: "auto", color: "var(--color-on-surface-variant)" }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                      close
                    </span>
                  </button>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Pinned chat input */}
            <ChatInput
              value={input}
              onChange={setInput}
              onSubmit={handleSubmit}
              loading={loading}
            />
          </div>

          {/* Document preview panel */}
          {showPreview && (
            <DocumentPreview
              citation={previewCitation}
              retrievedContext={previewContext}
              onClose={() => {
                setPreviewCitation(null);
                setPreviewContext(undefined);
              }}
            />
          )}
        </div>
      </main>

      {/* Keyframe for spinner — injected inline to avoid needing Tailwind animation config */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
