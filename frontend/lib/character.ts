/**
 * Character integration contract.
 *
 * The animated guide character is designed separately. This module is the
 * seam between the website and that character: the site publishes *states*
 * (what the guide is doing) and *gaze targets* (where the user's cursor is),
 * and a character rig subscribes to them. Until a rig is registered, the
 * `CharacterSlot` component renders a neutral paper "understudy".
 *
 * From any script (e.g. the designer's bundle):
 *   window.__BHDH_CHARACTER__.registerRig({
 *     mount(el) { ... render into el; return () => cleanup },
 *     setState(state, meta) { ... },
 *     lookAt(nx, ny) { ... }   // normalised -1..1 relative to the slot centre
 *   });
 */
export type CharacterState = "idle" | "listening" | "thinking" | "speaking" | "abstain" | "pointing" | "celebrate";

export interface CharacterMeta {
  text?: string;
  citations?: number;
  institution?: string | null;
}

export interface CharacterRig {
  /** Render into the slot element. Return a cleanup function. */
  mount: (el: HTMLElement, context: { size: "hero" | "guide" | "mini" }) => void | (() => void);
  setState?: (state: CharacterState, meta?: CharacterMeta) => void;
  lookAt?: (nx: number, ny: number) => void;
}

type StateListener = (state: CharacterState, meta?: CharacterMeta) => void;
type RigListener = (rig: CharacterRig | null) => void;

class CharacterBus {
  private state: CharacterState = "idle";
  private meta: CharacterMeta | undefined;
  private rig: CharacterRig | null = null;
  private stateListeners = new Set<StateListener>();
  private rigListeners = new Set<RigListener>();
  private idleTimer: ReturnType<typeof setTimeout> | null = null;

  get current() { return { state: this.state, meta: this.meta }; }
  get currentRig() { return this.rig; }

  /** Set a state. Transient states (speaking, abstain, celebrate, pointing) fall back to idle after `holdMs`. */
  set(state: CharacterState, meta?: CharacterMeta, holdMs?: number) {
    this.state = state;
    this.meta = meta;
    this.stateListeners.forEach((fn) => fn(state, meta));
    this.rig?.setState?.(state, meta);
    if (this.idleTimer) { clearTimeout(this.idleTimer); this.idleTimer = null; }
    const hold = holdMs ?? (state === "speaking" ? 9000 : state === "abstain" ? 7000 : state === "celebrate" || state === "pointing" ? 3000 : undefined);
    if (hold) this.idleTimer = setTimeout(() => this.set("idle"), hold);
  }

  subscribe(fn: StateListener) {
    this.stateListeners.add(fn);
    fn(this.state, this.meta);
    return () => { this.stateListeners.delete(fn); };
  }

  onRig(fn: RigListener) {
    this.rigListeners.add(fn);
    fn(this.rig);
    return () => { this.rigListeners.delete(fn); };
  }

  registerRig(rig: CharacterRig) {
    this.rig = rig;
    rig.setState?.(this.state, this.meta);
    this.rigListeners.forEach((fn) => fn(rig));
    return () => { if (this.rig === rig) { this.rig = null; this.rigListeners.forEach((fn) => fn(null)); } };
  }

  lookAt(nx: number, ny: number) {
    this.rig?.lookAt?.(nx, ny);
  }
}

declare global {
  interface Window { __BHDH_CHARACTER__?: CharacterBus }
}

function getBus(): CharacterBus {
  if (typeof window === "undefined") return new CharacterBus();
  if (!window.__BHDH_CHARACTER__) window.__BHDH_CHARACTER__ = new CharacterBus();
  return window.__BHDH_CHARACTER__;
}

export const character = {
  set: (state: CharacterState, meta?: CharacterMeta, holdMs?: number) => getBus().set(state, meta, holdMs),
  subscribe: (fn: StateListener) => getBus().subscribe(fn),
  onRig: (fn: RigListener) => getBus().onRig(fn),
  registerRig: (rig: CharacterRig) => getBus().registerRig(rig),
  lookAt: (nx: number, ny: number) => getBus().lookAt(nx, ny),
  get current() { return getBus().current; },
};
