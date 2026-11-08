# Statue Rig — code-animated character package

Your character (stone-gray statue, red laurel, red toga) turned into **editable SVG parts** plus a **timeline animation engine**. The engine moves him with the same motion grammar the reference channels use: pose-swap holds, pop-ins, idle breathing, push-in zooms, close-up expression punches and phrase-by-phrase text builds. It renders straight to MP4.

```
statue-rig/
├── assets/
│   ├── source/                  your two reference sheets (pipeline input)
│   ├── parts/*.svg              27 editable SVGs: 14 full-body poses + 13 head/expression busts
│   └── statue-library.svg       every part as a <symbol> in one file (open in Figma / Illustrator / Inkscape)
├── engine/
│   ├── library.js               generated bundle of parts + anchors (what the engine loads)
│   ├── animator.js              the animation engine (deterministic renderAt(t))
│   ├── player.html              preview / scrub a scene in the browser
│   ├── gallery.html             visual catalogue of every pose & expression with its name
│   ├── fonts.css, fonts/        bundled fonts (Permanent Marker, Bebas Neue, Anton, Cinzel)
├── scenes/demo.json             example scene (the 17 s style test)
└── tools/
    ├── render.js                scene JSON → MP4 or PNG still (Playwright + ffmpeg)
    ├── serve.js                 local server for player.html / gallery.html
    ├── cutout.py                cuts poses/heads out of the sheets (BiRefNet segmentation + clean-up)
    ├── vectorize.py             PNG → palette-classed SVG (vtracer)
    ├── build_library.py         SVGs → assets/statue-library.svg + engine/library.js
    ├── boxes.json               crop boxes & clean-up hints per part
    └── svg2png.js               QA helper
```

## Quick start

Requirements: Node 18+, `npm i` (installs Playwright), ffmpeg on PATH. Python is only needed to regenerate parts.

```bash
npm install
```

```bash
npx playwright install chromium
```

```bash
node tools/render.js scenes/demo.json out/demo.mp4
```

```bash
node tools/render.js scenes/demo.json out/thumb.png --still 15
```

```bash
node tools/serve.js
```
Then open `http://localhost:8080/engine/player.html?scene=/scenes/demo.json` (scrub and play), or `/engine/gallery.html` to browse every part.

Fast low-res preview: add `--scale 0.5`. Render a slice: `--from 3 --to 8`.

## How he is built

| Layer | What it is | Edit it by |
|---|---|---|
| **Parts** (`assets/parts/*.svg`) | Flat vector traces of your drawings. Every path carries a palette class (`.ink .stone .stone-mid .stone-sh .stone-hi .toga .toga-sh .toga-hi`) | Opening the SVG in any vector editor; recolouring by changing the class colours |
| **Palette** | 8 colours sampled from your sheets: ink `#0B0607`, stone `#988883`, stone-mid `#7F706B`, stone-shadow `#483B3A`, stone-highlight `#B8A79E`, toga `#4A0A10`, toga-shadow `#260A0C`, toga/laurel highlight `#741219` | `PALETTE` in `tools/vectorize.py` (permanent) or `"palette": {"toga": "#1C3F8A"}` in a scene (per video) |
| **Anchors** | Every pose knows where its feet are and how tall a full standing body is in its own drawing, so pose swaps stay the same size with feet planted | Automatic (`tools/build_library.py`) |
| **Engine** | Timeline of events → frame at any time `t` | Scene JSON (below) |

**Why pose swaps, not a bone rig:** the reference channels animate by holding a drawing for ~2–3 s, then cutting or popping to the next pose, with small idle motion in between. Your own drawings used as the pose library keep him looking *exactly* like your sheets. Re-posing a bone rig would distort the art. To add a new pose, draw it, add its crop to `tools/boxes.json`, and re-run the pipeline (see "Adding poses").

## Scene reference

A scene is JSON: canvas settings plus a list of timed events. Coordinates are **fractions of the frame (0–1)**. Text and stroke sizes are **px at 1080p** and scale with the canvas.

```json
{
  "width": 1920, "height": 1080, "fps": 30, "duration": 17,
  "background": { "color": "#ECE4D6", "grain": 0.45, "vignette": 0.3 },
  "palette": { "toga": "#4A0A10" },
  "talk": [[0.3, 2.3], [2.6, 3.6]],
  "audio": "voiceover.mp3",
  "groundShadow": true,
  "events": [ ... ]
}
```
- `talk`: time ranges when the narrator speaks. Close-ups bob subtly during these.
- `audio`: a path relative to the scene file. It is muxed into the MP4 and plays in the player.

### Events

| `type` | Fields | Notes |
|---|---|---|
| **pose** | `name`, `actor` (default `"hero"`), `x` (feet centre), `ground` (feet y, default 0.93), `height` (standing body height as a fraction of the frame, default 0.78), `scale`, `flip`, `enter`: `cut`·`pop`·`slide-left`·`slide-right`·`drop`·`rise`·`fade`, `dur`, `idle` (default true) | Omitted placement fields are **inherited** from that actor's previous pose, so `{"t":2.5,"type":"pose","name":"pose_thinking"}` swaps in place. `name: null` hides the actor; add `exit`: `pop`·`slide-left`·`slide-right`·`fade`·`fall` |
| **nudge** | `actor`, `kind`: `hop`·`squash`·`shake`·`lean`·`grow`, `dur`, `amp`, `dir` | Quick emphasis on a held pose |
| **closeup** | `name` (a `head_*` part, or `null` to end), `side`: `left`·`center`·`right` (or `x`), `fill` (bust height, default 0.98), `enter`: `cut`·`punch`·`pop`·`rise`, `shake`, `flip`, `bg` | Full-screen bust shot. Consecutive close-ups auto-"punch" on expression change |
| **text** | `id`, `text` (or `words` array, `"\n"` = line break), `font`: `marker`·`caps`·`impact`·`roman`, `size`, `color`, `stroke`, `strokeWidth`, `x`, `y`, `anchor`: `start`·`middle`·`end`, `maxWidth`, `lineHeight`, `every` (seconds between words; `0` = all at once), `enter`: `pop`·`fade`·`rise`, `upper`, `rotate`, `wobble`, `screen` | Remove with `{"type":"text","id":"…","off":true,"exit":"pop"}`. `screen:true` ignores the camera and draws over close-ups |
| **prop** | `id`, `kind`: `arrow` (`from`,`to`,`bend`,`head`), `circle` (`at`,`rx`,`ry`), `x`/`check` (`at`,`size`), `underline` (`from`,`to`), `panel` (`from`,`to`,`fill`,`radius`,`stroke`), `part` (`name`,`at`,`size`), `svg` (`markup`,`at`,`size`); plus `color`, `width`, `enter`: `draw`·`pop`·`fade`, `dur`, `float`, `layer:"back"`, `screen` | Hand-drawn marks draw on stroke by stroke. `panel` with `layer:"back"` builds split-screen backgrounds. `svg` drops in any icon or logo |
| **camera** | `zoom`, `x`, `y` (focus point), `rotate`, `dur`, `ease`: `linear`·`in`·`out`·`inOut` | `dur: 0` = instant punch-in / reset |
| **shake** | `dur`, `amp` (px) | Screen shake, close-ups included |
| **bg** | `color`, `dur` | Background colour change (cut or fade) |
| **flash** | `color`, `opacity`, `dur` | Impact flash |

### The reference-channel moves, as events

| Move from the research | How to do it |
|---|---|
| Hold → hard cut to a new pose (~2–3 s holds) | Successive `pose` events, `enter` omitted |
| Character pops in with overshoot | `"enter": "pop"` |
| Phrase-by-phrase handwritten build | `text` with `"font":"marker"`, `"every":0.25` |
| Push-in on a detail | `camera` with `zoom` 1.2–1.5 over 1–2 s |
| Expression close-up for the punchline | `closeup` with a `head_*` part. Swap the head for a "punch" |
| Rage beat | `closeup` `head_shout` + `"shake":true` + `shake` + `flash` |
| Loser vs winner split | Two actors (`"actor":"loser"`), `pose_kneel` vs `pose_front_proud`, `caps` labels, `x` / `check` props |
| Night / drama mood | `bg` to `#2A0A0D` (or `#191E24`) with cream text |

## Pose & expression names

Open `engine/gallery.html` for the visual list.

- **Poses:**
  - Standing: `pose_front_proud` · `pose_back_proud` · `pose_side_proud` · `pose_stand_34` · `pose_stand_side` · `pose_stand_back` · `pose_stand_front`
  - Gestures: `pose_gesture_open` · `pose_arms_crossed` · `pose_thinking` · `pose_pointing`
  - Others: `pose_kneel` · `pose_walk` · `pose_throne` (seated; no chair prop yet)
- **Heads:**
  - Calm / proud: `head_hero` · `head_confident` · `head_neutral_34` · `head_proud` · `head_side` · `head_smug_up`
  - Down / brooding: `head_brooding` · `head_brood_down` · `head_sideeye`
  - Loud / grinning: `head_shout` · `head_shout_2` · `head_grin` · `head_grin_2`

## Regenerating / adding poses (Python pipeline)

```bash
pip install "rembg[cpu]" vtracer opencv-python-headless scipy pillow numpy
```

```bash
python3 tools/cutout.py assets/source work/cut
```

```bash
python3 tools/vectorize.py work/cut work/vec
```

```bash
python3 tools/build_library.py work/vec
```
- `cutout.py` reads `character-sheet.png` / `character-reference.png` from the folder you pass (or `sheet1.png` / `sheet2.png`).
- It downloads the BiRefNet-lite segmentation model on first run.
- **Add a new pose:** put the new drawing on a sheet, add `"pose_name": {"sheet": "...", "box": [x0,y0,x1,y1]}` to `tools/boxes.json`, add a description, facing and row to `INFO` in `build_library.py`, then re-run the three commands. Leftover background bits can be removed with `"clean": true`, `"exclude"` rects (sheet coords) or `"exclude_poly"` polygons (crop coords).
- **Best results for new art:** draw new poses on a flat, plain background in a colour that isn't red or black. The cut-out is then trivial and more accurate.

## Known limitations
- **Flat colours.** The stone grain of the original paintings is simplified to 8 flat colours. A film-grain overlay (`background.grain`) brings back some texture.
- **No lip-sync or blinking.** Expressions change by swapping close-up heads. This matches the reference channels, which don't lip-sync. A mouth/eye rig would need separate mouth and eye drawings.
- **Poses only exist where you drew them.** Arms and legs aren't separately articulated. New poses come from new drawings (see above).
- **Small leftovers.** `pose_throne` has no chair. A few busts have slightly flat-cut tops where the laurel touched the panel edge.

## Fonts
Permanent Marker (Apache-2.0), Bebas Neue, Anton and Cinzel (SIL OFL 1.1), from Fontsource. All are free for commercial video use.
