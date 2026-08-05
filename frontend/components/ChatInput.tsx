"use client";

// components/ChatInput.tsx
// Pinned bottom input bar with rounded pill input + gradient send button
// Design source: Stitch — rounded-full input, arrow_upward send button

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: () => void;
  loading: boolean;
  placeholder?: string;
}

const QUICK_PROMPTS = [
  "End-of-service gratuity for 3 years of service at AED 15,000/month?",
  "What is the probation period notice rule?",
  "Sham Emiratisation fine for 4 workers?",
  "Maternity leave entitlement under UAE Labour Law?",
];

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  loading,
  placeholder = "Ask a legal compliance question...",
}: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !loading && value.trim()) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div
      className="shrink-0 z-10 w-full"
      style={{
        background: "var(--color-surface-container-lowest)",
        borderTop: "1px solid var(--color-outline-variant)",
        padding: "16px 24px 12px",
      }}
    >
      {/* Quick prompts */}
      {!value && (
        <div className="flex gap-2 flex-wrap mb-3 max-w-3xl mx-auto">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => onChange(prompt)}
              className="transition-colors rounded-full px-3 py-1"
              style={{
                fontSize: 11,
                fontFamily: "var(--font-label)",
                fontWeight: 500,
                color: "var(--color-on-surface-variant)",
                background: "var(--color-surface-container)",
                border: "1px solid var(--color-outline-variant)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: 260,
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="max-w-3xl mx-auto relative flex items-center">
        <input
          id="chat-input"
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={loading}
          className="w-full rounded-full"
          style={{
            background: "var(--color-surface-container-lowest)",
            border: "1px solid var(--color-outline-variant)",
            paddingLeft: 20,
            paddingRight: 52,
            paddingTop: 12,
            paddingBottom: 12,
            fontSize: 15,
            color: "var(--color-on-surface)",
            outline: "none",
            fontFamily: "var(--font-sans)",
            boxShadow: "0 1px 4px rgba(0,30,64,0.06)",
            opacity: loading ? 0.6 : 1,
          }}
          onFocus={(e) => {
            (e.target as HTMLInputElement).style.borderColor = "var(--color-primary)";
            (e.target as HTMLInputElement).style.boxShadow =
              "0 0 0 2px rgba(0,30,64,0.12)";
          }}
          onBlur={(e) => {
            (e.target as HTMLInputElement).style.borderColor =
              "var(--color-outline-variant)";
            (e.target as HTMLInputElement).style.boxShadow =
              "0 1px 4px rgba(0,30,64,0.06)";
          }}
        />
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="btn-primary absolute right-2 rounded-full shadow-md flex items-center justify-center"
          style={{
            width: 40,
            height: 40,
            opacity: loading || !value.trim() ? 0.5 : 1,
            cursor: loading || !value.trim() ? "not-allowed" : "pointer",
          }}
          aria-label="Send message"
        >
          {loading ? (
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 20, animation: "spin 1s linear infinite" }}
            >
              progress_activity
            </span>
          ) : (
            <span className="material-symbols-outlined" style={{ fontSize: 20, fontWeight: 700 }}>
              arrow_upward
            </span>
          )}
        </button>
      </div>

      {/* Disclaimer */}
      <p
        className="text-center mt-2"
        style={{
          fontSize: 9,
          color: "var(--color-on-surface-variant)",
          fontFamily: "var(--font-label)",
          fontWeight: 600,
          letterSpacing: "0.8px",
          textTransform: "uppercase",
        }}
      >
        AI-generated legal insights. Always verify with official documentation.
      </p>
    </div>
  );
}
