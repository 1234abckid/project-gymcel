"""Bundle the vector parts into the engine library.

Reads  <vec_dir>/*.svg + *.quant.png  (output of vectorize.py)
Writes assets/parts/*.svg          (one editable SVG per pose / head)
       assets/statue-library.svg   (all parts as <symbol>s - open in Figma / Illustrator / Inkscape)
       engine/library.js           (window.STATUE = {palette, parts, symbols}) used by the animator

Anchors: so that pose swaps keep the same size and the feet on the same
ground line, every pose gets
   footX, groundY : where the feet touch the ground (SVG px)
   unit           : how many SVG px one full standing body-height is in this drawing
Heads (busts) get their bounding box; the animator fits them to the frame.

usage: python3 tools/build_library.py <vec_dir>
"""
import json, os, re, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from vectorize import PALETTE  # noqa: E402

BOXES = json.load(open(os.path.join(ROOT, "tools", "boxes.json")))

# Standing body height (head top -> sole) in *source sheet* pixels, measured per drawing row.
ROW_UNIT = {"sheet1": 864, "sheet2_top": 493, "sheet2_bottom": 358}

INFO = {
    # name: (description, facing, row)
    "pose_front_proud":  ("Hands behind back, chin up - proud default (front 3/4)", "right", "sheet1"),
    "pose_back_proud":   ("Hands behind back, seen from behind", "back", "sheet1"),
    "pose_side_proud":   ("Hands behind back, profile", "right", "sheet1"),
    "pose_stand_34":     ("Fists down, 3/4 front, looking up-right", "right", "sheet2_top"),
    "pose_stand_side":   ("Profile, arms down", "right", "sheet2_top"),
    "pose_stand_back":   ("Back view, arms down", "back", "sheet2_top"),
    "pose_stand_front":  ("Front, arms down, chin up", "right", "sheet2_top"),
    "pose_gesture_open": ("Open-palm presenting gesture (explaining)", "right", "sheet2_top"),
    "pose_arms_crossed": ("Arms crossed, judging", "right", "sheet2_bottom"),
    "pose_thinking":     ("Hand on chin, thinking", "right", "sheet2_bottom"),
    "pose_pointing":     ("Pointing forward / at something", "right", "sheet2_bottom"),
    "pose_kneel":        ("Kneeling on one knee, head bowed (defeat / resolve)", "right", "sheet2_bottom"),
    "pose_walk":         ("Mid-stride walk", "right", "sheet2_bottom"),
    "pose_throne":       ("Seated, lounging (throne prop not included)", "right", "sheet2_bottom"),
    "head_hero":         ("Big heroic close-up, chin up, calm", "right", None),
    "head_confident":    ("Confident side-eye", "right", None),
    "head_brooding":     ("Brooding, looking down", "right", None),
    "head_shout":        ("Shouting / rage", "right", None),
    "head_grin":         ("Cocky grin", "right", None),
    "head_neutral_34":   ("Neutral 3/4", "right", None),
    "head_proud":        ("Proud, chin up", "right", None),
    "head_side":         ("Profile-ish, calm", "right", None),
    "head_smug_up":      ("Smug, looking up and sideways", "right", None),
    "head_brood_down":   ("Disappointed, eyes down", "right", None),
    "head_shout_2":      ("Shouting (alt)", "right", None),
    "head_grin_2":       ("Grin (alt)", "right", None),
    "head_sideeye":      ("Unimpressed side-eye", "right", None),
}


def anchors(alpha):
    ys, xs = np.nonzero(alpha)
    top, bot = ys.min(), ys.max()
    band = alpha[max(top, bot - max(4, int((bot - top) * 0.04))):bot + 1]
    bx = np.nonzero(band)[1]
    return dict(bbox=[int(xs.min()), int(top), int(xs.max()), int(bot)], footX=float(bx.mean()), groundY=float(bot))


def main():
    vec = sys.argv[1]
    parts, symbols = {}, []
    os.makedirs(os.path.join(ROOT, "assets", "parts"), exist_ok=True)
    for name, (desc, facing, row) in INFO.items():
        svg = open(os.path.join(vec, name + ".svg")).read()
        open(os.path.join(ROOT, "assets", "parts", name + ".svg"), "w").write(svg)
        w, h = map(int, re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
        alpha = np.asarray(Image.open(os.path.join(vec, name + ".quant.png")))[..., 3] > 0
        a = anchors(alpha)
        kind = "pose" if name.startswith("pose") else "head"
        p = dict(kind=kind, w=w, h=h, desc=desc, facing=facing, **a)
        if kind == "pose":
            crop_h = BOXES[name]["box"][3] - BOXES[name]["box"][1]
            p["unit"] = round(ROW_UNIT[row] * h / crop_h, 1)
        parts[name] = p
        body = re.search(r"<g id=\"%s\">(.*)</g>" % name, svg, re.S).group(1)
        symbols.append(f'<symbol id="{name}" viewBox="0 0 {w} {h}">{body.strip()}</symbol>')
    style = "\n".join(f".{r}{{fill:{c};stroke:{c}}}" for r, c in PALETTE.items())
    lib = (f'<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n<style>\n{style}\nsymbol path{{stroke-width:0.8;stroke-linejoin:round}}\n</style>\n'
           + "\n".join(symbols) + "\n</svg>\n")
    open(os.path.join(ROOT, "assets", "statue-library.svg"), "w").write(lib)
    js = ("/* AUTO-GENERATED by tools/build_library.py - do not edit by hand. */\n"
          f"window.STATUE = {json.dumps({'palette': PALETTE, 'parts': parts}, indent=1)};\n"
          f"window.STATUE.symbols = {json.dumps(chr(10).join(symbols))};\n")
    open(os.path.join(ROOT, "engine", "library.js"), "w").write(js)
    print(len(parts), "parts;", os.path.getsize(os.path.join(ROOT, "engine", "library.js")) // 1024, "KB library.js")
    for n, p in parts.items():
        if p["kind"] == "pose":
            print(f"  {n:20s} unit={p['unit']:7.1f} footX={p['footX']:6.1f} groundY={p['groundY']:6.1f} h={p['h']}")


if __name__ == "__main__":
    main()
