"use client";

// components/DocumentPreview.tsx
// Right-side panel showing the law article text when user clicks a citation
// Design source: Stitch — fixed right panel, serif font, highlighted clauses

import type { Citation } from "@/types/chat";

interface DocumentPreviewProps {
  citation: Citation | null;
  retrievedContext?: string;
  onClose: () => void;
}

export default function DocumentPreview({
  citation,
  retrievedContext,
  onClose,
}: DocumentPreviewProps) {
  if (!citation && !retrievedContext) return null;

  // Extract a snippet from retrieved_context that mentions the citation article
  const articleText = extractArticleText(retrievedContext, citation?.article_number);

  return (
    <div
      className="flex flex-col shadow-[-4px_0_12px_rgba(0,51,102,0.05)] z-10 relative"
      style={{
        width: "var(--spacing-preview, 380px)",
        flexShrink: 0,
        background: "var(--color-surface-container-lowest)",
        borderLeft: "1px solid var(--color-outline-variant)",
      }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between p-4 sticky top-0"
        style={{
          background: "var(--color-surface-container-lowest)",
          borderBottom: "1px solid var(--color-outline-variant)",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined"
            style={{ fontSize: 20, color: "var(--color-primary)" }}
          >
            menu_book
          </span>
          <h3
            style={{
              fontSize: 13,
              fontFamily: "var(--font-label)",
              fontWeight: 700,
              color: "var(--color-primary)",
            }}
          >
            Document Preview
          </h3>
        </div>
        <button
          onClick={onClose}
          className="transition-colors p-1 rounded"
          style={{ color: "var(--color-on-surface-variant)" }}
          onMouseEnter={(e) =>
            ((e.currentTarget as HTMLElement).style.color = "var(--color-primary)")
          }
          onMouseLeave={(e) =>
            ((e.currentTarget as HTMLElement).style.color =
              "var(--color-on-surface-variant)")
          }
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
            close
          </span>
        </button>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-y-auto p-5 space-y-4"
        style={{ background: "#fdfbf7", fontFamily: "Georgia, serif" }}
      >
        {citation && (
          <div
            className="text-center pb-4"
            style={{ borderBottom: "1px solid var(--color-outline-variant)" }}
          >
            <p
              style={{
                fontSize: 10,
                fontFamily: "var(--font-label)",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "1.5px",
                color: "var(--color-on-surface-variant)",
                marginBottom: 6,
              }}
            >
              {citation.source_document}
            </p>
            <h4
              style={{
                fontSize: 20,
                fontWeight: 600,
                color: "var(--color-primary)",
              }}
            >
              {citation.article_number}
            </h4>
          </div>
        )}

        {/* Article text from retrieved context */}
        {articleText ? (
          <div
            style={{
              fontSize: 14,
              color: "var(--color-on-surface)",
              lineHeight: 1.8,
              whiteSpace: "pre-wrap",
            }}
          >
            {articleText}
          </div>
        ) : (
          <div
            className="rounded-xl p-4"
            style={{
              background: "var(--color-surface-container)",
              border: "1px dashed var(--color-outline-variant)",
            }}
          >
            <p
              style={{
                fontSize: 13,
                color: "var(--color-on-surface-variant)",
                fontStyle: "italic",
                lineHeight: 1.6,
              }}
            >
              The full article text is retrieved from the Qdrant vector database
              on each query. Click a citation from an active response to preview
              the source article here.
            </p>
          </div>
        )}

        {/* Disclaimer */}
        <p
          className="rounded-xl p-3 mt-4"
          style={{
            fontSize: 11,
            color: "var(--color-on-surface-variant)",
            background: "rgba(0,30,64,0.04)",
            lineHeight: 1.6,
          }}
        >
          * This is an excerpt for context. Refer to the full official decree
          for comprehensive legal application.
        </p>
      </div>
    </div>
  );
}

/**
 * Extracts the most relevant text block from the raw retrieved_context string
 * (which is the formatted multi-match output from search_laws_tool).
 */
function extractArticleText(
  context: string | undefined,
  articleNumber: string | undefined
): string | null {
  if (!context || !articleNumber) return null;

  // Split by separator lines used in search_laws_tool output
  const blocks = context.split(/─{10,}/);

  const articleKey = articleNumber.replace("Article ", "").replace("Art. ", "").trim();

  for (const block of blocks) {
    if (
      block.includes(`Article Number: ${articleNumber}`) ||
      block.includes(`Article Number: Article ${articleKey}`)
    ) {
      // Extract just the Legal Text portion
      const legalTextMatch = block.match(/Legal Text:\n([\s\S]+?)$/);
      if (legalTextMatch) return legalTextMatch[1].trim();
      return block.trim();
    }
  }

  // Fallback: return first matching block
  for (const block of blocks) {
    if (block.includes(articleKey)) return block.trim();
  }

  return null;
}
