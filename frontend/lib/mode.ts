import { isMode, type Mode } from "@/lib/api";

/**
 * The console's mode lives on <html data-mode>, so the whole page re-themes
 * from tokens in app/modes.css rather than from props threaded through every
 * component. The saved pick is applied before first paint by the script in
 * app/layout.tsx; this module only handles changes after that.
 */

const STORAGE_KEY = "zuno-mode";
/** Long enough for the colour cross-fade in modes.css to finish. */
const SHIFT_MS = 900;

export const MODE_LABEL: Record<Mode, string> = {
  apple: "Apple",
  perfume: "Dior beauty",
};

/** What Zuno is doing in each mode, in one line for the picker. */
export const MODE_BLURB: Record<Mode, string> = {
  apple: "Sells Apple devices to teams and individuals",
  perfume: "Advises on fragrance, makeup and skincare",
};

export function readSavedMode(): Mode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isMode(saved)) return saved;
  } catch {
    // private mode - fall through to the default
  }
  return "apple";
}

export function saveMode(mode: Mode): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // private mode - the choice just does not persist
  }
}

let shiftTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Sets the page's theme to a mode. The `mode-shift` class turns on colour
 * transitions for every element just for the length of the switch, so the
 * change reads as one cross-fade without leaving a transition on every
 * hover and state change for the rest of the session.
 */
export function applyMode(mode: Mode): void {
  const root = document.documentElement;
  if (root.dataset.mode === mode) return;
  root.classList.add("mode-shift");
  root.dataset.mode = mode;
  if (shiftTimer) clearTimeout(shiftTimer);
  shiftTimer = setTimeout(() => root.classList.remove("mode-shift"), SHIFT_MS);
}

/** For pages that do not take a mode (they keep the Apple look). */
export function clearMode(): void {
  delete document.documentElement.dataset.mode;
}
