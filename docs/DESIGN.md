# Design system — "Paper Atlas"

The frontend was rebuilt (2026-11-07) around one idea: **the world is the page.** A real, geographically accurate
MapLibre globe sits *behind* the site; the content floats over it in chalk-coloured plates and speech bubbles.

## Visual direction

| Element | Choice | Why |
|---|---|---|
| Palette | vermilion `--flame #f2612a` page, `--ochre`, `--sun` yellow, `--rose` pink, `--moss` green, `--ink` near-black, `--chalk` / `--cream` plates, `--stone` grey | Warm, saturated, cohesive. Colour is semantic: moss = online, sun/ochre = physical catalogue records, ink = partner-verified, dashed grey = demo. |
| Display type | **Young Serif** (slab, ball terminals) | The slab headline voice of the reference. |
| Accent type | **Instrument Serif italic** | The italic "Stories." moments: eyebrows, the rotating hero word, "for “query”". |
| UI type | **Bricolage Grotesque** (variable, optical sizing) | Quirky grotesk; readable at small sizes, characterful at large. |
| Surfaces | `.plate-*`, `.bubble`, `.halftone`, grain overlay | Paper cut-out feel; bubbles tie everything to the guide "speaking". |
| Controls | pill buttons (`.btn`), chip filters, `.ask-pill` | No borders-on-everything dashboards. |
| Illustration | `components/art/Stamps.tsx` cartoon stamps per institution kind, `Shape` decorations | Flat colour, ink outlines, halftone fills. |

Tokens live in `frontend/app/globals.css`. Legacy names (`--paper`, `--teal`, `--brass`, `--rule`) are aliased to the new
palette so the partner portal restyles without touching its files.

## Motion

- `lib/motion.tsx`: GSAP + ScrollTrigger helpers — `useReveal` (rise / words / scale / wipe), `useParallax` (`data-speed`),
  `useTilt` (cursor 3D tilt), `useMagnetic`, `SplitWords`.
- `components/motion/SmoothScroll.tsx`: Lenis smooth scrolling synced to ScrollTrigger (off for reduced motion;
  inner scrollers use `data-lenis-prevent`).
- `app/template.tsx`: vermilion wipe page transition on every navigation.
- `components/motion/CursorDot.tsx`: trailing dot that grows over interactive elements (pointer: fine only).
- Everything respects `prefers-reduced-motion`: no idle globe spin, no parallax, no cursor, instant transitions.

## The world (globe)

`components/world/`

- `WorldStage.tsx` — fixed, full-viewport layer mounted from the root layout on `/` and `/search` only, so the camera
  glides from the home composition to the results instead of reloading. Sets `html[data-world=on]`, which makes
  `main` transparent to pointer events; every floating panel opts back in with `pointer-events-auto`.
- `WorldGlobe.tsx` — MapLibre GL 6 with `projection: globe` on OpenFreeMap vector tiles, re-painted by
  `worldPalette.ts` (cream-paper sea, moss-green continents with a halftone `background-pattern`, ink roads/boundaries) so the
  sphere reads as a bright sticker against the vermilion page. `GlobeHalo.tsx` makes it read as a *ball*: a shading layer
  (dark toward the rim, soft sheen top-left), an ink rim, a blurred drop shadow behind, and a tilted elliptical orbit whose
  far half is drawn in a `z-index: -1` layer *behind* the globe (the canvas is transparent outside the sphere) while the
  near half passes in front; a paper plane flies round it, shrinking behind the sphere (rAF, `ORBIT_PERIOD_S`). Plus three
  clouds hugging the rim and two sparks. It measures the sphere's on-screen
  circle from the map (`project(center)` and a point 85° east; `HORIZON_SHRINK ≈ 0.92` accounts for the perspective
  horizon) and hides itself when tilted, zoomed in, flat or larger than the viewport. Idle mode: pitch 0, the disc fills
  the right half (radius = min(0.5·h, 0.32·w) on desktop, its far edge may kiss the viewport edge) or peeks under the bubble (phones), rolls in from the
  east on first load, then keeps turning westward (one revolution per 80 s; pauses after any touch or while a pin is
  hovered). Once placed, idle pin re-publishes never recentre it,
  wheel scrolls the page, drag spins the world (touch devices get a static backdrop). Results mode: full interaction,
  `fitBounds` with insets for the drawer/controls, pins through React portals (`PinMarker.tsx`) with anchored cards.
  Selecting a record or a guide citation eases the camera to the holding institution.
- Fallbacks: **Flat map** toggle (mercator) in `WorldControls.tsx`; no WebGL → notice, and the list beside the map
  remains the complete, keyboard-accessible source of truth.
- `lib/worldStore.ts` — pins, mode, insets, projection. `Hero` publishes the directory as idle pins;
  `SearchView` publishes result pins.

## One page: stage ⇄ results (2026-11-07, second pass)

Home and search are **one URL** (`/`). `components/explorer/Explorer.tsx` reads the search params: no query → the
**stage** (`Stage.tsx`: Nova + her speech bubble with the ask pill, then the shortened home sections); any query →
`SearchView` (drawer + filters). Navigation inside the page uses native `history.pushState`, which Next syncs to
`useSearchParams`, so the globe and Nova never unmount. `/search?…` redirects to `/?…` for old links.

Asking: the bubble shrinks away, Nova (one persistent `CharacterDock`, FLIP-animated) walks from the stage to the
foot of the drawer, the drawer slides in, and the globe `flyTo`s / `fitBounds` the holders (the first idle → results
move is the long, cinematic one). “← Start over” reverses it.

Globe interaction on the stage is **cooperative**: ⌘/Ctrl + wheel and two-finger pinch zoom, plain wheel still
scrolls the page (MapLibre `cooperativeGestures`, hint restyled); +/− controls sit top-right. In results mode every
gesture goes straight to the world.

Desktop results: ask bar + drawer (left, own scroller), controls (top-right), online-only panel (bottom-right).
Mobile: ask bar, 44svh of world, then a sheet over it. Online items are never pinned.

## Nova, the guide

`components/character/Nova.tsx` is the default rig: a young Black archivist in the cut-out style (afro puffs with a
bead and a clip, rose dotted headband, round ochre-rimmed glasses, a pencil behind her ear, hoops, freckles and dimples,
ribbed sun turtleneck with rolled cuffs, polka-dot moss pinafore with a name badge and a pocket holding a note and a
pencil, a cocoa satchel across her chest, a notebook with a flame ribbon in her hanging hand, striped socks and laced
boots; real hands with a thumb, and an index finger that extends when she points). `framing="full"` (the stage) shows
her head to toe; `framing="bust"` (results dock, app header) crops the viewBox at the straps. On the stage she owns the
left half, as tall as the stage; a **short ask bar** (one-line headline, pill, chips) sits under her and covers her feet
(`z-30`), so nothing ever covers the world; phones stack the same way.

Reactions beyond the bus states: her eyes follow the cursor and wander when it rests; when the pointer comes within
40 px of her she perks up (brows, lean) and waves once (9 s cooldown); focusing the ask input sets `listening` with
`meta.text = "typing"`, which Nova renders as *attentive* (lean in, raised brows, no sound bars); hovering a pin on the
stage makes her point at the world; she waves on her own every 16–28 s. Puffs bounce and the satchel sways with her bob.
She fidgets (a short wave) every 16–28 s while idle, and points at the world when a pin is hovered on the stage.
(Original description:
sun turtleneck, moss pinafore, ochre hoops), pure SVG. States drive arm poses (two-segment arms, CSS-transitioned),
eyebrows, mouth and props: `idle` (bob + blink, eyes follow the cursor), `listening` (hand to ear, sound bars),
`thinking` (hand on chin, thought dots), `speaking` (talking mouth, nod), `abstain` (shrug), `pointing` (arm out to
the world), `celebrate` (wave + sparks).) Her name lives in `NOVA_NAME`; copy says “Nova says”.

## Character integration contract

A custom rig can still replace Nova. The site exposes a small bus in `frontend/lib/character.ts`:

```ts
window.__BHDH_CHARACTER__.registerRig({
  mount(el, { size }) { /* render into el; size is "hero" | "guide" | "mini"; return cleanup */ },
  setState(state, meta) { /* "idle" | "listening" | "thinking" | "speaking" | "abstain" | "pointing" | "celebrate" */ },
  lookAt(nx, ny) { /* cursor position, -1..1 relative to the slot centre */ },
});
```

Who sets which state:

| State | Set by |
|---|---|
| `listening` | push-to-talk while recording |
| `thinking` | guide request in flight |
| `speaking` (meta: answer text, citation count, first institution) | answer arrived; also while "Read aloud" plays |
| `abstain` | the guide refused to answer; mic error |
| `pointing` | a question was just submitted from the hero |
| `idle` | automatic fallback after transient states |

`components/character/CharacterSlot.tsx` renders the mount point and Nova until a rig registers. The explorer has one
slot (the dock, `hero` on the stage, `guide` beside the drawer); the institution app uses `mini` in every header.

## Institution app (`/app`)

Phone-first PWA for partner staff, same palette and parts, over the same partner API as the desktop portal
(`components/app/*`, `lib/appSession.ts`). Flame header plate with Nova in the corner, white tiles, ink bottom tab bar
with a raised vermilion **Scan** button. Screens: **Home** (counts, quick actions, activity), **Scan** (camera →
vision reads spines → Open Library candidates → confirm → draft; Nova thinks while the job runs), **Upload**
(CSV/JSON preview → commit · PDF finding aid · by-hand form), **Review** (status segments, search, publish /
withdraw by role), **Me** (institution switcher, install hint, sign out). The manifest's `start_url` is `/app`.

## Accessibility

Skip link, labelled controls, visible ink/sun focus rings, WCAG AA contrast on every plate, reduced-motion support,
editable voice transcripts, full result list beside/below the map, legend for pin kinds, `aria-expanded` on pins and
menu, Escape closes the menu.
