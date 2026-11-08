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
from vectorize import PALETTE, ALL_ROLES, hex2rgb  # noqa: E402

BOXES = json.load(open(os.path.join(ROOT, "tools", "boxes.json")))

# Standing body height (head top -> sole) in *source sheet* pixels, measured per drawing row.
ROW_UNIT = {"sheet1": 864, "sheet2_top": 493, "sheet2_bottom": 358, "sheet3": 466}

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
    "head_calm":         ("Calm, slight confident smile (v2 set)", "right", None),
    "head_glance":       ("Cool side glance (v2 set)", "right", None),
    "head_chin_up":      ("Chin up, proud (v2 set)", "right", None),
    "head_yell":         ("Yelling (v2 set)", "right", None),
    "head_smile":        ("Big toothy smile (v2 set)", "right", None),
    "head_defeated":     ("Frowning down, sullen / defeated", "right", None),
    "head_surprised":    ("Surprised, eyes wide, mouth open", "right", None),
    "head_laughing":     ("Laughing hard", "right", None),
    "head_tired":        ("Tired, eyes down, drained", "right", None),
    "head_pleading":     ("Pleading / sad, brows up, mouth open", "right", None),
    "head_disgust":      ("Disgust / sneer, teeth clenched", "right", None),
    "head_afraid":       ("Afraid, wide eyes", "right", None),
    "head_smirk":        ("Smirk, one brow up", "right", None),
    "head_angry":        ("Angry, controlled glare", "right", None),
    "pose_fist_raise":   ("Fist raised in triumph", "right", "sheet3"),
    "pose_hands_hips":   ("Hands on hips, confident", "right", "sheet3"),
    "pose_sit_despair":  ("Sitting on a block, head in hands (block included)", "right", "sheet3"),
    "pose_stretch":      ("Arms overhead, stretching", "right", "sheet3"),
    "pose_run":          ("Running, mid-stride", "right", "sheet3"),
    "pose_point_up":     ("Pointing up at the sky", "right", "sheet3"),
    "prop_whiteboard": ("Rolling whiteboard (writable)", None, None),
    "prop_flipchart": ("Flip-chart easel (writable)", None, None),
    "prop_pointer": ("Teacher's pointer stick", None, None),
    "prop_marker": ("Marker pen", None, None),
    "prop_clipboard": ("Clipboard (writable)", None, None),
    "prop_book_open": ("Open book", None, None),
    "prop_book": ("Closed red book with bookmark", None, None),
    "prop_scroll": ("Parchment scroll (writable)", None, None),
    "prop_chalkboard": ("Chalkboard (writable, light text)", None, None),
    "prop_dumbbell": ("Hex dumbbell", None, None),
    "prop_barbell": ("Loaded barbell", None, None),
    "prop_plate": ("Weight plate", None, None),
    "prop_kettlebell": ("Kettlebell", None, None),
    "prop_shaker": ("Protein shaker", None, None),
    "prop_bottle": ("Water bottle", None, None),
    "prop_towel": ("Red towel", None, None),
    "prop_band": ("Resistance band", None, None),
    "prop_jump_rope": ("Jump rope", None, None),
    "prop_stopwatch": ("Stopwatch", None, None),
    "prop_phone": ("Smartphone", None, None),
    "prop_headphones": ("Headphones", None, None),
    "prop_sunglasses": ("Sunglasses", None, None),
    "prop_coffee": ("Takeaway coffee", None, None),
    "prop_backpack": ("Backpack", None, None),
    "prop_wallet": ("Wallet", None, None),
}

# writable props: which colour region is the writing surface (largest blob of that role)
SURFACE_ROLE = {"prop_whiteboard": ["paper", "paper-sh"], "prop_flipchart": ["paper", "paper-sh"], "prop_clipboard": ["paper", "paper-sh"],
                "prop_chalkboard": ["gear", "gear-dk", "gear-hi"], "prop_scroll": ["tan", "tan-sh"]}


CENTER_ANCHOR = {"pose_run"}


def anchors(alpha):
    ys, xs = np.nonzero(alpha)
    top, bot = ys.min(), ys.max()
    band = alpha[max(top, bot - max(4, int((bot - top) * 0.04))):bot + 1]
    bx = np.nonzero(band)[1]
    return dict(bbox=[int(xs.min()), int(top), int(xs.max()), int(bot)], footX=float(bx.mean()), groundY=float(bot))


def surface(quant_png, bbox, roles):
    """Largest connected blob of the given palette roles -> writable rect (fractions of bbox)."""
    from scipy import ndimage as ndi
    q = np.asarray(Image.open(quant_png).convert("RGBA"))
    m = np.zeros(q.shape[:2], bool)
    for r in roles:
        c = np.array(hex2rgb(ALL_ROLES[r]))
        m |= (np.abs(q[..., :3].astype(int) - c).sum(-1) < 6) & (q[..., 3] > 0)
    m = ndi.binary_closing(m, iterations=4)
    lab, k = ndi.label(m)
    if not k:
        return {}
    big = lab == (np.argmax(ndi.sum(m, lab, range(1, k + 1))) + 1)
    ys, xs = np.nonzero(big)
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    return {"surface": [round((xs.min() - x0) / bw, 3), round((ys.min() - y0) / bh, 3), round((xs.max() - x0) / bw, 3), round((ys.max() - y0) / bh, 3)]}


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
        kind = "pose" if name.startswith("pose") else ("prop" if name.startswith("prop") else "head")
        p = dict(kind=kind, w=w, h=h, desc=desc, facing=facing, **a)
        if name in CENTER_ANCHOR:  # mid-air / one-foot poses: anchor on the body centre
            p["footX"] = (a["bbox"][0] + a["bbox"][2]) / 2
        if kind == "pose":
            crop_h = BOXES[name]["box"][3] - BOXES[name]["box"][1]
            p["unit"] = round(ROW_UNIT[row] * h / crop_h, 1)
        if name in SURFACE_ROLE:
            p.update(surface(os.path.join(vec, name + ".quant.png"), a["bbox"], SURFACE_ROLE[name]))
            p["surfaceDark"] = name == "prop_chalkboard"
        parts[name] = p
        body = re.search(r"<g id=\"%s\">(.*)</g>" % name, svg, re.S).group(1)
        symbols.append(f'<symbol id="{name}" viewBox="0 0 {w} {h}">{body.strip()}</symbol>')
    style = "\n".join(f".{r}{{fill:{c};stroke:{c}}}" for r, c in ALL_ROLES.items())
    lib = (f'<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n<style>\n{style}\nsymbol path{{stroke-width:0.8;stroke-linejoin:round}}\n</style>\n'
           + "\n".join(symbols) + "\n</svg>\n")
    open(os.path.join(ROOT, "assets", "statue-library.svg"), "w").write(lib)
    js = ("/* AUTO-GENERATED by tools/build_library.py - do not edit by hand. */\n"
          f"window.STATUE = {json.dumps({'palette': ALL_ROLES, 'parts': parts}, indent=1)};\n"
          f"window.STATUE.symbols = {json.dumps(chr(10).join(symbols))};\n")
    open(os.path.join(ROOT, "engine", "library.js"), "w").write(js)
    print(len(parts), "parts;", os.path.getsize(os.path.join(ROOT, "engine", "library.js")) // 1024, "KB library.js")
    for n, p in parts.items():
        if p["kind"] == "pose":
            print(f"  {n:20s} unit={p['unit']:7.1f} footX={p['footX']:6.1f} groundY={p['groundY']:6.1f} h={p['h']}")


if __name__ == "__main__":
    main()
