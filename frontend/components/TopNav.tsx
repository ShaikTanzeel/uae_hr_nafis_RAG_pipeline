"use client";

// components/TopNav.tsx — Top header bar
// Design source: Stitch "HR Co-Pilot: Refined Layout & Hierarchy"

interface TopNavProps {
  onClearChat: () => void;
}

export default function TopNav({ onClearChat }: TopNavProps) {
  return (
    <header
      className="sticky top-0 z-40 flex justify-between items-center w-full px-6 h-16 flex-shrink-0"
      style={{
        background: "var(--color-surface-container-lowest)",
        borderBottom: "1px solid var(--color-surface-variant)",
        boxShadow: "0 1px 4px rgba(0,30,64,0.06)",
      }}
    >
      {/* Brand + nav links */}
      <div className="flex items-center gap-8">
        <h2
          className="font-extrabold"
          style={{
            fontSize: 20,
            color: "var(--color-primary)",
            letterSpacing: "-0.3px",
          }}
        >
          Legal Compliance Suite
        </h2>
        <nav className="hidden md:flex gap-6">
          {["Dashboard", "Policies", "Legal Archive"].map((link) => (
            <a
              key={link}
              href="#"
              className="transition-colors"
              style={{
                fontSize: 13,
                fontFamily: "var(--font-label)",
                fontWeight: 500,
                color: "var(--color-on-surface-variant)",
              }}
              onMouseEnter={(e) =>
                ((e.target as HTMLElement).style.color = "var(--color-primary)")
              }
              onMouseLeave={(e) =>
                ((e.target as HTMLElement).style.color =
                  "var(--color-on-surface-variant)")
              }
            >
              {link}
            </a>
          ))}
        </nav>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        {/* Guardrail badge */}
        <div
          className="hidden md:flex items-center gap-1.5 px-3 py-1 rounded-full"
          style={{
            background: "rgba(34,197,94,0.1)",
            border: "1px solid rgba(34,197,94,0.3)",
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: "#16a34a" }}>
            verified_user
          </span>
          <span
            style={{
              fontSize: 11,
              fontFamily: "var(--font-label)",
              fontWeight: 600,
              color: "#16a34a",
              letterSpacing: "0.5px",
            }}
          >
            Guardrails Active
          </span>
        </div>

        <button
          className="transition-colors rounded-full p-1.5 flex items-center justify-center"
          style={{ color: "var(--color-on-surface-variant)" }}
          title="Clear conversation"
          onClick={onClearChat}
          onMouseEnter={(e) =>
            ((e.currentTarget as HTMLElement).style.color = "var(--color-primary)")
          }
          onMouseLeave={(e) =>
            ((e.currentTarget as HTMLElement).style.color =
              "var(--color-on-surface-variant)")
          }
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
            delete_sweep
          </span>
        </button>

        <div
          className="flex items-center gap-2 pl-3"
          style={{ borderLeft: "1px solid var(--color-surface-variant)" }}
        >
          <button
            className="transition-colors rounded-full p-1.5"
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
              notifications
            </span>
          </button>

          {/* Avatar placeholder */}
          <div
            className="rounded-full flex items-center justify-center text-white font-bold flex-shrink-0"
            style={{
              width: 32,
              height: 32,
              background: "var(--color-primary-container)",
              fontSize: 13,
              border: "1px solid var(--color-outline-variant)",
            }}
          >
            HR
          </div>
        </div>
      </div>
    </header>
  );
}
