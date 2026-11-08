"""Turn a production script (lines of voiceover + visual beats) into a timed scene and mixed audio.

usage: python3 tools/produce.py productions/<name>.json        -> scenes/<name>.json + out/<name>.wav
       node tools/render.js scenes/<name>.json out/<name>.mp4

Production format (see productions/workout_explainer.json):
{
  "name": "workout_explainer",
  "voice": {"voice": "am_michael", "speed": 1.08, "fx": "coach"},
  "music": {"file": "music_beat", "gain_db": -21, "duck_db": -8},
  "scene": { width/height/fps/background ... },          # copied into the scene
  "lead_in": 0.4, "tail": 1.5,
  "beats": [
    {"say": "Listen up.", "pause": 0.35, "hold": 0,
     "events": [ {"when": 0, "type": "pose", ...}, {"when": "@scroll", "type": "prop", "at": [0.7, 0.4], ...} ],
     "sfx":    [ {"when": "@war", "name": "impact", "gain_db": -6} ]}
  ]
}
Timing ("when"; "at" stays the on-screen position of props): number = seconds after the line starts; "@word" = when that word is
spoken (estimated); "@word+0.2"; "end" = when the line ends.  Any field whose value is
"@word" (e.g. textDelay) is resolved relative to the event's own time.
Sound effects are added automatically for pops, slides, close-up cuts, shakes, X/check
marks, dark-background beats and title text; set "sfx": false on an event to skip, or
"sfx": "name" to choose.
"""
import json, os, re, sys, subprocess, hashlib
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
TTS_DIR = os.environ.get("KOKORO_DIR", os.path.join(ROOT, "work", "tts"))
CACHE = os.path.join(ROOT, "work", "vo_cache")

SFX_GAIN = {"pop": -9, "whoosh": -11, "swoosh": -13, "whip": -11, "impact": -6, "thud": -8, "boom": -5,
            "ding": -10, "buzz": -13, "scribble": -15, "tick": -24, "riser": -13}

VOICE_FX = {
    # warm, punchy, compressed "coach in your ear" chain
    "coach": "highpass=f=85,equalizer=f=180:t=q:w=1:g=-1.5,equalizer=f=3000:t=q:w=1.2:g=3.5,"
             "equalizer=f=7500:t=q:w=1.5:g=1.5,acompressor=threshold=-21dB:ratio=4:attack=4:release=90:makeup=5,"
             "alimiter=limit=0.89",
    "none": "anull",
}


# ---------------- TTS ----------------
_kokoro = None


def tts(text, voice, speed):
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{speed}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".wav")
    if not os.path.exists(path):
        global _kokoro
        if _kokoro is None:
            from kokoro_onnx import Kokoro
            _kokoro = Kokoro(os.path.join(TTS_DIR, "kokoro-v1.0.onnx"), os.path.join(TTS_DIR, "voices-v1.0.bin"))
        s, sr = _kokoro.create(text, voice=voice, speed=speed, lang="en-us")
        s = resample_poly(s, SR, sr).astype(np.float32)
        sf.write(path, s, SR)
    x, _ = sf.read(path, dtype="float32")
    return trim(x)


def trim(x, thr=0.012, pad=0.03):
    a = np.abs(x)
    idx = np.nonzero(a > thr)[0]
    if not len(idx):
        return x
    i0 = max(0, idx[0] - int(pad * SR))
    i1 = min(len(x), idx[-1] + int(pad * SR))
    return x[i0:i1]


def word_times(text, dur):
    """Estimate when each word starts, weighting by length and punctuation pauses."""
    toks = text.split()
    weights, starts, acc = [], [], 0.0
    for w in toks:
        wt = len(re.sub(r"[^\w']", "", w)) + 1.5
        if re.search(r"[.!?]$", w):
            wt += 5
        elif re.search(r"[,;:—-]$", w) or w.endswith("..."):
            wt += 3
        weights.append(wt)
    total = sum(weights)
    for w, wt in zip(toks, weights):
        starts.append((re.sub(r"[^\w']", "", w).lower(), acc / total * dur))
        acc += wt
    return starts


# ---------------- timing ----------------
def resolve(at, t0, dur, words):
    if at is None or at == 0:
        return t0
    if isinstance(at, (int, float)):
        return t0 + at
    s = str(at).strip()
    if s == "end":
        return t0 + dur
    m = re.match(r"^@([\w']+)([+-][\d.]+)?$", s)
    if m:
        w = m.group(1).lower()
        for ww, tt in words:
            if ww == w:
                return t0 + tt + float(m.group(2) or 0)
        raise SystemExit(f'word "{w}" not found in line: {" ".join(x for x, _ in words)}')
    if re.match(r"^[+-]?[\d.]+$", s):
        return t0 + float(s)
    raise SystemExit(f"bad time: {at}")


def auto_sfx(ev, t):
    """Default sound for a scene event -> list of (time, name)."""
    if ev.get("sfx") is False:
        return []
    if isinstance(ev.get("sfx"), str):
        return [(t, ev["sfx"])]
    typ, enter = ev.get("type"), ev.get("enter")
    out = []
    if typ == "pose":
        if ev.get("name") is None:
            if ev.get("exit") in ("pop", "slide-left", "slide-right"):
                out.append((t, "swoosh"))
        elif enter == "pop":
            out.append((t, "pop"))
        elif enter in ("slide-left", "slide-right", "slide", "rise"):
            out.append((t, "whoosh"))
        elif enter == "drop":
            out += [(t, "whoosh"), (t + 0.42, "thud")]
    elif typ == "closeup" and ev.get("name"):
        out.append((t, "whip"))
    elif typ == "shake":
        out.append((t, "impact"))
    elif typ == "bg":
        c = ev.get("color", "#ffffff").lstrip("#")
        lum = sum(int(c[i:i + 2], 16) * w for i, w in ((0, .299), (2, .587), (4, .114)))
        out.append((t, "boom" if lum < 70 else "swoosh"))
    elif typ == "text" and not ev.get("off"):
        if ev.get("font", "marker") in ("caps", "roman", "impact") and ev.get("every", 0.28) == 0:
            out.append((t, "swoosh"))
        elif ev.get("font", "marker") == "marker":
            n = len(str(ev.get("text", "")).split())
            out += [(t + i * ev.get("every", 0.28), "tick") for i in range(n)]
    elif typ == "prop" and not ev.get("off"):
        k = ev.get("kind")
        if k == "x":
            out += [(t, "scribble"), (t + 0.15, "buzz")]
        elif k == "check":
            out += [(t, "scribble"), (t + 0.15, "ding")]
        elif k in ("circle", "underline", "arrow"):
            out.append((t, "scribble"))
        elif ev.get("enter") == "drop":
            out += [(t, "whoosh"), (t + 0.45, "thud")]
        elif k in ("part", "svg", "panel"):
            out.append((t, "thud" if ev.get("layer") == "back" else "pop"))
    elif typ == "nudge" and ev.get("kind") in ("hop", "grow"):
        out.append((t, "swoosh"))
    return out


# ---------------- audio ----------------
def db(x):
    return 10 ** (x / 20)


def place(buf, clip, t, gain=1.0):
    i = int(round(t * SR))
    if i >= len(buf) or i + len(clip) <= 0:
        return
    j = min(len(buf), i + len(clip))
    buf[max(0, i):j] += clip[max(0, -i):j - i] * gain


def ffmpeg_filter(x, chain):
    if chain == "anull":
        return x
    src, dst = os.path.join(CACHE, "_fx_in.wav"), os.path.join(CACHE, "_fx_out.wav")
    sf.write(src, x, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", chain, "-ar", str(SR), dst], check=True)
    y, _ = sf.read(dst, dtype="float32")
    return y[:len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y)))


def main():
    prod_path = sys.argv[1]
    P = json.load(open(prod_path))
    name = P.get("name") or os.path.splitext(os.path.basename(prod_path))[0]
    V = P.get("voice", {})
    voice, speed = V.get("voice", "am_michael"), V.get("speed", 1.05)

    t = P.get("lead_in", 0.4)
    events, sfx, talk, vo_clips = [], [], [], []
    for bi, beat in enumerate(P["beats"]):
        say = beat.get("say", "")
        clip = tts(say, voice, speed) if say else np.zeros(int(SR * beat.get("hold", 1.0)), np.float32)
        dur = len(clip) / SR
        words = word_times(say, dur) if say else []
        if say:
            vo_clips.append((t, clip))
            talk.append([round(t, 3), round(t + dur, 3)])
        for ev in beat.get("events", []):
            ev = dict(ev)
            et = resolve(ev.pop("when", 0), t, dur, words)
            for k, v in list(ev.items()):
                if isinstance(v, str) and v.startswith("@") and k not in ("text", "name", "id"):
                    ev[k] = round(resolve(v, t, dur, words) - et, 3)
            ev["t"] = round(et, 3)
            for st, sn in auto_sfx(ev, et):
                sfx.append((st, sn, SFX_GAIN.get(sn, -10)))
            ev.pop("sfx", None)
            events.append(ev)
        for s in beat.get("sfx", []):
            sfx.append((resolve(s.get("when", 0), t, dur, words), s["name"], s.get("gain_db", SFX_GAIN.get(s["name"], -10))))
        print(f"  beat {bi + 1:2d}  {t:6.2f}s  {dur:5.2f}s  {say[:60]}")
        t += dur + beat.get("pause", 0.35) + beat.get("hold", 0)
    total = t + P.get("tail", 1.5)

    # ---- mix ----
    n = int(SR * (total + 0.5))
    vo = np.zeros(n, np.float32)
    for st, c in vo_clips:
        place(vo, c, st)
    vo = ffmpeg_filter(vo, VOICE_FX.get(V.get("fx", "coach"), V.get("fx", "anull")))
    fx = np.zeros(n, np.float32)
    lib = os.path.join(ROOT, "assets", "sfx")
    cache = {}
    for st, sn, g in sfx:
        if sn not in cache:
            cache[sn], _ = sf.read(os.path.join(lib, sn + ".wav"), dtype="float32")
        place(fx, cache[sn], st, db(g))
    mus = np.zeros(n, np.float32)
    M = P.get("music")
    if M:
        loop, _ = sf.read(os.path.join(lib, M.get("file", "music_beat") + ".wav"), dtype="float32")
        reps = int(np.ceil(n / len(loop)))
        mus = np.tile(loop, reps)[:n] * db(M.get("gain_db", -21))
        # sidechain duck under the voice
        envv = np.convolve(np.abs(vo), np.ones(int(SR * 0.05)) / int(SR * 0.05), mode="same")
        envv = np.minimum(1, envv / 0.05)
        sm = int(SR * 0.25)
        envv = np.convolve(envv, np.ones(sm) / sm, mode="same")
        mus *= 1 - (1 - db(M.get("duck_db", -8))) * envv
        fade = np.ones(n)
        fi, fo = int(SR * 0.8), int(SR * 2.0)
        fade[:fi] = np.linspace(0, 1, fi)
        fade[-fo:] = np.linspace(1, 0, fo)
        mus *= fade
    mix = vo + fx + mus
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    raw = os.path.join(CACHE, f"{name}_raw.wav")
    final = os.path.join(ROOT, "out", f"{name}.wav")
    sf.write(raw, mix, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(SR), "-ac", "2", final], check=True)

    scene = dict(P.get("scene", {}))
    scene.update({"title": P.get("title", name), "duration": round(total, 2), "talk": talk,
                  "audio": f"../out/{name}.wav", "events": events})
    scene_path = os.path.join(ROOT, "scenes", f"{name}.json")
    json.dump(scene, open(scene_path, "w"), indent=1)
    print(f"wrote {scene_path}  ({total:.1f} s, {len(events)} events, {len(sfx)} sfx)  and {final}")


if __name__ == "__main__":
    main()
