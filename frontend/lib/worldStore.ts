import { create } from "zustand";
import type { Pin, RecordCard } from "@/lib/types";

export type WorldMode = "idle" | "results";
export type WorldProjection = "globe" | "flat";

interface WorldState {
  /** Pins currently on the world. */
  pins: Pin[];
  recordsById: Map<string, RecordCard>;
  /** idle = home page miniature world; results = fitted to the search results. */
  mode: WorldMode;
  /** Whether the stage is visible behind the page at all. */
  visible: boolean;
  /** A question was asked and the results are on their way: the world leans in while it waits. Cleared by publish(). */
  pending: boolean;
  /** Fraction (0..1) of the viewport reserved on the left/top for overlays, so camera fits avoid them. */
  inset: { left: number; top: number; bottom: number; right: number };
  projection: WorldProjection;
  /** The user can switch to a flat map; `webgl === false` means no map can render at all. */
  webgl: boolean | null;
  status: "booting" | "ready" | "error";
  publish: (pins: Pin[], recordsById: Map<string, RecordCard>, mode: WorldMode) => void;
  setVisible: (v: boolean) => void;
  setPending: (v: boolean) => void;
  setInset: (inset: Partial<WorldState["inset"]>) => void;
  setProjection: (p: WorldProjection) => void;
  setWebgl: (ok: boolean) => void;
  setStatus: (s: WorldState["status"]) => void;
}

export const useWorld = create<WorldState>((set) => ({
  pins: [],
  recordsById: new Map(),
  mode: "idle",
  visible: false,
  pending: false,
  inset: { left: 0, top: 0, bottom: 0, right: 0 },
  projection: "globe",
  webgl: null,
  status: "booting",
  publish: (pins, recordsById, mode) => set({ pins, recordsById, mode, pending: false }),
  setVisible: (visible) => set({ visible }),
  setPending: (pending) => set({ pending }),
  setInset: (inset) => set((s) => ({ inset: { ...s.inset, ...inset } })),
  setProjection: (projection) => set({ projection }),
  setWebgl: (webgl) => set({ webgl }),
  setStatus: (status) => set({ status }),
}));
