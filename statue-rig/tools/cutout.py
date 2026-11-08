"""Cut the character out of the reference sheets.

The sheet backgrounds (dark reds #250407-#570B11 and near-black) are almost the
same colour as the toga, so colour keying fails.  Instead we use the drawing's
own black outline as a wall: background = every non-ink pixel reachable from
the crop border without crossing ink.  The outline itself is kept as a band
around the interior.

usage: python3 tools/cutout.py <sheets_dir> <out_dir> [name ...]
"""
import json, sys, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
BOXES = json.load(open(os.path.join(HERE, "boxes.json")))


def ink_mask(a):
    """Neutral near-black linework (outline + hard shadow shapes)."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(-1)
    return (mx < 34) & ((r - g) < 14) & ((r - b) < 14)


def cut(sheet, box, holes, scale):
    x0, y0, x1, y1 = box
    a = sheet[y0:y1, x0:x1].astype(int)
    ink = ink_mask(a)
    # seal 1-2px gaps in the outline so the flood can't leak into the toga
    sealed = ndi.binary_closing(ink, structure=np.ones((3, 3)), iterations=1)
    free = ~sealed
    lab, n = ndi.label(free)
    border = np.zeros_like(free)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    bg_labels = set(np.unique(lab[border & free])) - {0}
    for hx, hy in holes:
        l = lab[hy - y0, hx - x0]
        if l:
            bg_labels.add(l)
    bg = np.isin(lab, list(bg_labels))
    interior = free & ~bg
    # drop specks (sparkles, texture blobs)
    il, k = ndi.label(interior)
    if k:
        sizes = ndi.sum(interior, il, range(1, k + 1))
        keep = np.isin(il, np.where(sizes > max(40, sizes.max() * 0.002))[0] + 1)
        interior = keep
    band = max(3, int(round(4 * scale)))
    near = ndi.binary_dilation(interior, iterations=band)
    char = interior | (sealed & near)
    # keep the single largest connected blob (removes pillars, labels, neighbours)
    cl, k = ndi.label(char)
    if k > 1:
        sizes = ndi.sum(char, cl, range(1, k + 1))
        char = cl == (np.argmax(sizes) + 1)
    char = ndi.binary_fill_holes(char) & (char | ~bg)  # close pinholes but not real gaps
    rgba = np.dstack([a.astype(np.uint8), (char * 255).astype(np.uint8)])
    return rgba


def cut_alpha(sheet_rgba, box, holes, scale):
    """For sheets that already have a transparent background (e.g. ChatGPT PNGs).
    Pick the figure with a strict alpha threshold (so faint fringes don't glue
    neighbours together), then keep its softer edge pixels."""
    x0, y0, x1, y1 = box
    a = sheet_rgba[y0:y1, x0:x1]
    core = largest(ndi.binary_opening(a[..., 3] > 200, iterations=1))
    m = (a[..., 3] > 128) & ndi.binary_dilation(core, iterations=3)
    m = ndi.binary_fill_holes(m)
    return np.dstack([a[..., :3].astype(np.uint8), (m * 255).astype(np.uint8)])


def largest(m):
    cl, k = ndi.label(m)
    if k > 1:
        sizes = ndi.sum(m, cl, range(1, k + 1))
        m = cl == (np.argmax(sizes) + 1)
    return m


def clean_leaks(a, m, keep_bottom):
    """Remove background patches the model kept outside the drawn outline.

    A leak is a non-ink region inside the mask that (1) touches the mask edge
    over a good part of its own boundary, (2) is not stone-coloured.  Real
    character regions (toga panels, laurel leaves) are wrapped in the black
    outline, so they don't touch the mask edge.
    """
    ink = ink_mask(a)
    free = m & ~ndi.binary_dilation(ink, iterations=1)
    lab, k = ndi.label(free)
    if not k:
        return m
    outside = ~m
    edge = ndi.binary_dilation(outside, iterations=2) & m
    r, g = a[..., 0], a[..., 1]
    stone = (g > 45) & ((r - g) < 30)
    bottom_rows = np.zeros_like(m)
    bottom_rows[-3:, :] = True
    out = m.copy()
    for i in range(1, k + 1):
        comp = lab == i
        n = comp.sum()
        if n < 30:
            continue
        perim = comp & ~ndi.binary_erosion(comp)
        touch = (perim & edge).sum() / max(1, perim.sum())
        if keep_bottom and (comp & bottom_rows).any():
            continue
        if np.median(r[comp]) > 90:  # bright laurel / toga highlights are never background
            continue
        if touch > 0.25 and stone[comp].mean() < 0.35:
            out[ndi.binary_dilation(comp, iterations=2) & m & ~stone] = False
    # drop ink crumbs no longer attached to anything substantial
    return ndi.binary_opening(out, iterations=1) | (out & stone)


def drop_edge_blobs(a, m):
    """Busts are cropped from panels; neighbouring panel corners are solid black
    blocks touching the crop's top/left/right edge.  Linework is thin, so remove
    only *thick* dark blobs that touch those edges."""
    dark = m & (a.max(-1) < 48)
    thick = ndi.binary_opening(dark, structure=np.ones((3, 3)), iterations=3)
    lab, k = ndi.label(thick)
    if not k:
        return m
    edge = np.zeros_like(m)
    edge[:3, :] = edge[:, :3] = edge[:, -3:] = True
    hit = set(np.unique(lab[edge & thick])) - {0}
    if hit:
        blob = ndi.binary_dilation(np.isin(lab, list(hit)), iterations=2) & dark
        m = m & ~blob
    return m


def name_is_bust(box, sheet):
    return CURRENT.get("kind") == "head"


SHEET_FILES = {"sheet1": "character-sheet.png", "sheet2": "character-reference.png", "sheet3": "character-expressions-2.png", "sheet4": "props.png"}
CURRENT = {}
EXCLUDE = []
EXCLUDE_POLY = []
_SESSIONS = {}
MODEL = os.environ.get("CUT_MODEL", "birefnet-general-lite")
BOOST = float(os.environ.get("CUT_BOOST", "1.0"))  # gamma <1 brightens dark art for the model


def cut_ml(sheet, box, holes, scale):
    """Segment with a rembg model (default BiRefNet-lite), then clean the mask."""
    from rembg import new_session, remove
    if MODEL not in _SESSIONS:
        _SESSIONS[MODEL] = new_session(MODEL)
    x0, y0, x1, y1 = box
    a = sheet[y0:y1, x0:x1]
    up = 2 if scale < 1.5 else 1
    src = a if BOOST == 1.0 else ((a / 255.0) ** BOOST * 255).astype(np.uint8)
    im = Image.fromarray(src).resize((a.shape[1] * up, a.shape[0] * up), Image.LANCZOS)
    m = np.asarray(remove(im, session=_SESSIONS[MODEL], only_mask=True, post_process_mask=True))
    m = np.asarray(Image.fromarray(m).resize((a.shape[1], a.shape[0]), Image.LANCZOS)) > 127
    for hx, hy in holes:  # manual background seeds for enclosed gaps
        lab, _ = ndi.label(m == m[hy - y0, hx - x0])
        m[lab == lab[hy - y0, hx - x0]] = False
    m = largest(m)
    m = ndi.binary_fill_holes(m) if not holes else m
    if CURRENT.get("clean"):
        m = clean_leaks(a.astype(int), m, keep_bottom=name_is_bust(box, sheet))
    if CURRENT.get("kind") == "head":
        m = drop_edge_blobs(a.astype(int), m)
    for ex in EXCLUDE:  # optional manual exclusion rects in sheet coords
        ex0, ey0, ex1, ey1 = ex
        m[max(0, ey0 - y0):max(0, ey1 - y0), max(0, ex0 - x0):max(0, ex1 - x0)] = False
    for poly in EXCLUDE_POLY:  # optional manual exclusion polygons in crop coords
        from PIL import ImageDraw
        pm = Image.new("L", (m.shape[1], m.shape[0]), 0)
        ImageDraw.Draw(pm).polygon([tuple(p) for p in poly], fill=255)
        m &= ~(np.asarray(pm) > 0)
    m = largest(m)
    return np.dstack([a.astype(np.uint8), (m * 255).astype(np.uint8)])


def main():
    sheets_dir, out_dir = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or [k for k in BOXES if not k.startswith("_")]
    os.makedirs(out_dir, exist_ok=True)
    sheets = {}
    for name in names:
        spec = BOXES[name]
        s = spec["sheet"]
        if s not in sheets:
            fn = os.path.join(sheets_dir, s + ".png")
            if not os.path.exists(fn):  # committed names in assets/source
                fn = os.path.join(sheets_dir, SHEET_FILES[s])
            sheets[s] = np.asarray(Image.open(fn).convert("RGBA" if spec.get("method") == "alpha" else "RGB"))
        scale = 1.6 if s == "sheet1" else 1.0  # sheet1 is drawn ~1.6x larger
        CURRENT.clear(); CURRENT["kind"] = "head" if name.startswith("head") else ("prop" if name.startswith("prop") else "pose")
        CURRENT["clean"] = spec.get("clean", False)
        EXCLUDE[:] = spec.get("exclude", [])
        EXCLUDE_POLY[:] = spec.get("exclude_poly", [])
        method = {"ml": cut_ml, "alpha": cut_alpha, "outline": cut}[spec.get("method", "ml")]
        rgba = method(sheets[s], spec["box"], spec.get("holes", []), scale)
        Image.fromarray(rgba).save(os.path.join(out_dir, name + ".png"))
        print(name, rgba.shape[1], "x", rgba.shape[0], "coverage %.2f" % (rgba[..., 3].mean() / 255))


if __name__ == "__main__":
    main()
