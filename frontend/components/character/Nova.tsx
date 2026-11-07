"use client";

import type { CharacterMeta, CharacterState } from "@/lib/character";

/**
 * Nova — the guide. A Black girl drawn in the Paper Atlas cut-out style:
 * flat colour, thick ink outlines, halftone shading. A young archivist:
 * round glasses, a pencil behind her ear, polka-dot pinafore with a pocket
 * full of notes, a satchel, a notebook in her hand, striped socks and laced
 * boots. Everything is driven by `state` (what she is doing) and `gaze`
 * (where the cursor is), so the same rig serves the stage, the results
 * drawer and the mobile sheet.
 */
export const NOVA_NAME = "Nova";

export type NovaFraming = "full" | "bust";
/** Bust = head, shoulders and arms only, cropped just under the pinafore straps, for small docks. */
const VIEWBOX: Record<NovaFraming, string> = { full: "0 0 300 400", bust: "0 0 300 258" };

interface Pose { lUpper: number; lLower: number; rUpper: number; rLower: number }
/** Arm angles in degrees. 0 = hanging straight down; the right arm raises outward with negative values, the left with positive. */
const POSES: Record<CharacterState, Pose> = {
  idle: { lUpper: 6, lLower: -10, rUpper: -6, rLower: 10 },
  listening: { lUpper: 150, lLower: 72, rUpper: -8, rLower: 14 },
  thinking: { lUpper: 8, lLower: -8, rUpper: 36, rLower: 148 },
  speaking: { lUpper: 10, lLower: -14, rUpper: -34, rLower: -62 },
  abstain: { lUpper: 62, lLower: 112, rUpper: -62, rLower: -112 },
  pointing: { lUpper: 8, lLower: -10, rUpper: -118, rLower: -4 },
  celebrate: { lUpper: 14, lLower: -20, rUpper: -152, rLower: -24 },
};

const SKIN = "#7a4a2e";
const SKIN_DEEP = "#5c3620";
const HAIR = "#1b1715";
const HAIR_LIGHT = "#3b3430";
const STROKE = { stroke: "var(--ink)", strokeWidth: 4, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

/** An open hand with a thumb; `pointing` extends the index finger. Drawn at the end of the lower arm. */
function Hand({ pointing, flip }: { pointing?: boolean; flip?: boolean }) {
  return (
    <g transform={`translate(0 56) ${flip ? "scale(-1 1)" : ""}`}>
      <path d="M-14 -2 Q-16 22 -3 27 Q13 31 16 12 Q17 -3 7 -6 L-9 -6 Q-14 -6 -14 -2 Z" fill={SKIN} {...STROKE} />
      <ellipse cx="-13" cy="8" rx="6" ry="9" fill={SKIN} {...STROKE} strokeWidth="3.5" />
      <path d="M-3 2 V20 M5 2 V20" fill="none" stroke={SKIN_DEEP} strokeWidth="2" strokeLinecap="round" />
      {pointing && <rect x="-1" y="22" width="11" height="30" rx="5.5" fill={SKIN} {...STROKE} />}
    </g>
  );
}

/** A small notebook she carries in her hanging hand. */
function Notebook() {
  return (
    <g transform="translate(-2 68) rotate(8)">
      <rect x="-13" y="0" width="28" height="38" rx="3" fill="var(--cream)" {...STROKE} strokeWidth="3.5" />
      <path d="M-7 8 H9 M-7 15 H9 M-7 22 H5" fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      <path d="M7 0 V12 L10 9 L13 12 V0 Z" fill="var(--flame)" />
      <rect x="-11" y="-4" width="5" height="16" rx="2" fill="var(--ochre)" stroke="var(--ink)" strokeWidth="2" />
    </g>
  );
}

function Arm({ side, upper, lower, pointing, wave, holding }: { side: "l" | "r"; upper: number; lower: number; pointing?: boolean; wave?: boolean; holding?: boolean }) {
  const sx = side === "l" ? 106 : 194;
  const sy = 226;
  const t = "transform 650ms var(--ease-bounce)";
  return (
    <g style={{ transform: `translate(${sx}px, ${sy}px) rotate(${upper}deg)`, transition: t }}>
      {/* upper arm (sleeve): a soft pill */}
      <path d="M0 0 L0 62" stroke="var(--ink)" strokeWidth="32" strokeLinecap="round" />
      <path d="M0 0 L0 62" stroke="var(--sun)" strokeWidth="24" strokeLinecap="round" />
      <g className={wave ? "nova-wave" : undefined} style={{ transform: `translate(0px, 62px) rotate(${lower}deg)`, transition: t }}>
        <path d="M0 0 L0 44" stroke="var(--ink)" strokeWidth="30" strokeLinecap="round" />
        <path d="M0 0 L0 44" stroke="var(--sun)" strokeWidth="22" strokeLinecap="round" />
        {/* rolled cuff */}
        <path d="M-12 40 H12 M-11 46 H11" stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M-10 43 H10" stroke="var(--ochre)" strokeWidth="4" strokeLinecap="round" />
        {side === "r" && (
          <g transform="translate(0 50)">
            <rect x="-13" y="-3" width="26" height="7" rx="2" fill="var(--ochre)" stroke="var(--ink)" strokeWidth="2" />
            <circle cx="0" cy="0.5" r="6" fill="var(--cream)" stroke="var(--ink)" strokeWidth="2.5" />
            <path d="M0 0.5 V-2.5 M0 0.5 H2.5" stroke="var(--ink)" strokeWidth="1.5" strokeLinecap="round" />
          </g>
        )}
        {holding && <Notebook />}
        <Hand pointing={pointing} flip={side === "l"} />
      </g>
    </g>
  );
}

interface NovaProps {
  state: CharacterState;
  meta?: CharacterMeta;
  gaze: { x: number; y: number };
  framing?: NovaFraming;
  /** The cursor is close to her: she perks up and leans in. */
  near?: boolean;
}

export function Nova({ state, meta, gaze, framing = "full", near = false }: NovaProps) {
  // "listening" with meta.text === "typing" is the ask bar being focused: attentive, hands down, no sound bars
  const typing = state === "listening" && meta?.text === "typing";
  const pose = typing ? POSES.idle : POSES[state];
  // where she looks: cursor by default, up-right while thinking, right while pointing
  const gx = state === "thinking" ? 0.6 : state === "pointing" ? 1 : gaze.x;
  const gy = state === "thinking" ? -0.8 : state === "pointing" ? -0.3 : gaze.y;
  const px = gx * 5;
  const py = gy * 3.5;
  const perk = near || typing;
  const headTilt = state === "abstain" ? -7 : state === "thinking" ? 5 : gx * (perk ? 5 : 3);
  const headLean = perk ? -6 : 0;
  const browRaise = state === "listening" || state === "celebrate" || perk ? -6 : state === "thinking" ? 3 : 0;
  const browSad = state === "abstain";
  const leftArmUp = (state === "listening" && !typing) || state === "abstain";
  return (
    <svg viewBox={VIEWBOX[framing]} preserveAspectRatio="xMidYMax meet" className="nova" data-state={typing ? "attentive" : state} data-framing={framing} data-near={near} aria-hidden>
      <defs>
        <pattern id="nova-ht" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
          <circle cx="1.5" cy="1.5" r="1.1" fill="var(--ink)" opacity="0.22" />
        </pattern>
        <pattern id="nova-ht-light" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(32)">
          <circle cx="1.5" cy="1.5" r="1.1" fill="var(--cream)" opacity="0.18" />
        </pattern>
        <pattern id="nova-dots" width="20" height="20" patternUnits="userSpaceOnUse" patternTransform="rotate(18)">
          <circle cx="6" cy="6" r="3.2" fill="var(--cream)" opacity="0.9" />
        </pattern>
      </defs>

      {/* ground shadow */}
      <ellipse cx="150" cy="390" rx="78" ry="8" fill="rgba(27,23,21,0.28)" />

      <g className="nova-body">
        {/* legs: leggings, striped socks, laced boots */}
        <rect x="118" y="296" width="26" height="72" rx="6" fill="var(--ink)" />
        <rect x="156" y="296" width="26" height="72" rx="6" fill="var(--ink)" />
        {/* knee patches */}
        <ellipse cx="131" cy="326" rx="8" ry="6" fill={HAIR_LIGHT} />
        <ellipse cx="169" cy="326" rx="8" ry="6" fill={HAIR_LIGHT} />
        <g>
          <rect x="116" y="338" width="30" height="22" rx="4" fill="var(--chalk)" {...STROKE} />
          <rect x="154" y="338" width="30" height="22" rx="4" fill="var(--chalk)" {...STROKE} />
          <path d="M118 345 H144 M118 352 H144 M156 345 H182 M156 352 H182" stroke="var(--sun)" strokeWidth="3.5" />
        </g>
        <path d="M110 388 L110 366 Q110 356 120 356 H142 Q150 356 150 366 V388 Z" fill="var(--flame-deep)" {...STROKE} />
        <path d="M150 388 L150 366 Q150 356 160 356 H182 Q192 356 192 366 V388 Z" fill="var(--flame-deep)" {...STROKE} />
        <path d="M118 364 l14 4 m-14 5 l14 4 m-14 5 l14 4 M158 364 l14 4 m-14 5 l14 4 m-14 5 l14 4" fill="none" stroke="var(--ink)" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M112 384 H150 M150 384 H190" stroke="var(--chalk)" strokeWidth="3" />
        {/* lace bows */}
        <path d="M131 362 l-6 -4 l1 7 z M131 362 l6 -4 l-1 7 z M171 362 l-6 -4 l1 7 z M171 362 l6 -4 l-1 7 z" fill="var(--chalk)" stroke="var(--ink)" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M102 390 H198" stroke="var(--ink)" strokeWidth="4" strokeLinecap="round" />

        {/* left arm behind the body (carries the notebook when hanging) */}
        <Arm side="l" upper={pose.lUpper} lower={pose.lLower} holding={!leftArmUp} />

        {/* neck + ribbed turtleneck */}
        <rect x="134" y="192" width="32" height="36" rx="8" fill={SKIN} {...STROKE} />
        <path d="M122 212 H178 V238 H122 Z" fill="var(--sun)" {...STROKE} />
        <path d="M130 216 V234 M138 216 V234 M146 216 V234 M154 216 V234 M162 216 V234 M170 216 V234" stroke="var(--ochre)" strokeWidth="2" opacity="0.8" />

        {/* polka-dot pinafore */}
        <path d="M104 232 Q150 216 196 232 L208 320 Q150 334 92 320 Z" fill="var(--moss)" {...STROKE} />
        <path d="M104 232 Q150 216 196 232 L208 320 Q150 334 92 320 Z" fill="url(#nova-dots)" />
        <path d="M104 232 Q150 216 196 232 L208 320 Q150 334 92 320 Z" fill="url(#nova-ht-light)" />
        {/* straps, buttons, name badge */}
        <path d="M126 232 L124 264 M174 232 L176 264" stroke="var(--ink)" strokeWidth="4" strokeLinecap="round" />
        <circle cx="126" cy="266" r="5" fill="var(--sun)" stroke="var(--ink)" strokeWidth="3" />
        <circle cx="174" cy="266" r="5" fill="var(--sun)" stroke="var(--ink)" strokeWidth="3" />
        <rect x="168" y="276" width="22" height="14" rx="3" fill="var(--cream)" {...STROKE} strokeWidth="2.5" />
        <path d="M174 287 V279 L184 287 V279" fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {/* chest pocket with a note and a pencil */}
        <path d="M128 270 L130 262 L148 266 L146 274 Z" fill="var(--cream)" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" />
        <g transform="translate(150 254) rotate(14)">
          <rect x="-3" y="0" width="6" height="22" rx="1" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2" />
          <path d="M-3 0 L0 -6 L3 0 Z" fill={SKIN} stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" />
          <path d="M-1.2 -4 L0 -6.5 L1.2 -4 Z" fill="var(--ink)" />
        </g>
        <rect x="126" y="272" width="30" height="24" rx="5" fill="var(--moss-deep)" {...STROKE} strokeWidth="3.5" />

        {/* satchel: strap across the chest, bag on the hip (sways with her) */}
        <path d="M178 238 L100 306" stroke="var(--ink)" strokeWidth="13" strokeLinecap="round" />
        <path d="M178 238 L100 306" stroke="var(--cocoa)" strokeWidth="7" strokeLinecap="round" />
        <path d="M172 246 L108 300" stroke="var(--sun)" strokeWidth="1.5" strokeDasharray="3 4" strokeLinecap="round" opacity="0.8" />
        {/* enamel pin on the strap */}
        <circle cx="150" cy="262" r="7" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2.5" />
        <path d="M150 257.5 l1.3 3 l3.2 .3 l-2.4 2.1 l.7 3.1 l-2.8 -1.6 l-2.8 1.6 l.7 -3.1 l-2.4 -2.1 l3.2 -.3 z" fill="var(--ink)" />
        <g className="nova-satchel">
          <rect x="70" y="296" width="44" height="36" rx="7" fill="var(--cocoa)" {...STROKE} />
          <path d="M74 300 H110 M74 328 H110" stroke="var(--sun)" strokeWidth="1.5" strokeDasharray="3 3" opacity="0.7" />
          <path d="M70 304 Q92 300 114 304 V314 Q92 318 70 314 Z" fill={SKIN_DEEP} {...STROKE} strokeWidth="3" />
          <rect x="86" y="310" width="12" height="9" rx="2" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2.5" />
        </g>

        {/* head group: hair, face, features */}
        <g className="nova-head" style={{ transform: `rotate(${headTilt}deg) translate(${gx * 3}px, ${gy * 2 + headLean}px)`, transformOrigin: "150px 200px", transition: "transform 500ms var(--ease-out)" }}>
          {/* afro + puffs */}
          <circle cx="150" cy="132" r="86" fill={HAIR} />
          <circle cx="150" cy="132" r="86" fill="url(#nova-ht-light)" />
          <g className="nova-puff nova-puff-l">
            <circle cx="98" cy="68" r="34" fill={HAIR} {...STROKE} />
            <path d="M80 60 q4 -12 16 -16 M86 84 q-6 -6 -4 -16" fill="none" stroke={HAIR_LIGHT} strokeWidth="3.5" strokeLinecap="round" />
            {/* rose bow clip */}
            <path d="M78 46 l-12 -7 v14 z M78 46 l12 -7 v14 z" fill="var(--rose)" stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" />
            <circle cx="78" cy="46" r="3.5" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2" />
          </g>
          <g className="nova-puff nova-puff-r">
            <circle cx="202" cy="68" r="34" fill={HAIR} {...STROKE} />
            <path d="M186 56 q6 -10 18 -10 M214 84 q6 -6 4 -16" fill="none" stroke={HAIR_LIGHT} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx="222" cy="50" r="5" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2.5" />
          </g>
          <path d="M74 110 q-4 12 2 24 M224 104 q6 12 2 26 M112 196 q10 8 24 8 M96 92 q-2 10 4 18 M206 94 q4 10 -2 20" fill="none" stroke={HAIR_LIGHT} strokeWidth="3.5" strokeLinecap="round" />
          <circle cx="150" cy="132" r="86" fill="none" {...STROKE} />
          {/* headband */}
          <path d="M90 104 Q150 84 210 104 L212 118 Q150 98 88 118 Z" fill="var(--rose)" {...STROKE} />
          <circle cx="120" cy="103" r="2.2" fill="var(--cream)" /><circle cx="150" cy="98" r="2.2" fill="var(--cream)" /><circle cx="180" cy="103" r="2.2" fill="var(--cream)" />
          <circle cx="206" cy="104" r="9" fill="var(--sun)" stroke="var(--ink)" strokeWidth="3.5" />

          {/* ears + hoops */}
          <circle cx="92" cy="158" r="11" fill={SKIN} {...STROKE} />
          <circle cx="208" cy="158" r="11" fill={SKIN} {...STROKE} />
          <circle cx="90" cy="180" r="9" fill="none" stroke="var(--ochre)" strokeWidth="4" />
          <circle cx="210" cy="180" r="9" fill="none" stroke="var(--ochre)" strokeWidth="4" />
          {/* pencil behind the right ear */}
          <g transform="translate(216 128) rotate(-28)">
            <rect x="-3.5" y="0" width="7" height="34" rx="1.5" fill="var(--sun)" stroke="var(--ink)" strokeWidth="2.5" />
            <path d="M-3.5 34 L0 42 L3.5 34 Z" fill={SKIN} stroke="var(--ink)" strokeWidth="2.5" strokeLinejoin="round" />
            <rect x="-3.5" y="0" width="7" height="6" fill="var(--rose)" stroke="var(--ink)" strokeWidth="2.5" />
          </g>

          {/* face */}
          <ellipse cx="150" cy="152" rx="58" ry="62" fill={SKIN} {...STROKE} />
          <path d="M100 136 Q104 190 150 206 Q196 190 200 136" fill="url(#nova-ht)" opacity="0.6" />
          {/* hairline over the forehead */}
          <path d="M94 128 Q110 108 150 110 Q190 108 206 128 Q190 118 150 120 Q110 118 94 128 Z" fill={HAIR} />

          {/* cheeks + freckles */}
          <circle cx="114" cy="180" r="8" fill="var(--rose)" opacity="0.75" />
          <circle cx="186" cy="180" r="8" fill="var(--rose)" opacity="0.75" />
          {[104, 112, 120].map((x, i) => <circle key={x} cx={x} cy={172 + (i % 2) * 5} r="1.6" fill={SKIN_DEEP} />)}
          {[180, 188, 196].map((x, i) => <circle key={x} cx={x} cy={172 + (i % 2) * 5} r="1.6" fill={SKIN_DEEP} />)}

          {/* eyes */}
          <ellipse cx="128" cy="156" rx="12" ry="14" fill="var(--white)" stroke="var(--ink)" strokeWidth="3.5" />
          <ellipse cx="172" cy="156" rx="12" ry="14" fill="var(--white)" stroke="var(--ink)" strokeWidth="3.5" />
          <g style={{ transform: `translate(${px}px, ${py}px)`, transition: "transform 180ms ease-out" }}>
            <circle cx="128" cy="158" r="6.5" fill="var(--ink)" />
            <circle cx="172" cy="158" r="6.5" fill="var(--ink)" />
            <circle cx="130.5" cy="155" r="2.2" fill="var(--white)" />
            <circle cx="174.5" cy="155" r="2.2" fill="var(--white)" />
          </g>
          {/* eyelids (blink) */}
          <g className="nova-lids">
            <rect className="nova-lid" x="114" y="140" width="28" height="32" rx="13" fill={SKIN} />
            <rect className="nova-lid" x="158" y="140" width="28" height="32" rx="13" fill={SKIN} />
          </g>
          {/* lashes */}
          <path d="M117 144 Q128 138 139 144" fill="none" stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M161 144 Q172 138 183 144" fill="none" stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
          {/* round glasses */}
          <g fill="rgba(255,253,249,0.14)">
            <circle cx="128" cy="156" r="20" stroke="var(--ink)" strokeWidth="4" />
            <circle cx="172" cy="156" r="20" stroke="var(--ink)" strokeWidth="4" />
            <circle cx="128" cy="156" r="17" fill="none" stroke="var(--ochre)" strokeWidth="2" />
            <circle cx="172" cy="156" r="17" fill="none" stroke="var(--ochre)" strokeWidth="2" />
            <path d="M148 154 Q150 149 152 154" fill="none" stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
            <path d="M108 152 L96 148 M192 152 L204 148" fill="none" stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
            <path d="M115 147 q4 -7 11 -9 M159 147 q4 -7 11 -9" fill="none" stroke="var(--white)" strokeWidth="2.2" strokeLinecap="round" opacity="0.75" />
          </g>

          {/* brows */}
          <g style={{ transform: `translateY(${browRaise}px)`, transition: "transform 300ms var(--ease-out)" }}>
            {browSad ? (
              <>
                <path d="M112 130 Q124 124 138 132" fill="none" stroke="var(--ink)" strokeWidth="5" strokeLinecap="round" />
                <path d="M162 132 Q176 124 188 130" fill="none" stroke="var(--ink)" strokeWidth="5" strokeLinecap="round" />
              </>
            ) : (
              <>
                <path d="M112 128 Q126 120 139 126" fill="none" stroke="var(--ink)" strokeWidth="5" strokeLinecap="round" />
                <path d="M161 126 Q174 120 188 128" fill="none" stroke="var(--ink)" strokeWidth="5" strokeLinecap="round" />
              </>
            )}
          </g>

          {/* nose */}
          <path d="M145 178 Q150 187 157 180" fill="none" stroke={SKIN_DEEP} strokeWidth="3.5" strokeLinecap="round" />

          {/* mouth by state */}
          {state === "speaking" && (
            <g className="nova-mouth-talk">
              <ellipse cx="150" cy="197" rx="12" ry="8" fill="var(--ink)" />
              <rect x="141" y="190" width="18" height="4" rx="1.5" fill="var(--white)" />
              <ellipse cx="150" cy="201" rx="6" ry="3" fill="var(--rose)" />
            </g>
          )}
          {state === "celebrate" && (<><path d="M130 190 Q150 216 170 190 Z" fill="var(--ink)" /><path d="M134 191 H166 V195 Q150 199 134 195 Z" fill="var(--white)" /><path d="M140 203 Q150 212 160 203 Z" fill="var(--rose)" /></>)}
          {state === "abstain" && <path d="M138 198 Q144 192 150 198 Q156 204 162 198" fill="none" stroke="var(--ink)" strokeWidth="4" strokeLinecap="round" />}
          {state === "thinking" && <path d="M140 196 Q152 194 160 198" fill="none" stroke="var(--ink)" strokeWidth="4" strokeLinecap="round" />}
          {(state === "idle" || state === "pointing" || state === "listening") && (
            <>
              <path d="M134 192 Q150 207 166 192" fill="none" stroke="var(--ink)" strokeWidth="4" strokeLinecap="round" />
              <path d="M131 190 q-2 3 0 6 M169 190 q2 3 0 6" fill="none" stroke={SKIN_DEEP} strokeWidth="2.5" strokeLinecap="round" />
            </>
          )}
        </g>

        {/* right arm in front */}
        <Arm side="r" upper={pose.rUpper} lower={pose.rLower} pointing={state === "pointing"} wave={state === "celebrate"} />
      </g>

      {/* state props */}
      {state === "listening" && !typing && (
        <g fill="var(--moss)" transform="translate(40 150)">
          {[0, 1, 2, 3].map((i) => <rect key={i} className="wave-bar" x={i * 9} y="-14" width="5" height="28" rx="2.5" />)}
        </g>
      )}
      {state === "thinking" && (
        <g fill="var(--chalk)" stroke="var(--ink)" strokeWidth="3">
          <circle className="think-dot" cx="232" cy="92" r="6" />
          <circle className="think-dot" cx="250" cy="70" r="9" />
          <circle className="think-dot" cx="272" cy="40" r="14" />
        </g>
      )}
      {state === "celebrate" && (
        <g fill="var(--sun)" stroke="var(--ink)" strokeWidth="3">
          <path className="nova-spark" d="M258 70 l5 12 l12 5 l-12 5 l-5 12 l-5 -12 l-12 -5 l12 -5 z" />
          <path className="nova-spark" d="M232 30 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 z" />
        </g>
      )}
      {state === "abstain" && (
        <g fill="none" stroke="var(--ink)" strokeWidth="3" strokeLinecap="round">
          <path d="M234 92 q10 -10 0 -20 M246 104 q10 -10 0 -20" opacity="0.6" />
        </g>
      )}
    </svg>
  );
}
