"use client";

// components/CitationCard.tsx
// Legal article source citation pill/card
// Design source: Stitch — horizontal card with gavel icon, article number, "View" on hover

import type { Citation } from "@/types/chat";

const docIconMap: Record<string, string> = {
  "Federal Decree": "gavel",
  "Cabinet Resolution": "description",
  "Cabinet Regulation": "policy",
  default: "article",
};

function getIcon(sourceDocument: string): string {
  for (const [key, icon] of Object.entries(docIconMap)) {
    if (sourceDocument.includes(key)) return icon;
  }
  return docIconMap.default;
}

interface CitationCardProps {
  citation: Citation;
  onView?: (citation: Citation) => void;
}

export default function CitationCard({ citation, onView }: CitationCardProps) {
  return (
    <div
      className="flex items-center justify-between p-3 rounded-3xl cursor-pointer group shadow-sm transition-colors"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-outline-variant)",
        width: 240,
        flexShrink: 0,
      }}
      onClick={() => onView?.(citation)}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor =
          "var(--color-secondary)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor =
          "var(--color-outline-variant)";
      }}
    >
      <div className="flex items-center gap-2">
        <div
          className="rounded-full flex items-center justify-center flex-shrink-0"
          style={{
            width: 36,
            height: 36,
            background: "rgba(0,30,64,0.08)",
          }}
        >
          <span
            className="material-symbols-outlined"
            style={{ fontSize: 18, color: "var(--color-primary)" }}
          >
            {getIcon(citation.source_document)}
          </span>
        </div>
        <div>
          <p
            style={{
              fontSize: 11,
              fontFamily: "var(--font-label)",
              fontWeight: 700,
              color: "var(--color-on-surface)",
              lineHeight: 1.2,
            }}
          >
            {citation.source_document.includes("Federal")
              ? "UAE Labor Law"
              : citation.source_document.includes("Cabinet Resolution")
              ? "Executive Regulation"
              : "Nafis Regulation"}
          </p>
          <p
            style={{
              fontSize: 11,
              color: "var(--color-on-surface-variant)",
              marginTop: 1,
            }}
          >
            {citation.article_number}
          </p>
        </div>
      </div>
      <span
        className="opacity-0 group-hover:opacity-100 transition-opacity"
        style={{
          fontSize: 12,
          fontFamily: "var(--font-label)",
          fontWeight: 600,
          color: "var(--color-secondary)",
        }}
      >
        View
      </span>
    </div>
  );
}
