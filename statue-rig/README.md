# Statue Rig — code-animated character package

Your character (stone-gray statue, red laurel, red toga) turned into **editable SVG parts** plus a **timeline animation engine**. The engine moves him with the same motion grammar the reference channels use: pose-swap holds, pop-ins, idle breathing, push-in zooms, close-up expression punches and phrase-by-phrase text builds. It renders straight to MP4.

```
statue-rig/
├── assets/
│   ├── source/                  your reference sheets (pipeline input)
│   ├── parts/*.svg              72 editable SVGs: 20 full-body poses, 27 head/expression busts, 25 props
│   └── statue-library.svg       every part as a <symbol> in one file (open in Figma / Illustrator / Inkscape)
├── engine/
│   ├── library.js               generated bundle of parts + anchors (what the engine loads)
│   ├── animator.js              the animation engine (deterministic renderAt(t))
│   ├── player.html              preview / scrub a scene in the browser
│   ├── gallery.html             visual catalogue of every pose & expression with its name
│   ├── fonts.css, fonts/        bundled fonts (Permanent Marker, Bebas Neue, Anton, Cinzel)
├── scenes/demo.json             example scene (the 17 s style test)
├── scenes/showcase_v2.json      set-2 poses and expressions in motion
├── scenes/props_demo.json       props: whiteboard lesson, floating gym props, chalkboard
├── productions/                 narrated videos: script + timed visuals → produce.py
├── assets/sfx/                  synthesised sound effects + music bed (tools/sfx.py)
└── tools/
    ├── render.js                scene JSON → MP4 or PNG still (Playwright + ffmpeg)
    ├── produce.py               production script → TTS voiceover + auto SFX + music mix + timed scene
    ├── sfx.py                   synthesises the sound-effect library
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

## Making a narrated video (voiceover + sound effects)

```bash
pip install kokoro-onnx soundfile scipy numpy
```

```bash
mkdir -p work/tts && curl -L -o work/tts/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && curl -L -o work/tts/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

```bash
python3 productions/workout_explainer.py
```

```bash
python3 tools/produce.py productions/workout_explainer.json
```

```bash
node tools/render.js scenes/workout_explainer.json out/workout_explainer.mp4
```

- **Production files** (`productions/*.py` → `.json`): one *beat* per voiceover line, each with the visual events timed inside it.
  - `"when"` sets the timing: seconds after the line starts, `"@word"` (when that word is spoken), `"@word+0.2"`, or `"end"`.
  - `"at"` stays the on-screen position for props.
- **Voice:** Kokoro TTS runs locally, voice `am_michael` at 1.06× speed, with a "coach" chain on top (high-pass, presence boost, compression, limiter). Other male voices: `am_fenrir`, `am_onyx`, `am_eric`, `am_liam`, `am_puck`, `bm_george`, `bm_lewis` (British). Change `"voice"` in the production. Lines are cached, so re-running after a visual-only change is instant.
- **Sound effects** are added automatically:

  | Event | Sound |
  |---|---|
  | Pop-in | `pop` |
  | Slide | `whoosh` |
  | Close-up cut | `whip` |
  | Shake | `impact` |
  | Background to dark | `boom` |
  | Title text | `swoosh` |
  | Handwritten words | soft `tick` |
  | Board landing | `thud` |
  | X mark | `scribble` + `buzz` |
  | Check mark | `scribble` + `ding` |

  Override per event with `"sfx": "name"` or `"sfx": false`, or add extras in a beat's `"sfx": [...]`. All effects are synthesised by `tools/sfx.py` into `assets/sfx/`, so there are no samples and no licences.
- **Music:** `music_beat` (96 bpm drums and bass, also synthesised) dips by 8 dB under the voice. The final mix is loudness-normalised to −14 LUFS, YouTube's target.
- **Using your own recorded voiceover instead of TTS:** make the scene by hand, set `"audio"` to your file, and set `"talk"` to the ranges where you speak.
- **Word timing** is estimated from the script, not detected from the audio, so a visual can land a fraction of a second early or late. Nudge it with `"@word+0.2"`.

## How he is built

| Layer | What it is | Edit it by |
|---|---|---|
| **Parts** (`assets/parts/*.svg`) | Flat vector traces of your drawings. Every path carries a palette class (`.ink .stone .stone-mid .stone-sh .stone-hi .toga .toga-sh .toga-hi`) | Opening the SVG in any vector editor; recolouring by changing the class colours |
| **Palette** | 8 character colours (props add 11 more: paper, gear, metal, tan, leather ± shades) sampled from your sheets: ink `#0B0607`, stone `#988883`, stone-mid `#7F706B`, stone-shadow `#483B3A`, stone-highlight `#B8A79E`, toga `#4A0A10`, toga-shadow `#260A0C`, toga/laurel highlight `#741219` | `PALETTE` in `tools/vectorize.py` (permanent) or `"palette": {"toga": "#1C3F8A"}` in a scene (per video) |
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
| **prop** | `id`, `kind`: `part` (`name` = a `prop_*` / any part, `at`, `size`/`width`, `rotate`, `flip`, `text`… see Props), `arrow` (`from`,`to`,`bend`,`head`), `circle` (`at`,`rx`,`ry`), `x`/`check` (`at`,`size`), `underline` (`from`,`to`), `panel` (`from`,`to`,`fill`,`radius`,`stroke`), `part` (`name`,`at`,`size`), `svg` (`markup`,`at`,`size`); plus `color`, `width`, `enter`: `draw`·`pop`·`fade`, `dur`, `float`, `layer:"back"`, `screen` | Hand-drawn marks draw on stroke by stroke. `panel` with `layer:"back"` builds split-screen backgrounds. `svg` drops in any icon or logo |
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
  - **Set 2** — one consistent bust framing, so they swap seamlessly in close-ups. Prefer mixing within a set: set-2 busts include the shoulders, so their heads read smaller than set 1's.
    - `head_calm` · `head_glance` · `head_chin_up` · `head_yell` · `head_smile`
    - `head_defeated` · `head_surprised` · `head_laughing` · `head_tired` · `head_pleading`
    - `head_disgust` · `head_afraid` · `head_smirk` · `head_angry`

## Props

25 props, all on the same flat palette as the character:
- **Teaching:** `prop_whiteboard`\*, `prop_flipchart`\*, `prop_clipboard`\*, `prop_chalkboard`\*, `prop_scroll`\*, `prop_pointer`, `prop_marker`
- **Books:** `prop_book_open`, `prop_book`
- **Gym:** `prop_dumbbell`, `prop_barbell`, `prop_plate`, `prop_kettlebell`, `prop_shaker`, `prop_bottle`, `prop_towel`, `prop_band`, `prop_jump_rope`, `prop_stopwatch`
- **Everyday:** `prop_phone`, `prop_headphones`, `prop_sunglasses`, `prop_coffee`, `prop_backpack`, `prop_wallet`

\* writable: the board's writing area was detected automatically.

```json
{ "t": 0, "type": "prop", "id": "wb", "kind": "part", "name": "prop_whiteboard", "at": [0.63, 0.5], "size": 0.78,
  "enter": "pop", "layer": "back", "text": "Sleep 8 hours. Lift 4x a week.", "font": "marker", "every": 0.28, "textDelay": 0.9 }
```
- **Placement:** `at` is the centre of the visible drawing. Size it with `size` (height as a fraction of the frame) or `width` (fraction of frame width). Also takes `rotate` (degrees), `flip`, `float` (gentle bob), `enter` / `exit` (`pop`, `fade`, `drop`...), and `layer: "back"` to put it behind the character.
- **Board text** (writable props only): the text auto-fits the writing area and builds word by word. Options: `font`, `every`, `textDelay` (seconds after the prop appears), `textSize` (force a size), `textColor`, `padding`, `textEnter`. Chalkboard text defaults to light. Board text is skipped if the prop is rotated.
- **Removing:** `{"type":"prop","id":"wb","off":true,"exit":"pop"}` also removes its board text.
- **New props:** add them to a transparent sheet named `prop_<name>`. If the prop is writable, add it to `SURFACE_ROLE` in `build_library.py`.

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
- **Transparent sheets (e.g. ChatGPT PNGs):** use `"method": "alpha"` in `boxes.json`. The figure is taken straight from the alpha channel, with no segmentation model or clean-up needed. Add the file to `SHEET_FILES` in `cutout.py`. Poses on a new sheet also need their standing body height (source px) in `ROW_UNIT` in `build_library.py`.
- **Poses that don't stand on both feet** (running, jumping): add the name to `CENTER_ANCHOR` in `build_library.py` so swaps anchor on the body centre.

## Known limitations
- **Flat colours.** The stone grain of the original paintings is simplified to 8 flat colours. A film-grain overlay (`background.grain`) brings back some texture.
- **No lip-sync or blinking.** Expressions change by swapping close-up heads. This matches the reference channels, which don't lip-sync. A mouth/eye rig would need separate mouth and eye drawings.
- **Poses only exist where you drew them.** Arms and legs aren't separately articulated. New poses come from new drawings (see above).
- **Small leftovers.** `pose_throne` has no chair. A few busts have slightly flat-cut tops where the laurel touched the panel edge.

## Fonts
Permanent Marker (Apache-2.0), Bebas Neue, Anton and Cinzel (SIL OFL 1.1), from Fontsource. All are free for commercial video use.
