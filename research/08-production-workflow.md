# Deliverable 8 — Production Workflow (reconstruction)

> Neither channel publishes its tools or process. Everything here is **reverse-engineered from observable output** (frames, scripts, cadence) and labelled as such. Software names are *candidates that could reproduce the look*, not claims about what either creator uses.

## 1. What the output tells us about the process [Measured → Interpretation]

| Observation | Implication for workflow |
|---|---|
| One character redrawn in many static poses; holds of 2–4 s; few in-betweens visible at 1–2 s sampling | **Pose-library cutout animation**, not frame-by-frame |
| Push-in zooms, slides and pop-ins; text that builds phrase by phrase | Keyframed transforms in an editor or compositor |
| The same layouts recur (bedroom set, presenter lean, whiteboard card, loser / winner pair) | **Template scenes**, re-dressed per video |
| Diagrams (molecules, brain, dopamine bar) are new each video | Custom illustration is the main per-video cost |
| Real-photo inserts (merch, supplement tubs, app screenshots) | Simple compositing |
| Scripts re-use passages across videos and even across channels; sponsor reads re-used verbatim | Script templates and a reusable segment library |
| B: weekly uploads at 4–10 min with ~2.2–2.5 s holds | A repeatable pipeline, probably with more than one person or heavy asset reuse [Estimate] |
| A: an upload every ~3.7 weeks, irregular | A smaller operation or lower priority [Estimate] |
| B: app UI cards dropped in mid-video | Pre-built "plug" templates |

## 2. Pipeline

### Pre-production
1. **Topic selection.** A appears to pick by search phrase (exact-match titles; SEO tags). B appears to pick by emotional identity and contrarian angle (no tags; sentence-case declaratives) and takes requests through a public request board.
2. **Research.** Popular-science level: one mechanism per section, plus a named study or quote (B: 13 of 20 transcripts cite a study, theory or authority).
3. **Script.**
   - *A template:* problem image → [skit] → promise → 4–8 headed sections → sponsor → recap → banana catchphrase. ~520–1,300 words (2–7 min at ~170 WPM).
   - *B template:* scene → stakes → promise → model → protocol → twist → emotional close → "Stay Monke". ~600–1,300 words.
   - *Voice pass:* convert to "monkey English" (A: full caveman; B 2026: third-person "Monkey / he" with light broken grammar).
4. **Joke pass.** Innuendo / prop list (A); scenario, simile and shock lines (B).
5. **Storyboard / shot list.** Roughly one visual idea per sentence: a ~2.5–3 s hold works out to **~1 image per 7–9 words**. A 5-minute video needs roughly **100–130 visual states**, many of them re-used poses.

### Production
6. **Character pose library** (one-time, then extended): presenter lean, flex, thumbs-up, sleeping, phone-in-hand, desk / laptop, walking, hunched "loser", T-pose "winner", face close-ups with 6–10 expressions, mouth variants.
7. **Per-video illustrations:** props, diagrams, sets, any secondary characters (human contrast figures).
8. **Voice-over.** Single narrator plus extra voices for skits (A). Not analysable here: voice gender, recording method, and whether it's human or synthetic are unknown.
9. **Music / SFX.** Caption tags show music at outros and occasional SFX (`[screaming]`). Everything else is unknown.

### Post-production
10. **Assembly and animation:** place poses and props on the timeline against the VO; add zooms, pops and text builds; cut on sentence boundaries.
11. **Text layers:** handwritten section headers (A), whiteboard-card text (B), labels.
12. **Plug segment:** drop in a sponsor template (A) or app cards (B).
13. **Thumbnail:** redraw the key pose large; 1–4 words; one prop or contrast; signature background (white / cream).
14. **Publish:** A writes descriptions with the boilerplate plus a sponsor link plus 8–10 SEO tags. B writes the app link first, then a one-line summary, then community links, with no tags.

## 3. Tool categories that could reproduce the look

| Need | Candidate tools (examples) | Notes |
|---|---|---|
| Hand-drawn character and props | Procreate, Clip Studio Paint, Photoshop, Krita | A's marker wobble suggests a pressure brush; B's cleaner closed lines suit a monoline brush or vector |
| Vector alternative | Illustrator, Affinity Designer, Inkscape | Makes rigging and recolouring easier |
| Cutout animation / motion | After Effects, Moho, Toon Boom Harmony (cutout), Cavalry, Rive | Pose swaps plus transform keyframes are enough for the observed style |
| Editing | Premiere Pro, DaVinci Resolve, Final Cut, CapCut | Many cutout explainers are assembled directly in an NLE |
| Audio | Any DAW / editor (Audition, Reaper, Audacity), noise reduction | Not observable for these channels |
| Captions / timing | Auto-transcription tools to line visuals up with VO | |
| AI assistance (possible, not evidenced) | Script drafting, TTS, image ideation | **No evidence** that either channel uses AI for art or voice. Verbatim reuse is a templating sign, not an AI sign |

## 4. Reuse and efficiency

| Asset | Reusable? | Evidence |
|---|---|---|
| Character poses and expressions | **High** | The same presenter lean across A's videos; the same loser / winner pair across 7 B thumbnails |
| Backgrounds / sets | **High** | A's bedroom; B's bed, desk and whiteboard; white / cream voids need nothing |
| Diagram components (molecules, brain, graphs) | Medium | Testosterone molecule recurs on 4 A thumbnails |
| Section header and text styles | High | Templates |
| Sponsor / plug segments | High | A's Cal AI read re-used near-verbatim ×6; B's app cards |
| Thumbnail templates | High, but **over-use backfires** | A's before → after arrow: 338K first use → 49K / 21K later |
| Custom per video | Script, jokes, new props and diagrams, skits | Where the quality differences show up |

**Automatable:** caption generation, rough VO-to-visual timing, re-colouring, exporting, description templates.
**Needs human creativity:** topic choice, story cold opens, jokes, the thumbnail concept, the visual puns, the accuracy check.

## 5. Production complexity

| Channel | Rating | Rationale |
|---|---|---|
| A | **Low–medium** | Static poses, white void, ~3 s holds, re-used segments. Effort goes into props, diagrams and the occasional skit |
| B | **Medium** | More poses per minute (≈ 2.2–2.5 s holds), mood scenes (night / dark), whiteboard device, app inserts, 6–10-minute runtimes, weekly |

**Rough effort estimate for a 5-minute video in this style [Estimate, not observed]:**
- Script: 3–6 h.
- VO: 1–2 h.
- New illustration (20–40 assets on top of the library): 6–15 h.
- Assembly and animation: 6–12 h.
- Thumbnail: 1–3 h.
- **Total ≈ 17–38 person-hours.** It falls as the pose library grows.
