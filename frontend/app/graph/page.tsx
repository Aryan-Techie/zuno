"use client";

import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { NavLinks } from "@/components/NavLinks";
import { fetchKnowledgeGraph, isMissing, type KnowledgeGraphStats, type Mode } from "@/lib/api";

type View = "apple" | "perfume" | "codebase";

const VIEWS: { key: View; label: string; src: string; blurb: string }[] = [
  {
    key: "apple",
    label: "Apple knowledge",
    src: "/graphify/knowledge-apple.html",
    blurb: "What Zuno knows when it sells Apple: pricing, FAQs, competitor notes and policies, as one graph.",
  },
  {
    key: "perfume",
    label: "Dior knowledge",
    src: "/graphify/knowledge-perfume.html",
    blurb: "What Zuno knows as a beauty advisor: the fragrances, their notes and families, makeup and skincare.",
  },
  {
    key: "codebase",
    label: "ZUNO codebase",
    src: "/graphify/codebase.html",
    blurb: "This repository as Graphify sees it: the modules, the functions and how they call each other.",
  },
];

const GETGRAPHIFY_URL = process.env.NEXT_PUBLIC_GETGRAPHIFY_URL || "https://www.getgraphify.com";

type Stats = { state: "loading" } | { state: "ready"; stats: KnowledgeGraphStats } | { state: "missing" } | { state: "error" };

/**
 * Graphify views: the two product knowledge graphs Zuno answers from and the
 * graph of this codebase, each a static HTML view Graphify writes into
 * public/graphify/. The numbers above a knowledge graph come from the
 * backend's own copy of it (/api/knowledge-graph), so they describe exactly
 * what the running agent loaded.
 */
export default function GraphPage() {
  const [view, setView] = useState<View>("apple");
  const [stats, setStats] = useState<Partial<Record<Mode, Stats>>>({});
  const [frame, setFrame] = useState<Record<string, "checking" | "ok" | "missing">>({});
  const current = VIEWS.find((v) => v.key === view)!;

  // Match the embedded view to the console's appearance. Same origin, so the
  // iframe reads the same localStorage key Graphify's own toggle writes.
  useEffect(() => {
    try {
      localStorage.setItem("graphify-theme", document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    } catch {
      // private mode - Graphify falls back to its own default
    }
  }, []);

  useEffect(() => {
    if (view === "codebase" || stats[view]) return;
    const mode: Mode = view;
    setStats((s) => ({ ...s, [mode]: { state: "loading" } }));
    fetchKnowledgeGraph(mode)
      .then((g) => setStats((s) => ({ ...s, [mode]: g ? { state: "ready", stats: g.stats } : { state: "missing" } })))
      .catch((e) => setStats((s) => ({ ...s, [mode]: isMissing(e) ? { state: "missing" } : { state: "error" } })));
  }, [view, stats]);

  // A missing view file is a normal state (the lead adds them as they are
  // built), so check before pointing the iframe at a 404 page.
  useEffect(() => {
    const src = current.src;
    if (frame[src]) return;
    setFrame((f) => ({ ...f, [src]: "checking" }));
    fetch(src, { method: "HEAD" })
      .then((r) => setFrame((f) => ({ ...f, [src]: r.ok ? "ok" : "missing" })))
      .catch(() => setFrame((f) => ({ ...f, [src]: "missing" })));
  }, [current.src, frame]);

  const s = view === "codebase" ? null : stats[view];
  const frameState = frame[current.src] ?? "checking";

  return (
    <div className="app graph-page">
      <header className="top">
        <div className="brand">
          <Logo size={24} />
          <span className="wordmark">Zuno</span>
          <span className="sub">Graph</span>
        </div>
        <div className="actions">
          <NavLinks current="/graph" />
        </div>
      </header>

      <main className="stage">
        <div className="graph-wrap">
          <div className="graph-intro">
            <div>
              <h1>Graphify views</h1>
              <p>{current.blurb}</p>
            </div>
            <div className="seg" role="tablist" aria-label="Graph">
              {VIEWS.map((v) => (
                <button key={v.key} role="tab" aria-selected={v.key === view} aria-controls="graph-panel" onClick={() => setView(v.key)}>
                  {v.label}
                </button>
              ))}
            </div>
          </div>

          {view !== "codebase" && <GraphStats stats={s ?? { state: "loading" }} />}
          <p className="graph-note">
            {view === "codebase" ? (
              <>Graphify’s map of this repository. The same graph the team queries before reading source.</>
            ) : (
              <>
                <b>EXTRACTED</b> links are stated in our documents. <b>INFERRED</b> links are ones Graphify resolved on its own,
                from names and context, and they carry a confidence score.
              </>
            )}
          </p>

          <div className={`graph-frame${frameState === "ok" ? "" : " empty"}`} id="graph-panel" role="tabpanel" aria-label={current.label}>
            {frameState === "ok" && (
              <>
                <iframe key={current.src} src={current.src} title={`${current.label} graph`} loading="lazy" />
              </>
            )}
            {frameState === "missing" && (
              <div className="cat-empty">
                <b>This view hasn’t been built yet</b>
                <span>
                  Graphify writes it to <code>frontend/public{current.src}</code>; it will show here once it is there.
                </span>
              </div>
            )}
            {frameState === "checking" && <div className="cat-empty">Loading the graph…</div>}
          </div>
          {frameState === "ok" && (
            <p className="graph-note" style={{ marginTop: 10 }}>
              Drag to pan, scroll to zoom, click a node for its neighbours.{" "}
              <a href={current.src} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>
                Open it full screen
              </a>
              .
            </p>
          )}

          <a className="notion-card" href={GETGRAPHIFY_URL} target="_blank" rel="noreferrer">
            <span className="glyph" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <circle cx="6" cy="6" r="2.2" />
                <circle cx="18" cy="7" r="2.2" />
                <circle cx="12" cy="17" r="2.6" />
                <circle cx="4.5" cy="16" r="1.6" />
                <path d="M7.9 7.1 10.6 15M16.6 8.7 13.3 15M8 6.3l7.8.5M6 15.8l3.4.7" />
              </svg>
            </span>
            <span>
              <b>The CRM, as a graph, on getgraphify.com</b>
              <p>ZUNO mirrors its CRM into Notion, and getgraphify.com draws that Notion workspace as a knowledge graph.</p>
            </span>
            <span className="go">Open the workspace graph ↗</span>
          </a>
        </div>
      </main>
    </div>
  );
}

function GraphStats({ stats }: { stats: Stats }) {
  if (stats.state === "missing") {
    return (
      <p className="graph-note" style={{ marginTop: 0 }}>
        The backend has no knowledge graph for this mode yet, so there are no numbers to show.
      </p>
    );
  }
  if (stats.state === "error") {
    return (
      <p className="graph-note" style={{ marginTop: 0 }}>
        The graph’s numbers didn’t load from the backend.
      </p>
    );
  }
  const st = stats.state === "ready" ? stats.stats : null;
  const links = st?.links ?? 0;
  const extracted = st?.extracted ?? 0;
  const inferred = st?.inferred ?? 0;
  const other = Math.max(0, links - extracted - inferred);
  const pct = (n: number) => (links ? `${(n / links) * 100}%` : "0%");
  return (
    <div className="graph-stats" aria-busy={!st}>
      <div className="stat">
        <div className="k">Nodes</div>
        <div className="v">{st ? st.nodes : "—"}</div>
      </div>
      <div className="stat">
        <div className="k">Links</div>
        <div className="v">{st ? links : "—"}</div>
      </div>
      <div className="stat">
        <div className="k">Communities</div>
        <div className="v">{st ? st.communities : "—"}</div>
      </div>
      <div className="stat conf">
        <div className="k">
          <span>How the links were found</span>
        </div>
        <div className="conf-bar" role="img" aria-label={`${extracted} extracted, ${inferred} inferred${other ? `, ${other} ambiguous` : ""}`}>
          <i className="ex" style={{ width: pct(extracted) }} />
          <i className="in" style={{ width: pct(inferred) }} />
          {other > 0 && <i className="am" style={{ width: pct(other) }} />}
        </div>
        <div className="conf-legend">
          <span className="ex">{st ? extracted : "—"} extracted</span>
          <span className="in">{st ? inferred : "—"} inferred</span>
          {other > 0 && <span className="am">{other} ambiguous</span>}
        </div>
      </div>
    </div>
  );
}
