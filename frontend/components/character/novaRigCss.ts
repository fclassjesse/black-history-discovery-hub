/**
 * Nova's rig styles ship WITH the component (rendered as a hoisted <style>), not in
 * globals.css: the owner's browser has served a stale globals.css several times, which
 * froze her head and body while the inline-driven eyes kept moving. Classes use a fresh
 * `nv-` prefix so no cached `np-` rule can ever match her.
 *
 * Figure geometry used by the speech bubble, in the slot's container units:
 *   FW = min(100cqw, 100cqh * 1039 / 1200)   figure width
 *   FH = min(100cqh, 100cqw * 1200 / 1039)   figure height
 */
const FW = "min(100cqw, 100cqh * 1039 / 1200)";
const FH = "min(100cqh, 100cqw * 1200 / 1039)";

export const NOVA_RIG_CSS = `
.nv-breathe { transform-origin: 50% 100%; animation: nv-breathe 4.2s ease-in-out infinite; }
.nv-sway { animation: nv-sway 7.5s ease-in-out infinite; }
.nv-root[data-near="true"] .nv-breathe, .nv-root[data-state="attentive"] .nv-breathe { animation-duration: 2.8s; }
.nv-root[data-state="listening"] .nv-breathe { animation-duration: 2.2s; }
.nv-root[data-state="speaking"] .nv-sway { animation: nv-nod 0.95s ease-in-out infinite; }
.nv-root[data-state="thinking"] .nv-sway { animation: nv-ponder 3s ease-in-out infinite; }
.nv-root[data-state="celebrate"] .nv-breathe { animation: nv-hop 0.65s cubic-bezier(0.22, 1, 0.36, 1) 2; }
.nv-root[data-state="celebrate"] .nv-sway { animation: nv-cheer 0.65s ease-in-out 2; }
.nv-root[data-state="abstain"] .nv-sway { animation: nv-shake 0.9s ease-in-out 1; }
.nv-root img { user-select: none; -webkit-user-drag: none; }

/* speech bubble: at her top right, never wider than the left column (--nova-col-right, set by the dock) */
.nv-say {
  position: absolute; z-index: 3; pointer-events: none;
  /* just right of her face, but pulled left when the column is narrow so it never leaves the column */
  left: min(calc(50cqw + ${FW} * 0.27), calc(var(--nova-col-right, 100cqw) - 158px));
  /* top edge level with her headband, never above the slot's top 34px (the EN/FR + Menu bar sits there); longer lines grow downward */
  top: max(34px, calc(100cqh - ${FH} * 0.9 + max(0px, -1 * var(--nova-lift, 0px))));
  width: max-content;
  max-width: min(260px, calc(var(--nova-col-right, 100cqw) - min(calc(50cqw + ${FW} * 0.27), calc(var(--nova-col-right, 100cqw) - 158px)) - 28px));
  padding: 9px 14px 10px; border: 2.5px solid var(--ink); border-radius: 18px 18px 18px 6px;
  background: var(--cream); color: var(--ink); box-shadow: 0 8px 0 -3px rgba(27, 23, 21, 0.22);
  font-size: 0.9rem; line-height: 1.3; font-weight: 500;
  transform-origin: 0% 100%; animation: nv-say-in 0.42s cubic-bezier(0.34, 1.5, 0.64, 1) both;
}
.nv-say::after {
  content: ""; position: absolute; left: -2.5px; bottom: -12px; width: 18px; height: 14px;
  background: var(--cream); border-left: 2.5px solid var(--ink); border-bottom: 2.5px solid var(--ink);
  clip-path: polygon(0 0, 100% 0, 0 100%); border-bottom-left-radius: 3px;
}
.nv-say[data-leaving="true"] { animation: nv-say-out 0.28s ease-in both; }
.nv-say-caret { display: inline-block; width: 2px; height: 1em; margin-left: 2px; vertical-align: -0.15em; background: var(--ink); animation: nv-caret 0.8s steps(1) infinite; }
.nv-say-dots { display: inline-flex; gap: 4px; margin-left: 6px; vertical-align: middle; }
.nv-say-dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--ink); animation: thinkdots 1.2s ease-in-out infinite; }
.nv-say-dots i:nth-child(2) { animation-delay: 0.15s; }
.nv-say-dots i:nth-child(3) { animation-delay: 0.3s; }

@keyframes nv-breathe { 0%, 100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-2px) scale(1.006); } }
@keyframes nv-sway { 0%, 100% { transform: rotate(0deg) translateX(0); } 30% { transform: rotate(0.9deg) translateX(1px); } 70% { transform: rotate(-0.8deg) translateX(-1px); } }
@keyframes nv-nod { 0%, 100% { transform: rotate(0deg) translateY(0); } 35% { transform: rotate(-0.8deg) translateY(3px); } 70% { transform: rotate(0.5deg) translateY(1px); } }
@keyframes nv-ponder { 0%, 100% { transform: rotate(0deg); } 50% { transform: rotate(-1.6deg) translateY(-1px); } }
@keyframes nv-hop { 0%, 100% { transform: translateY(0); } 40% { transform: translateY(-12px); } }
@keyframes nv-cheer { 0%, 100% { transform: rotate(0deg); } 40% { transform: rotate(3deg); } }
@keyframes nv-shake { 0%, 100% { transform: rotate(0deg); } 25% { transform: rotate(-2.5deg); } 55% { transform: rotate(2deg); } 80% { transform: rotate(-1deg); } }
@keyframes nv-say-in { from { opacity: 0; transform: translate(-6px, 10px) scale(0.6); } to { opacity: 1; transform: none; } }
@keyframes nv-say-out { to { opacity: 0; transform: translate(-4px, 6px) scale(0.85); } }
@keyframes nv-caret { 50% { opacity: 0; } }

@media (prefers-reduced-motion: reduce) {
  .nv-breathe, .nv-sway, .nv-say, .nv-say-caret, .nv-say-dots i { animation: none !important; }
}
`;
