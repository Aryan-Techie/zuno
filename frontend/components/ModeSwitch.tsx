"use client";

import { useEffect, useState } from "react";
import { MODES, type Mode } from "@/lib/api";
import { MODE_BLURB, MODE_LABEL } from "@/lib/mode";

/**
 * Apple or Dior beauty. A two-way segmented control with a sliding thumb:
 * large under the orb before a call (with a line on what Zuno does in each
 * mode), compact in the top bar once the call is live, where a switch goes
 * through the API and lands on Zuno's next turn.
 */
export function ModeSwitch({
  mode,
  onChange,
  size = "compact",
  disabled = false,
  busy = false,
}: {
  mode: Mode;
  onChange: (mode: Mode) => void;
  size?: "large" | "compact";
  disabled?: boolean;
  /** A switch is in flight; the control holds still until it lands. */
  busy?: boolean;
}) {
  const index = MODES.indexOf(mode);
  return (
    <div className={`mode-switch ${size}${busy ? " busy" : ""}`}>
      <div className="mode-track" role="radiogroup" aria-label="Which shop Zuno works in">
        <span className="mode-thumb" style={{ transform: `translateX(${index * 100}%)` }} aria-hidden="true" />
        {MODES.map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={m === mode}
            className={m === mode ? "on" : ""}
            disabled={disabled || busy}
            onClick={() => m !== mode && onChange(m)}
          >
            {m === "apple" ? <AppleMark /> : <BottleMark />}
            {MODE_LABEL[m]}
          </button>
        ))}
      </div>
      {size === "large" && <p className="mode-blurb">{MODE_BLURB[mode]}</p>}
    </div>
  );
}

function AppleMark() {
  // A plain apple silhouette, drawn rather than the trademarked logo.
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 4.6c.9-1.3 2.6-1.6 3.7-.9 1.5.9 1.9 3 1.2 5.2-.7 2.2-2 4-3.4 4-.6 0-.9-.3-1.5-.3s-.9.3-1.5.3c-1.4 0-2.7-1.8-3.4-4-.7-2.2-.3-4.3 1.2-5.2 1.1-.7 2.8-.4 3.7.9z" />
      <path d="M8 4.4c0-1.3.6-2.3 1.8-2.8" />
    </svg>
  );
}

function BottleMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="6.2" y="1.6" width="3.6" height="2.6" rx=".5" />
      <path d="M7 4.2v1.3M9 4.2v1.3" />
      <rect x="3.6" y="5.5" width="8.8" height="8.9" rx="1.6" />
    </svg>
  );
}

export interface ToastMessage {
  id: number;
  text: string;
  detail?: string;
}

/**
 * A short, quiet notice under the top bar - used for "who switched the
 * mode". Lives for a few seconds, then fades; a new message replaces the
 * old one rather than stacking.
 */
export function Toast({ toast }: { toast: ToastMessage | null }) {
  const [shown, setShown] = useState<ToastMessage | null>(null);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (!toast) return;
    setShown(toast);
    setLeaving(false);
    const fade = setTimeout(() => setLeaving(true), 3400);
    const gone = setTimeout(() => setShown(null), 3900);
    return () => {
      clearTimeout(fade);
      clearTimeout(gone);
    };
  }, [toast]);

  return (
    <div className="toast-wrap" role="status" aria-live="polite">
      {shown && (
        <div className={`toast${leaving ? " leaving" : ""}`} key={shown.id}>
          <span className="toast-dot" aria-hidden="true" />
          <span className="toast-text">{shown.text}</span>
          {shown.detail && <span className="toast-detail">{shown.detail}</span>}
        </div>
      )}
    </div>
  );
}
