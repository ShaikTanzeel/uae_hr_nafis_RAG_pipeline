"use client";

// components/Sidebar.tsx — Left navigation panel
// Design source: Stitch "HR Co-Pilot: Refined Layout & Hierarchy"
// Sidebar background: #001e40 (primary), brand + "New Consultation" CTA + nav items

import type { HealthResponse, LawDocument } from "@/types/chat";

interface SidebarProps {
  onNewConsultation: () => void;
  health?: HealthResponse | null;
  laws?: LawDocument[];
}

const navItems = [
  { icon: "chat", label: "Co-Pilot Chat", href: "#", active: true },
  { icon: "library_books", label: "Document Library", href: "#" },
  { icon: "analytics", label: "Compliance Analytics", href: "#" },
  { icon: "receipt_long", label: "Audit Logs", href: "#" },
  { icon: "settings", label: "Settings", href: "#" },
];

const footerItems = [
  { icon: "help", label: "Support", href: "#" },
  { icon: "logout", label: "Sign Out", href: "#" },
];

export default function Sidebar({ onNewConsultation, health, laws }: SidebarProps) {
  return (
    <nav
      className="fixed h-full left-0 top-0 flex flex-col py-6 z-50"
      style={{
        width: "var(--spacing-sidebar)",
        backgroundColor: "var(--color-primary)",
        borderRight: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {/* ── Brand ──────────────────────────────────────────────────── */}
      <div className="px-4 mb-6">
        <div className="flex items-center gap-3">
          {/* UAE Flag mini */}
          <div
            className="flex-shrink-0 rounded overflow-hidden flex"
            style={{
              width: 36,
              height: 24,
              border: "1.5px solid rgba(255,255,255,0.25)",
            }}
          >
            <div style={{ width: "28%", background: "#EF3340" }} />
            <div style={{ width: "72%", display: "flex", flexDirection: "column" }}>
              <div style={{ flex: 1, background: "#009639" }} />
              <div style={{ flex: 1, background: "#FFFFFF" }} />
              <div style={{ flex: 1, background: "#000000" }} />
            </div>
          </div>
          <div>
            <h1
              className="font-bold leading-tight"
              style={{
                fontSize: 17,
                color: "var(--color-secondary-fixed)",
                letterSpacing: "-0.2px",
              }}
            >
              HR &amp; NAFIS BOT
            </h1>
            <p
              style={{
                fontSize: 9,
                color: "var(--color-secondary-fixed)",
                opacity: 0.75,
                fontFamily: "var(--font-label)",
                letterSpacing: "0.5px",
                textTransform: "uppercase",
              }}
            >
              Legal Compliance UAE
            </p>
          </div>
        </div>
      </div>

      {/* ── New Consultation CTA ────────────────────────────────────── */}
      <div className="px-3 mb-6">
        <button
          onClick={onNewConsultation}
          className="btn-gold w-full flex items-center justify-center gap-2 py-2 px-4 rounded-xl font-semibold shadow-md"
          style={{ fontFamily: "var(--font-label)", fontSize: 13 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>add</span>
          New Consultation
        </button>
      </div>

      {/* ── Main Navigation ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-2">
        <ul className="space-y-0.5">
          {navItems.map((item) => (
            <li key={item.label}>
              <a
                href={item.href}
                className={`nav-item flex items-center gap-3 px-3 py-2 rounded-xl ${
                  item.active ? "active" : ""
                }`}
                style={{
                  color: item.active ? "#ffffff" : "rgba(255,255,255,0.55)",
                  fontSize: 13,
                  fontFamily: "var(--font-label)",
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>

        {/* ── System Status ──────────────────────────────────────────── */}
        <div className="mt-6 mb-2 px-2">
          <p
            style={{
              fontSize: 9,
              fontFamily: "var(--font-label)",
              fontWeight: 600,
              letterSpacing: "1.2px",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.35)",
              marginBottom: 8,
            }}
          >
            System Status
          </p>
          <div className="space-y-1.5">
            <StatusCard label="Reasoning" value="GPT-4o-mini · OpenAI" />
            <StatusCard label="Embeddings" value="gemini-embedding-001" />
            <StatusCard
              label="Vector DB"
              value={
                health?.qdrant_connected
                  ? `Qdrant · ${health.vector_count ?? "–"} vectors`
                  : "Qdrant · offline"
              }
              ok={health?.qdrant_connected}
            />
            <StatusCard label="Temperature" value="0.0 (Deterministic)" />
          </div>
        </div>

        {/* ── Legal Corpus ───────────────────────────────────────────── */}
        {laws && laws.length > 0 && (
          <div className="mt-4 px-2">
            <p
              style={{
                fontSize: 9,
                fontFamily: "var(--font-label)",
                fontWeight: 600,
                letterSpacing: "1.2px",
                textTransform: "uppercase",
                color: "rgba(255,255,255,0.35)",
                marginBottom: 8,
              }}
            >
              Legal Corpus
            </p>
            <div className="space-y-1.5">
              {laws.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-lg px-2 py-1.5"
                  style={{ background: "rgba(255,255,255,0.04)" }}
                >
                  <p
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "rgba(255,255,255,0.7)",
                      fontFamily: "var(--font-label)",
                      lineHeight: 1.3,
                    }}
                  >
                    {doc.short}
                  </p>
                  <p
                    style={{
                      fontSize: 10,
                      color: "rgba(255,255,255,0.4)",
                      marginTop: 1,
                    }}
                  >
                    {doc.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Footer Nav ──────────────────────────────────────────────── */}
      <div
        className="pt-4 px-2 mt-auto"
        style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}
      >
        <ul className="space-y-0.5">
          {footerItems.map((item) => (
            <li key={item.label}>
              <a
                href={item.href}
                className="nav-item flex items-center gap-3 px-3 py-2 rounded-xl"
                style={{
                  color: "rgba(255,255,255,0.5)",
                  fontSize: 13,
                  fontFamily: "var(--font-label)",
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

function StatusCard({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div
      className="rounded-lg px-2 py-1.5"
      style={{ background: "rgba(255,255,255,0.05)" }}
    >
      <p
        style={{
          fontSize: 9,
          fontFamily: "var(--font-label)",
          fontWeight: 600,
          letterSpacing: "0.5px",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.35)",
          marginBottom: 2,
        }}
      >
        {label}
      </p>
      <div className="flex items-center gap-1.5">
        {ok !== undefined && (
          <div
            className="rounded-full flex-shrink-0"
            style={{
              width: 5,
              height: 5,
              background: ok ? "#22c55e" : "#ef4444",
            }}
          />
        )}
        <p
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "rgba(255,255,255,0.75)",
            fontFamily: "var(--font-label)",
          }}
        >
          {value}
        </p>
      </div>
    </div>
  );
}
