"""Production source for the workout explainer.

    python3 productions/workout_explainer.py          # writes productions/workout_explainer.json
    python3 tools/produce.py productions/workout_explainer.json
    node tools/render.js scenes/workout_explainer.json out/workout_explainer.mp4

Each beat = one voiceover line + the visuals timed to it.  "when" is the time
inside the line (seconds, "@word", "@word+0.2", or "end"); "at" on props is
their on-screen position.
"""
import json, os

BOLT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 140"><path d="M60 4 L14 78 L46 78 L36 136 L86 56 L54 56 L66 4 Z" fill="#E8B23A" stroke="#0B0607" stroke-width="7" stroke-linejoin="round"/></svg>'
HEART = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 90"><path d="M50 84 C20 62 5 46 5 27 C5 13 16 5 29 5 C38 5 46 10 50 18 C54 10 62 5 71 5 C84 5 95 13 95 27 C95 46 80 62 50 84Z" fill="#9E1A22" stroke="#0B0607" stroke-width="7" stroke-linejoin="round"/><path d="M24 26 C26 18 32 15 38 16" fill="none" stroke="#E2D8D3" stroke-width="6" stroke-linecap="round"/></svg>'
MOON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M62 6 A46 46 0 1 0 94 70 A38 38 0 1 1 62 6 Z" fill="#E2D8D3" stroke="#0B0607" stroke-width="6" stroke-linejoin="round"/><circle cx="20" cy="18" r="4" fill="#E2D8D3"/><circle cx="84" cy="22" r="3" fill="#E2D8D3"/></svg>'
CREAM, DARK, NIGHT, RED, GREEN = "#ECE4D6", "#2A0A0D", "#191E24", "#B3121C", "#2E7D32"


def title(n, label, extra=()):
    """'Number N. Label.' title card: big red number, then the label lands on its last word."""
    return {"say": f"Number {n}. {label}.", "pause": 0.25, "events": [
        {"when": 0, "type": "text", "id": f"title{n}", "text": f"#{n}", "font": "impact", "size": 220, "x": 0.5, "y": 0.3, "color": RED, "every": 0},
        {"when": "@" + label.split()[-1].lower(), "type": "text", "id": f"title{n}b", "text": label.upper(), "font": "caps", "size": 170, "x": 0.5, "y": 0.58, "every": 0},
        *extra]}


def clear_title(n):
    return [{"when": 0, "type": "text", "id": f"title{n}", "off": True, "exit": "pop"},
            {"when": 0, "type": "text", "id": f"title{n}b", "off": True, "exit": "pop"}]


def off(*ids, kind="prop", exit="cut"):
    return [{"when": "end", "type": kind, "id": i, "off": True, "exit": exit} for i in ids]


HIDE = {"when": "end", "type": "pose", "name": None}

P = {
    "name": "workout_explainer",
    "title": "What working out actually does to you",
    "voice": {"voice": "am_michael", "speed": 1.06, "fx": "coach"},
    "music": {"file": "music_beat", "gain_db": -22, "duck_db": -8},
    "scene": {"width": 1920, "height": 1080, "fps": 30, "background": {"color": CREAM, "grain": 0.45, "vignette": 0.3}},
    "lead_in": 0.5, "tail": 2.0,
    "beats": [
        # ---- hook ----
        {"say": "Listen up. You've got a body built for war... and you're using it to scroll.", "pause": 0.4, "events": [
            {"when": 0, "type": "pose", "name": "pose_fist_raise", "x": 0.4, "height": 0.8, "enter": "pop"},
            {"when": "@built", "type": "text", "id": "war", "text": "BUILT FOR WAR", "font": "caps", "size": 150, "x": 0.76, "y": 0.42, "color": RED, "every": 0},
            {"when": "@built", "type": "shake", "dur": 0.3, "amp": 10},
            {"when": "@and", "type": "text", "id": "war", "off": True},
            {"when": "@and", "type": "bg", "color": DARK},
            {"when": "@and", "type": "pose", "name": "pose_sit_despair", "x": 0.42, "sfx": False},
            {"when": "@scroll-0.15", "type": "prop", "id": "phone", "kind": "part", "name": "prop_phone", "at": [0.7, 0.42], "size": 0.3, "rotate": -10, "float": True},
            {"when": "@scroll+0.25", "type": "prop", "id": "phx", "kind": "x", "at": [0.7, 0.42], "size": 0.12}]},
        {"say": "Today, I'm gonna show you what working out actually does to you. No fluff. Let's go.", "pause": 0.3, "events": [
            {"when": 0, "type": "prop", "id": "phone", "off": True}, {"when": 0, "type": "prop", "id": "phx", "off": True},
            {"when": 0, "type": "bg", "color": CREAM},
            {"when": 0, "type": "pose", "name": "pose_hands_hips", "x": 0.27, "height": 0.8, "enter": "slide-left"},
            {"when": "@show", "type": "text", "id": "q", "text": "What working out actually does", "font": "marker", "size": 96, "x": 0.68, "y": 0.36, "maxWidth": 0.5, "every": 0.2},
            {"when": "@no", "type": "closeup", "name": "head_smirk", "side": "right"},
            {"when": "@go", "type": "closeup", "name": None},
            {"when": "@go", "type": "nudge", "kind": "hop", "dur": 0.4},
            *off("q", kind="text"), HIDE]},
        # ---- 1 brain ----
        title(1, "Your brain"),
        {"say": "Thirty minutes of training floods your head with dopamine and endorphins. That's a natural mood boost. No prescription needed.", "pause": 0.35, "events": [
            *clear_title(1),
            {"when": 0, "type": "pose", "name": "pose_gesture_open", "x": 0.27, "height": 0.8, "enter": "pop"},
            {"when": "@thirty", "type": "prop", "id": "sw", "kind": "part", "name": "prop_stopwatch", "at": [0.62, 0.32], "size": 0.2, "rotate": 8},
            {"when": "@dopamine", "type": "prop", "id": "bolt", "kind": "svg", "markup": BOLT, "at": [0.8, 0.32], "size": 0.26, "float": True},
            {"when": "@dopamine", "type": "text", "id": "dop", "text": "DOPAMINE + ENDORPHINS", "font": "caps", "size": 110, "x": 0.7, "y": 0.66, "every": 0},
            {"when": "@natural", "type": "closeup", "name": "head_smile"},
            {"when": "@prescription", "type": "closeup", "name": "head_glance"},
            {"when": "end", "type": "closeup", "name": None},
            *off("sw", "bolt"), *off("dop", kind="text"), HIDE]},
        # ---- 2 heart ----
        title(2, "Your heart"),
        {"say": "Every workout makes it stronger, so it pumps more blood with less effort. Your resting heart rate drops.", "pause": 0.35, "events": [
            *clear_title(2),
            {"when": 0, "type": "pose", "name": "pose_run", "x": 0.3, "height": 0.8, "enter": "slide-left"},
            {"when": "@stronger", "type": "prop", "id": "heart", "kind": "svg", "markup": HEART, "at": [0.72, 0.36], "size": 0.32, "float": True},
            {"when": "@stronger", "type": "nudge", "kind": "grow", "dur": 0.4},
            {"when": "@resting", "type": "text", "id": "rhr", "text": "Lower resting heart rate", "font": "marker", "size": 84, "x": 0.72, "y": 0.68, "maxWidth": 0.45, "every": 0.18},
            *off("heart", exit="pop"), *off("rhr", kind="text"), HIDE]},
        # ---- 3 sleep ----
        title(3, "Deep sleep"),
        {"say": "Train hard in the day, and you fall asleep faster and sleep deeper at night.", "pause": 0.35, "events": [
            *clear_title(3),
            {"when": 0, "type": "pose", "name": "pose_stretch", "x": 0.3, "height": 0.8, "enter": "pop"},
            {"when": "@fall", "type": "closeup", "name": "head_tired", "side": "right"},
            {"when": "@deeper", "type": "closeup", "name": None},
            {"when": "@deeper", "type": "bg", "color": NIGHT},
            {"when": "@deeper", "type": "prop", "id": "moon", "kind": "svg", "markup": MOON, "at": [0.72, 0.34], "size": 0.3, "float": True},
            {"when": "@night", "type": "text", "id": "zz", "text": "Z z z", "font": "marker", "size": 110, "x": 0.72, "y": 0.68, "color": CREAM, "every": 0.18},
            *off("moon"), *off("zz", kind="text"),
            {"when": "end", "type": "bg", "color": CREAM, "sfx": False}, HIDE]},
        # ---- 4 strength ----
        title(4, "Strength that lasts"),
        {"say": "After about thirty, you slowly lose muscle every decade. Lifting is how you fight back.", "pause": 0.35, "events": [
            *clear_title(4),
            {"when": 0, "type": "pose", "name": "pose_kneel", "x": 0.3, "height": 0.8, "enter": "pop"},
            {"when": "@lose", "type": "text", "id": "loss", "text": "MUSCLE LOSS AFTER 30", "font": "caps", "size": 120, "x": 0.7, "y": 0.4, "color": RED, "every": 0},
            {"when": "@lifting", "type": "text", "id": "loss", "off": True},
            {"when": "@lifting", "type": "pose", "name": "pose_fist_raise", "sfx": "pop"},
            {"when": "@lifting", "type": "prop", "id": "bb", "kind": "part", "name": "prop_barbell", "at": [0.7, 0.42], "width": 0.42},
            {"when": "@fight", "type": "prop", "id": "db", "kind": "part", "name": "prop_dumbbell", "at": [0.7, 0.72], "size": 0.17, "rotate": -10},
            {"when": "@back", "type": "shake", "dur": 0.35, "amp": 14},
            *off("bb", "db", exit="pop"), HIDE]},
        # ---- 5 confidence ----
        title(5, "Confidence"),
        {"say": "Every rep you finish is proof that you keep your promises to yourself.", "pause": 0.4, "events": [
            *clear_title(5),
            {"when": 0, "type": "pose", "name": "pose_front_proud", "x": 0.3, "height": 0.8, "enter": "pop"},
            {"when": "@proof", "type": "closeup", "name": "head_chin_up", "side": "right"},
            {"when": "@proof", "type": "text", "id": "pr", "text": "Proof you keep your promises.", "font": "marker", "size": 88, "x": 0.3, "y": 0.42, "maxWidth": 0.42, "every": 0.2, "screen": True},
            {"when": "end", "type": "closeup", "name": None}, *off("pr", kind="text"), HIDE]},
        # ---- plan ----
        {"say": "You don't need a fancy gym. Three sessions a week. Push-ups, squats, and a long walk. Just show up.", "pause": 0.4, "events": [
            {"when": 0, "type": "pose", "name": "pose_pointing", "x": 0.2, "height": 0.8, "enter": "slide-left"},
            {"when": "@fancy", "type": "prop", "id": "wb", "kind": "part", "name": "prop_whiteboard", "at": [0.64, 0.5], "size": 0.78, "layer": "back", "enter": "pop",
             "text": "3x a week: Push-ups. Squats. Long walk.", "font": "marker", "every": 0.3, "textDelay": "@three"},
            {"when": "@show", "type": "prop", "id": "ck", "kind": "check", "at": [0.86, 0.2], "size": 0.07, "color": GREEN},
            *off("wb", exit="pop"), *off("ck"), HIDE]},
        # ---- close ----
        {"say": "Discipline builds the body. The body builds the man. Now get moving.", "pause": 0.2, "hold": 1.0, "events": [
            {"when": 0, "type": "bg", "color": DARK},
            {"when": 0, "type": "pose", "name": "pose_point_up", "x": 0.33, "height": 0.8, "enter": "rise"},
            {"when": "@discipline", "type": "text", "id": "d1", "text": "DISCIPLINE BUILDS THE BODY.", "font": "roman", "size": 84, "x": 0.73, "y": 0.4, "maxWidth": 0.4, "color": CREAM, "every": 0.25},
            {"when": "@now", "type": "text", "id": "d1", "off": True},
            {"when": "@now", "type": "closeup", "name": "head_yell", "side": "right", "shake": True},
            {"when": "@now", "type": "shake", "dur": 0.45, "amp": 18},
            {"when": "@now", "type": "text", "id": "endt", "text": "NOW GET MOVING.", "font": "impact", "size": 130, "x": 0.3, "y": 0.45, "color": RED, "every": 0.22, "screen": True}]},
    ],
}

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workout_explainer.json")
    json.dump(P, open(out, "w"), indent=1)
    print("wrote", out)
