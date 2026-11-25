"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Logo } from "@/components/Logo";
import { Orb, type Phase, type Speaker } from "@/components/Orb";
import { Transcript, type FeedItem } from "@/components/Transcript";
import { LeadCard } from "@/components/LeadCard";
import { SignalsCard } from "@/components/SignalsCard";
import { DealCard, type DealRound } from "@/components/DealCard";
import { HandoffCard, type Escalation } from "@/components/HandoffCard";
import { ActivityCard, type ToolRecord } from "@/components/ActivityCard";
import { ToolPopup } from "@/components/ToolPopup";
import { Avatar3D } from "@/components/Avatar3D";
import { Brief } from "@/components/Brief";
import { FieldCursor } from "@/components/FieldCursor";
import { useFieldCursor } from "@/lib/useFieldCursor";
import { DoodleUnderline } from "@/components/Doodles";
import { ModeSwitch, Toast, type ToastMessage } from "@/components/ModeSwitch";
import { ProductSpotlight } from "@/components/ProductSpotlight";
import { NavLinks } from "@/components/NavLinks";
import { AgoraCallClient, type RtmCustomEvent } from "@/lib/agoraClient";
import {
  endCall,
  fetchCapacity,
  fetchSessionEvents,
  fetchSummary,
  isMissing,
  isMode,
  parseModeChanged,
  parseSpotlight,
  setSessionMode,
  startCall,
  type CallSummary,
  type CatalogProduct,
  type LeftBrain,
  type Mode,
  type RightBrain,
} from "@/lib/api";
import { applyMode, MODE_LABEL, readSavedMode, saveMode } from "@/lib/mode";
import { productMode } from "@/lib/catalog";
import { toolBusy } from "@/lib/vocab";

type CallStatus = "idle" | "connecting" | "active" | "ending" | "ended";

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

let seq = 0;
const nextId = (prefix: string) => `${prefix}-${++seq}`;

/** How many recently spotlighted products the strip keeps within reach. */
const RECENT_MAX = 4;

export default function Home() {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [ragScore, setRagScore] = useState<number | null>(null);
  const [leftBrain, setLeftBrain] = useState<LeftBrain | null>(null);
  const [rightBrain, setRightBrain] = useState<RightBrain | null>(null);
  const [rounds, setRounds] = useState<DealRound[]>([]);
  const [pendingApprovalId, setPendingApprovalId] = useState<string | null>(null);
  const [requestedPct, setRequestedPct] = useState<number | null>(null);
  const [approvedPct, setApprovedPct] = useState<number | null>(null);
  const [approvedBy, setApprovedBy] = useState<string | null>(null);
  const [escalation, setEscalation] = useState<Escalation | null>(null);
  // Name of the person on the channel after a warm transfer; null while
  // Zuno still has the call.
  const [repOnCall, setRepOnCall] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [leadId, setLeadId] = useState<string | null>(null);
  const [booked, setBooked] = useState(false);
  const [summary, setSummary] = useState<CallSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [micMuted, setMicMuted] = useState(false);
  const [hold, setHold] = useState(false);
  const [agentState, setAgentState] = useState<string>("idle");
  const [youTalking, setYouTalking] = useState(false);
  const [tab, setTab] = useState<"brief" | "transcript">("brief");
  const [dark, setDark] = useState(false);
  // Opt-in only - the 2D orb is the proven default. See components/Avatar3D.tsx.
  const [use3D, setUse3D] = useState(false);
  // Live-calls badge - proof this isn't a single-call toy, sourced from the
  // same endpoint the /dashboard page polls. Failures just hide the badge.
  const [callsLiveNow, setCallsLiveNow] = useState<number | null>(null);
  // Which shop Zuno works in. Picked before the call, switchable during it
  // from here or by the caller's voice; the backend's answer always wins.
  const [mode, setMode] = useState<Mode>("apple");
  const [modeBusy, setModeBusy] = useState(false);
  const [toast, setToast] = useState<ToastMessage | null>(null);
  // The product on screen, the few before it, and whether the operator has
  // tucked the card away until the next product is named.
  const [spotlight, setSpotlight] = useState<CatalogProduct | null>(null);
  const [recent, setRecent] = useState<CatalogProduct[]>([]);
  const [spotHidden, setSpotHidden] = useState(false);

  const sessionIdRef = useRef<string | null>(null);
  const leadCardWrapRef = useRef<HTMLDivElement | null>(null);
  const clientRef = useRef<AgoraCallClient | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const endedAtRef = useRef<number | null>(null);
  // tool_call_started and tool_call_finished carry no shared id, only the
  // tool name, so in-flight calls are matched first-in first-out per name.
  const inFlightRef = useRef<Map<string, { id: string; startedMs: number }[]>>(new Map());
  const modeRef = useRef<Mode>("apple");
  // A console switch toasts on the click; its echo on the event stream
  // (by: "console") must not toast a second time.
  const consoleSwitchRef = useRef<Mode | null>(null);

  const phase: Phase = status === "idle" ? "idle" : status === "ended" ? "ended" : "live";
  const fieldCursor = useFieldCursor(leftBrain, status === "active", leadCardWrapRef);

  /* ---------------- theme and mode ---------------- */
  useEffect(() => {
    setDark(document.documentElement.dataset.theme === "dark");
    const saved = readSavedMode();
    modeRef.current = saved;
    setMode(saved);
    applyMode(saved);
  }, []);

  const showToast = useCallback((text: string, detail?: string) => {
    setToast({ id: Date.now(), text, detail });
  }, []);

  /** Applies a mode the backend has confirmed (or, before a call, the pick). */
  const adoptMode = useCallback((next: Mode) => {
    modeRef.current = next;
    setMode(next);
    applyMode(next);
    saveMode(next);
  }, []);

  /** A spotlighted product from the other catalog has no place on screen. */
  const dropOtherModeSpotlight = useCallback((next: Mode) => {
    setSpotlight((cur) => (cur && productMode(cur) !== next ? null : cur));
    setRecent((prev) => prev.filter((p) => productMode(p) === next));
  }, []);

  const showProduct = useCallback((product: CatalogProduct) => {
    setSpotlight(product);
    setSpotHidden(false);
    setRecent((prev) => [product, ...prev.filter((p) => p.id !== product.id)].slice(0, RECENT_MAX));
  }, []);
  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("zuno-theme", next ? "dark" : "light");
    } catch {
      // private mode - the choice just does not persist
    }
  };

  /* ---------------- live-calls badge ---------------- */
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const snapshot = await fetchCapacity();
        if (!cancelled) setCallsLiveNow(snapshot.calls_live_now);
      } catch {
        if (!cancelled) setCallsLiveNow(null);
      }
    };
    void poll();
    const id = setInterval(poll, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  /* ---------------- clock ---------------- */
  useEffect(() => {
    if (status !== "active" && status !== "connecting") return;
    const id = setInterval(() => {
      setElapsed(startedAtRef.current === null ? 0 : Math.floor((Date.now() - startedAtRef.current) / 1000));
    }, 500);
    return () => clearInterval(id);
  }, [status]);

  /* ---------------- who is talking (for the orb and caption) ---------------- */
  useEffect(() => {
    if (status !== "active") {
      setYouTalking(false);
      return;
    }
    const id = setInterval(() => {
      const levels = clientRef.current?.getLevels();
      setYouTalking(!!levels && !micMuted && !hold && levels.local > 0.08);
    }, 120);
    return () => clearInterval(id);
  }, [status, micMuted, hold]);

  const toolInFlight = useMemo(() => tools.find((t) => t.ms === null) ?? null, [tools]);

  const speaker: Speaker =
    phase !== "live"
      ? "none"
      : agentState === "speaking"
        ? "zuno"
        : toolInFlight || agentState === "thinking"
          ? "think"
          : youTalking
            ? "you"
            : "none";

  const getLevel = useCallback(() => {
    const levels = clientRef.current?.getLevels();
    if (!levels) return 0;
    return speaker === "zuno" ? levels.remote : speaker === "you" ? levels.local : 0;
  }, [speaker]);

  /* ---------------- feed helpers ---------------- */
  const pushNote = useCallback((tone: "info" | "good" | "warn" | "bad", text: string) => {
    setFeed((prev) => [...prev, { kind: "note", id: nextId("note"), tone, text }]);
  }, []);

  // One side of one exchange. The backend publishes these from the LLM
  // route as the words flow (routes/llm.py::_publish_turn) - the user's
  // turn once, Zuno's repeatedly as her reply grows, then once more marked
  // final. Upsert at the stable id so a growing reply updates in place.
  const upsertTurn = useCallback((id: string, role: "user" | "assistant", text: string, final: boolean) => {
    setFeed((prev) => {
      const item: FeedItem = { kind: "turn", id, role, text, final };
      const i = prev.findIndex((e) => e.id === id);
      if (i >= 0) {
        const next = [...prev];
        next[i] = item;
        return next;
      }
      return [...prev, item];
    });
  }, []);

  const handleCustomEvent = useCallback(
    (event: RtmCustomEvent) => {
      const p = event.payload;
      const eventMs = event.ts ? Date.parse(event.ts) : Date.now();
      switch (event.type) {
        case "transcript_turn": {
          const role = p.role === "user" ? "user" : "assistant";
          const text = String(p.text ?? "");
          if (!text) break;
          upsertTurn(`turn-${role}-${String(p.turn_id ?? eventMs)}`, role, text, Boolean(p.final));
          break;
        }
        case "tool_call_started": {
          const tool = String(p.tool_name ?? "tool");
          const id = nextId("tool");
          const list = inFlightRef.current.get(tool) ?? [];
          list.push({ id, startedMs: eventMs });
          inFlightRef.current.set(tool, list);
          const at = startedAtRef.current ? Math.max(0, (eventMs - startedAtRef.current) / 1000) : 0;
          const args = p.args && typeof p.args === "object" ? (p.args as Record<string, unknown>) : undefined;
          setTools((prev) => [...prev, { id, tool, at, ms: null, args }]);
          setFeed((prev) => [...prev, { kind: "tool", id, tool, ms: null }]);
          break;
        }
        case "tool_call_finished": {
          const tool = String(p.tool_name ?? "tool");
          const list = inFlightRef.current.get(tool) ?? [];
          const started = list.shift();
          if (!started) break;
          const ms = Math.max(0, Math.round(eventMs - started.startedMs));
          const resultSummary = p.result_summary ? String(p.result_summary) : undefined;
          const failed = String(p.result_summary ?? "").includes('"error"');
          if (p.rag_score != null) setRagScore(Number(p.rag_score));
          setTools((prev) => prev.map((t) => (t.id === started.id ? { ...t, ms, resultSummary } : t)));
          setFeed((prev) =>
            prev.map((e) =>
              e.kind === "tool" && e.id === started.id
                ? { ...e, ms, tone: failed ? "bad" : tool === "calendar_book_meeting" ? "good" : undefined }
                : e
            )
          );
          break;
        }
        case "qualification_updated":
          setLeftBrain(p as LeftBrain);
          if (p.lead_id) setLeadId(String(p.lead_id));
          break;
        case "deal_offer_made": {
          const round = p as unknown as DealRound;
          // Keyed on the round number rather than appended: a poll that
          // overlaps a retry would otherwise print the same round twice.
          setRounds((prev) => [...prev.filter((r) => r.round !== round.round), round].sort((a, b) => a.round - b.round));
          break;
        }
        case "deal_approval_requested":
          setPendingApprovalId(String(p.escalation_id ?? ""));
          setRequestedPct(p.requested_pct == null ? null : Number(p.requested_pct));
          pushNote("warn", "The deal desk is at its ceiling. A signature is needed; the call is still live.");
          break;
        case "deal_approval_granted":
          setPendingApprovalId(null);
          setApprovedPct(Number(p.approved_pct));
          setApprovedBy(String(p.approved_by ?? "a manager"));
          pushNote("good", `${p.approved_pct}% signed off by ${p.approved_by ?? "a manager"}`);
          break;
        case "escalation_triggered": {
          const esc: Escalation = {
            trigger_source: String(p.trigger_source ?? "llm"),
            reason: p.reason ? String(p.reason) : null,
            escalation_id: p.escalation_id ? String(p.escalation_id) : null,
            inbox_position: p.inbox_position == null ? null : Number(p.inbox_position),
            handoff_url: p.handoff_url ? String(p.handoff_url) : null,
            rep_name: p.rep_name ? String(p.rep_name) : null,
            brief: (p.brief as Escalation["brief"]) ?? null,
          };
          setEscalation(esc);
          pushNote("bad", esc.reason ? `Handed to a person: ${esc.reason}` : "Handed to a person with a written brief");
          break;
        }
        case "call_outcome_set": {
          const value = String(p.outcome ?? "");
          setOutcome(value);
          if (value === "meeting_booked") {
            setBooked(true);
            pushNote("good", "Meeting booked. The invite is on its way.");
          }
          break;
        }
        case "rep_joined": {
          const name = String(p.rep_name ?? "A colleague");
          setRepOnCall(name);
          pushNote("good", `${name} is on the call. Zuno is handing over.`);
          break;
        }
        case "zuno_left":
          setAgentState("left");
          pushNote("info", "Zuno has left the call.");
          break;
        case "objection_logged":
          // Reflected in right_brain on the next poll; nothing to print.
          break;
        case "mode_changed": {
          const change = parseModeChanged(p);
          if (!change) break;
          const echo = change.by === "console" && consoleSwitchRef.current === change.mode;
          if (echo) consoleSwitchRef.current = null;
          if (change.mode !== modeRef.current) {
            adoptMode(change.mode);
            dropOtherModeSpotlight(change.mode);
          }
          if (!echo) {
            showToast(
              change.by === "voice" ? `The caller switched to ${MODE_LABEL[change.mode]}` : `Switched to ${MODE_LABEL[change.mode]}`,
              change.by === "voice" ? "by voice" : "from a console"
            );
          }
          pushNote("info", `${MODE_LABEL[change.mode]} mode, ${change.by === "voice" ? "asked for by the caller" : "set from the console"}`);
          break;
        }
        case "product_spotlight": {
          const spot = parseSpotlight(p);
          if (spot) showProduct(spot.product);
          break;
        }
      }
    },
    [pushNote, upsertTurn, adoptMode, dropOtherModeSpotlight, showToast, showProduct]
  );

  /* ---------------- poll the backend for envelopes + brains ---------------- */
  useEffect(() => {
    if (status !== "active") return;
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;

    let cancelled = false;
    let cursor = 0;
    const poll = async () => {
      try {
        const data = await fetchSessionEvents(sessionId, cursor);
        if (cancelled) return;
        cursor = data.cursor;
        for (const envelope of data.events) {
          handleCustomEvent({ type: envelope.type, payload: envelope.payload, ts: envelope.ts, session_id: sessionId });
        }
        if (data.left_brain) setLeftBrain(data.left_brain);
        if (data.right_brain) setRightBrain(data.right_brain);
        // The event stream carries every switch, but the snapshot is the
        // truth: if an event was missed, follow the session quietly.
        if (isMode(data.mode) && data.mode !== modeRef.current && !consoleSwitchRef.current) {
          adoptMode(data.mode);
          dropOtherModeSpotlight(data.mode);
        }
      } catch {
        // transient - the next tick retries
      }
    };
    void poll();
    const timer = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [status, handleCustomEvent, adoptMode, dropOtherModeSpotlight]);

  /* ---------------- the brief, once the backend has written it ---------------- */
  useEffect(() => {
    if (status !== "ended" || summary) return;
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;
    let cancelled = false;
    let tries = 0;
    const tick = async () => {
      tries += 1;
      try {
        const s = await fetchSummary(sessionId);
        if (cancelled) return;
        if (s) {
          setSummary(s);
          return;
        }
      } catch {
        // keep trying
      }
      if (!cancelled && tries < 20) setTimeout(tick, 1500);
    };
    void tick();
    return () => {
      cancelled = true;
    };
  }, [status, summary]);

  /* ---------------- lifecycle ---------------- */
  const handleStart = useCallback(async () => {
    setError(null);
    setStatus("connecting");
    setFeed([]);
    setTools([]);
    setLeftBrain(null);
    setRightBrain(null);
    setRounds([]);
    setPendingApprovalId(null);
    setRequestedPct(null);
    setApprovedPct(null);
    setApprovedBy(null);
    setEscalation(null);
    setRepOnCall(null);
    setOutcome(null);
    setLeadId(null);
    setBooked(false);
    setSummary(null);
    setMicMuted(false);
    setHold(false);
    setAgentState("idle");
    setTab("brief");
    setElapsed(0);
    setSpotlight(null);
    setRecent([]);
    setSpotHidden(false);
    inFlightRef.current = new Map();
    consoleSwitchRef.current = null;
    try {
      // An RTM client left connected from a prior attempt logs in twice
      // under the same uid - Agora's own warning calls this a "mutual kick"
      // risk, confirmed live. Always close any stale client first.
      if (clientRef.current) {
        await clientRef.current.leave().catch(() => {});
        clientRef.current = null;
      }
      const session = await startCall(modeRef.current);
      sessionIdRef.current = session.session_id;
      if (isMode(session.mode) && session.mode !== modeRef.current) adoptMode(session.mode);
      startedAtRef.current = Date.now();
      endedAtRef.current = null;

      const client = new AgoraCallClient();
      clientRef.current = client;
      await client.join(session, {
        // Transcript comes over the polled event stream (transcript_turn),
        // not the toolkit's TRANSCRIPT_UPDATED - see handleCustomEvent.
        onCustomEvent: handleCustomEvent,
        onAgentStateChanged: (state) => setAgentState(state),
        onError: (e) => {
          const text = e instanceof Error ? e.message : String(e);
          setError(text);
          pushNote("bad", text);
        },
      });
      setStatus("active");
    } catch (e) {
      const text = e instanceof Error ? e.message : String(e);
      setError(text);
      setStatus("idle");
    }
  }, [handleCustomEvent, pushNote, adoptMode]);

  const handleEnd = useCallback(async () => {
    setStatus("ending");
    endedAtRef.current = Date.now();
    try {
      await clientRef.current?.leave();
      clientRef.current = null;
      if (sessionIdRef.current) {
        const result = await endCall(sessionIdRef.current);
        setOutcome(result.outcome);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      clientRef.current = null;
      setStatus("ended");
      setTab("brief");
    }
  }, []);

  const toggleMute = useCallback(async () => {
    const next = !micMuted;
    try {
      await clientRef.current?.setMicMuted(next);
      setMicMuted(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [micMuted]);

  const toggleHold = useCallback(async () => {
    const next = !hold;
    try {
      await clientRef.current?.setHold(next);
      setHold(next);
      // Coming off hold restores the mic; going on hold implies mute.
      if (next) setMicMuted(true);
      else {
        await clientRef.current?.setMicMuted(false);
        setMicMuted(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [hold]);

  /* ---------------- mode ---------------- */
  // Before a call the pick is local; during one it goes through the API and
  // the theme moves at once, rolling back if the backend says no.
  const changeMode = useCallback(
    async (next: Mode) => {
      const sessionId = sessionIdRef.current;
      const live = status === "active" && sessionId;
      if (!live) {
        adoptMode(next);
        return;
      }
      const previous = modeRef.current;
      setModeBusy(true);
      consoleSwitchRef.current = next;
      adoptMode(next);
      dropOtherModeSpotlight(next);
      try {
        await setSessionMode(sessionId, next);
        showToast(`Switched to ${MODE_LABEL[next]}`, "Zuno changes on its next turn");
      } catch (e) {
        consoleSwitchRef.current = null;
        adoptMode(previous);
        showToast(
          isMissing(e) ? "This backend can’t switch modes mid-call yet" : "The switch didn’t go through",
          `Still ${MODE_LABEL[previous]}`
        );
      } finally {
        setModeBusy(false);
      }
    },
    [status, adoptMode, dropOtherModeSpotlight, showToast]
  );

  /* ---------------- captions ---------------- */
  const durationSeconds =
    startedAtRef.current === null
      ? 0
      : Math.floor(((endedAtRef.current ?? Date.now()) - startedAtRef.current) / 1000);

  let caption: React.ReactNode;
  if (status === "idle") caption = error ? <span className="tone-bad">{error}</span> : "Ready when you are";
  else if (status === "connecting") caption = <em>Connecting…</em>;
  else if (status === "ending") caption = <em>Wrapping up…</em>;
  else if (status === "ended")
    caption = (
      <>
        Call ended · {fmt(durationSeconds)}
        <br />
        <em>{summary ? "Brief sent, CRM note written." : "Writing the brief for the rep…"}</em>
      </>
    );
  else if (hold) caption = <>On hold <em>· Zuno can’t hear you and you can’t hear it</em></>;
  else if (repOnCall && agentState === "left") caption = <>{repOnCall} has the call <em>· Zuno has left</em></>;
  else if (repOnCall) caption = <>{repOnCall} is on the line <em>· Zuno is handing over</em></>;
  else if (toolInFlight) caption = `${toolBusy(toolInFlight.tool)}…`;
  else if (agentState === "speaking") caption = "Zuno is speaking";
  else if (agentState === "thinking") caption = <em>Thinking</em>;
  else if (micMuted) caption = <em>Muted</em>;
  else caption = youTalking ? "Listening" : <em>Listening</em>;

  const turnCount = feed.filter((e) => e.kind === "turn").length;
  const statusLabel =
    status === "idle" ? "Standby" : status === "connecting" ? "Connecting" : status === "ended" ? "Ended" : "Live";

  const live = status === "connecting" || status === "active" || status === "ending";
  const spotOn = live && spotlight !== null && !spotHidden;

  return (
    <div className="app">
      <header className="top">
        <div className="top-left">
          <div className="brand">
            <Logo size={24} />
            <span className="wordmark">Zuno</span>
            <span className="sub">Console</span>
          </div>
          <div className={`status ${phase}${status === "connecting" ? " connecting" : ""}`} role="status">
            <span className="dot" />
            <span>{statusLabel}</span>
            {status !== "idle" && <span className="time">{fmt(status === "ended" ? durationSeconds : elapsed)}</span>}
          </div>
          {callsLiveNow != null && callsLiveNow > 0 && (
            <span className="live-count" title="Calls live across the whole backend right now">
              {callsLiveNow} live
            </span>
          )}
        </div>
        <div className="actions">
          {live && <ModeSwitch mode={mode} onChange={changeMode} busy={modeBusy} disabled={status !== "active"} />}
          <NavLinks current="/" />
          <button className="ghost" onClick={() => setUse3D((v) => !v)} aria-pressed={use3D} title="Show Zuno as an orb or a face">
            {use3D ? "Orb" : "Face"}
          </button>
          <button className="ghost icon" onClick={toggleTheme} title={dark ? "Light appearance" : "Dark appearance"} aria-label="Toggle dark mode">
            {dark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <Toast toast={toast} />

      <main className="stage" data-phase={phase} data-spot={spotOn ? "on" : undefined}>
        <section className="left">
          <div className={`voice${hold ? " hold" : ""}`}>
            {use3D ? (
              <Avatar3D
                phase={phase}
                speaker={speaker}
                hold={hold}
                getLevel={getLevel}
                getTrack={() => clientRef.current?.getRemoteMediaStreamTrack() ?? null}
              />
            ) : (
              <Orb phase={phase} speaker={speaker} hold={hold} getLevel={getLevel} />
            )}
            <ToolPopup tools={tools} />
            {mode === "perfume" && <p className="mode-fineprint">Demo. Not affiliated with Dior.</p>}
            <div className="caption">
              {caption}
              {status === "idle" && !error && <DoodleUnderline className="doodle" style={{ display: "block", margin: "4px auto 0" }} />}
            </div>
            <div className="controls">
              {(status === "idle" || status === "ended") && (
                <>
                  {status === "idle" && <ModeSwitch mode={mode} onChange={changeMode} size="large" />}
                  <button className="primary" onClick={handleStart}>
                    {status === "ended" ? "New call" : "Start call"}
                  </button>
                </>
              )}
              {live && (
                <span className="call-buttons">
                  <button
                    className={`round${micMuted ? " on" : ""}`}
                    onClick={toggleMute}
                    disabled={status !== "active" || hold}
                    title={micMuted ? "Unmute" : "Mute"}
                    aria-pressed={micMuted}
                  >
                    <MicIcon muted={micMuted} />
                  </button>
                  <button
                    className={`round${hold ? " on" : ""}`}
                    onClick={toggleHold}
                    disabled={status !== "active"}
                    title={hold ? "Resume" : "Hold"}
                    aria-pressed={hold}
                  >
                    {hold ? <PlayIcon /> : <PauseIcon />}
                  </button>
                  <button className="round end" onClick={handleEnd} disabled={status !== "active"} title="End call">
                    <EndIcon />
                  </button>
                </span>
              )}
            </div>
          </div>

          {live && spotlight && !spotHidden && (
            <ProductSpotlight product={spotlight} recent={recent} onPick={showProduct} onClose={() => setSpotHidden(true)} />
          )}
          {live && spotlight && spotHidden && (
            <button className="spot-restore" onClick={() => setSpotHidden(false)}>
              Show {spotlight.name} again
            </button>
          )}

          {status === "ended" && (
            <div className="tabs" role="tablist">
              <button role="tab" aria-selected={tab === "brief"} className={tab === "brief" ? "on" : ""} onClick={() => setTab("brief")}>
                Brief
              </button>
              <button
                role="tab"
                aria-selected={tab === "transcript"}
                className={tab === "transcript" ? "on" : ""}
                onClick={() => setTab("transcript")}
              >
                Transcript
              </button>
            </div>
          )}

          {status !== "idle" && (
            <Transcript
              items={feed}
              hidden={status === "ended" && tab !== "transcript"}
              emptyText={status === "connecting" ? "Joining the channel…" : "Say hello. Every turn and every tool call prints here as it happens."}
            />
          )}

          {status === "ended" && tab === "brief" && (
            <Brief
              summary={summary}
              outcome={outcome}
              durationSeconds={durationSeconds}
              turnCount={turnCount}
              tools={tools.map((t) => t.tool)}
              lead={leftBrain}
              brain={rightBrain}
              rounds={rounds}
              approvedPct={approvedPct}
              approvedBy={approvedBy}
              booked={booked}
              escalated={escalation !== null}
              leadId={leadId}
            />
          )}
        </section>

        <aside className="sheet">
          <div ref={leadCardWrapRef} style={{ position: "relative" }}>
            <LeadCard lead={leftBrain} booked={booked} escalated={escalation !== null} sessionId={sessionIdRef.current} />
            <FieldCursor {...fieldCursor} />
          </div>
          <SignalsCard brain={rightBrain} />
          <DealCard
            rounds={rounds}
            pendingApprovalId={pendingApprovalId}
            requestedPct={requestedPct}
            approvedPct={approvedPct}
            approvedBy={approvedBy}
          />
          <HandoffCard brain={rightBrain} escalation={escalation} repOnCall={repOnCall} ragScore={ragScore} />
          <ActivityCard tools={tools} booked={booked} />
        </aside>
      </main>
    </div>
  );
}

const icon = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function MicIcon({ muted }: { muted: boolean }) {
  return (
    <svg viewBox="0 0 24 24" {...icon}>
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
      {muted && <path d="M4 4l16 16" />}
    </svg>
  );
}
function PauseIcon() {
  return (
    <svg viewBox="0 0 24 24" {...icon}>
      <path d="M8 5v14M16 5v14" strokeWidth="2.4" />
    </svg>
  );
}
function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M7 4.5v15l12-7.5z" />
    </svg>
  );
}
function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" {...icon}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" {...icon}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </svg>
  );
}
function EndIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M3.6 13.9c-.9-.9-.9-2.2-.1-3.1C6 8.3 9 7 12 7s6 1.3 8.5 3.8c.8.9.8 2.2-.1 3.1l-1.6 1.6c-.7.7-1.8.8-2.6.2l-2-1.5c-.6-.5-.9-1.2-.8-1.9l.2-1.2c-1.1-.4-2.3-.4-3.4 0l.2 1.2c.1.7-.2 1.4-.8 1.9l-2 1.5c-.8.6-1.9.5-2.6-.2z" />
    </svg>
  );
}
