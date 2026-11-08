"""Turn cut-out PNG parts into flat, palette-classed, editable SVGs.

Pipeline per part:
  upscale -> edge-preserving smooth -> snap every pixel to the character
  palette (CIELAB nearest) -> soft-vote smoothing of the label map (removes
  the stone grain, keeps the shapes) -> vtracer (cutout mode) -> rewrite each
  path's fill to a CSS class (.ink, .stone, .toga ...)

Recolouring the whole character is then a matter of editing the <style>.

usage: python3 tools/vectorize.py <cut_dir> <out_dir> [name ...]
"""
import os, re, sys, glob, json
import numpy as np
import cv2
import vtracer
from PIL import Image

# role -> hex.  Sampled from the reference sheets (see README).
PALETTE = {
    "ink":      "#0B0607",  # outline + hard cel shadows
    "stone":    "#988883",  # skin base (stone gray)
    "stone-mid": "#7F706B",  # soft shading on skin
    "stone-sh": "#483B3A",  # deep skin shadow
    "stone-hi": "#B8A79E",  # rim light / highlight
    "toga":     "#4A0A10",  # toga + laurel base red
    "toga-sh":  "#260A0C",  # toga fold shadow
    "toga-hi":  "#741219",  # laurel / lit folds
}
# Extra roles used only by props (prop_*). Props also use the character roles above.
PROP_EXTRA = {
    "paper":      "#E2D8D3",  # whiteboard, pages, cup, labels
    "paper-sh":   "#BFB1AA",
    "gear":       "#2B292A",  # black rubber / plastic (weights, phone, bag)
    "gear-dk":    "#161415",
    "gear-hi":    "#4A4648",
    "metal":      "#9A9799",  # chrome bars, clips
    "metal-hi":   "#D0CFD0",
    "tan":        "#C69E79",  # scroll, cup sleeve, wood
    "tan-sh":     "#8E6A4C",
    "leather":    "#684B3B",  # wallet, frames
    "leather-sh": "#3A2620",
}
ALL_ROLES = {**PALETTE, **PROP_EXTRA}
KEY = (0, 255, 0)  # transparent pixels are keyed to this and dropped afterwards


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


class Pal:
    def __init__(self, roles):
        self.roles = list(roles)
        self.hex = dict(roles)
        self.rgb = np.array([hex2rgb(roles[r]) for r in self.roles], np.uint8)
        self.lab = cv2.cvtColor(self.rgb.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
        lum = self.rgb.astype(float) @ [0.299, 0.587, 0.114]
        # draw order: lighter fills first, ink last, so seams read as linework
        self.order = {r: (999 if r == "ink" else -lum[i]) for i, r in enumerate(self.roles)}



DROP = set(filter(None, os.environ.get("VEC_DROP", "stone-mid").split(",")))
CHAR_PAL = Pal({k: v for k, v in PALETTE.items() if k not in DROP})
PROP_PAL = Pal({k: v for k, v in ALL_ROLES.items() if k not in DROP})
# back-compat names
ROLES, PAL_RGB, PAL_LAB = CHAR_PAL.roles, CHAR_PAL.rgb, CHAR_PAL.lab


MIN_AREA = float(os.environ.get("VEC_MIN_AREA", "0.0015"))  # fraction of the figure area
MIN_INK = int(os.environ.get("VEC_MIN_INK", "60"))           # px; keep eyes/lines, drop crumbs
PROTECT = {"stone-hi", "paper", "metal-hi", "toga-hi"}          # small bright features: eye whites, teeth, glints


def merge_specks(lbl, a, roles):
    """Remove texture blotches: every colour patch smaller than MIN_AREA of the figure
    (ink: smaller than MIN_INK px) is absorbed into the nearest surviving colour.
    This is what keeps the painted stone/grunge texture from turning into camo."""
    from scipy import ndimage as ndi
    area = max(1, a.sum())
    keep = np.zeros_like(a)
    ink = roles.index("ink")
    for i in range(len(roles)):
        m = (lbl == i) & a
        if not m.any():
            continue
        lab, k = ndi.label(m)
        sizes = ndi.sum(m, lab, range(1, k + 1))
        thr = MIN_INK if (i == ink or roles[i] in PROTECT) else MIN_AREA * area
        big = np.zeros(k + 1, bool)
        big[1:] = sizes >= thr
        keep |= big[lab]
    unknown = a & ~keep
    if unknown.any() and keep.any():
        _, (iy, ix) = ndi.distance_transform_edt(~keep, return_indices=True)
        lbl = lbl.copy()
        lbl[unknown] = lbl[iy[unknown], ix[unknown]]
    return lbl


def adaptive_pal(im, name, k=6):
    """Per-prop palette: k-means on the prop's own (flattened) colours.  Roles are named
    <prop>-c0.. so each prop is recolourable on its own; near-black clusters become .ink."""
    a = im[..., 3] > 128
    rgb = flatten(np.ascontiguousarray(im[..., :3]), 1.0)
    px = rgb[a].reshape(-1, 1, 3)
    lab = cv2.cvtColor(px, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    _, lb, cen = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    cols = cv2.cvtColor(cen.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    order = np.argsort(-cols.astype(float) @ [0.299, 0.587, 0.114])
    roles, base = {}, name.replace("prop_", "")
    for j, i in enumerate(order):
        c = cols[i]
        if c.max() < 40 and "ink" not in roles:
            roles["ink"] = PALETTE["ink"]
        else:
            roles[f"{base}-c{j}"] = "#%02X%02X%02X" % tuple(int(v) for v in c)
    roles.setdefault("ink", PALETTE["ink"])
    return Pal(roles)


def flatten(rgb, scale):
    """Flatten painted texture/grain into clean colour areas while keeping edges
    (mean-shift + bilateral).  This is what stops the stone grunge reading as camo."""
    rgb = np.ascontiguousarray(rgb)
    sp = int(max(4, float(os.environ.get("VEC_FLAT_SP", "2.2")) * scale))
    rgb = cv2.pyrMeanShiftFiltering(rgb, sp, float(os.environ.get("VEC_FLAT_SR", "16")), maxLevel=1)
    return cv2.bilateralFilter(rgb, 9, 30, 5)


def quantize(rgb, alpha, scale, pal=CHAR_PAL):
    ROLES, PAL_RGB, PAL_LAB = pal.roles, pal.rgb, pal.lab
    rgb = flatten(rgb, scale)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    d = ((lab[:, :, None, :] - PAL_LAB[None, None]) ** 2).sum(-1)
    # bias: keep the (thin) outline and laurel highlight from being swallowed
    d[..., ROLES.index("ink")] *= 0.85
    lbl = d.argmin(-1)
    # soft vote: blur each one-hot class plane and take the argmax
    sigma = max(1.0, 0.9 * scale)
    votes = np.stack([cv2.GaussianBlur((lbl == i).astype(np.float32), (0, 0), sigma) for i in range(len(ROLES))], -1)
    votes[..., ROLES.index("ink")] *= 1.15
    lbl = votes.argmax(-1)
    a = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), sigma) > 127
    lbl = merge_specks(lbl, a, ROLES)
    out = PAL_RGB[lbl]
    out[~a] = KEY
    return out, a


def trace(img):
    h, w = img.shape[:2]
    rgba = np.dstack([img, np.full((h, w), 255, np.uint8)])
    px = [tuple(int(v) for v in p) for p in rgba.reshape(-1, 4)]
    return vtracer.convert_pixels_to_svg(
        px, size=(w, h), colormode="color", hierarchical="cutout", mode="spline",
        filter_speckle=6, color_precision=8, layer_difference=4, corner_threshold=55,
        length_threshold=3.5, max_iterations=10, splice_threshold=45, path_precision=1)


def classify(svg, w, h, name, pal=CHAR_PAL):
    ROLES, PAL_RGB, PALETTE = pal.roles, pal.rgb, pal.hex
    rev = {PALETTE[r].lower(): r for r in ROLES}
    key_hex = "#%02x%02x%02x" % KEY
    paths = []
    for m in re.finditer(r'<path d="([^"]+)" fill="(#[0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?/>', svg):
        d, fill, tx, ty = m.groups()
        fill = fill.lower()
        kr, kg, kb = hex2rgb(fill)
        if kg > 180 and kr < 90 and kb < 90:  # keyed transparency (vtracer may shift it a little)
            continue
        role = rev.get(fill)
        if role is None:  # nearest palette role (vtracer can average colours on edges)
            c = np.array(hex2rgb(fill))
            role = ROLES[int(((PAL_RGB.astype(int) - c) ** 2).sum(1).argmin())]
        t = f' transform="translate({tx},{ty})"' if tx else ""
        paths.append((role, f'<path class="{role}" d="{d}"{t}/>'))
    paths.sort(key=lambda p: pal.order[p[0]])
    used = sorted({r for r, _ in paths}, key=lambda r: pal.order[r])
    style = "\n".join(f"  .{r}{{fill:{PALETTE[r]};stroke:{PALETTE[r]}}}" for r in used)
    body = "\n".join(p for _, p in paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" data-part="{name}">\n'
            f'<style>\n{style}\n  path{{stroke-width:0.8;stroke-linejoin:round}}\n</style>\n'
            f'<g id="{name}">\n{body}\n</g>\n</svg>\n'), len(paths)


def main():
    cut_dir, out_dir = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or [os.path.basename(f)[:-4] for f in sorted(glob.glob(os.path.join(cut_dir, "*.png")))]
    os.makedirs(out_dir, exist_ok=True)
    meta = {}
    for name in names:
        im = np.asarray(Image.open(os.path.join(cut_dir, name + ".png")).convert("RGBA"))
        is_prop = name.startswith("prop")
        pal = adaptive_pal(im, name) if is_prop else CHAR_PAL
        if is_prop:  # props: longest side 900 px
            scale = 900 / max(im.shape[:2])
        else:
            scale = (1400 if name.startswith("pose") else 720) / im.shape[0]
        W, H = int(round(im.shape[1] * scale)), int(round(im.shape[0] * scale))
        rgb = cv2.resize(np.ascontiguousarray(im[..., :3]), (W, H), interpolation=cv2.INTER_CUBIC)
        al = cv2.resize(np.ascontiguousarray(im[..., 3]), (W, H), interpolation=cv2.INTER_LINEAR)
        q, a = quantize(rgb, al, scale, pal)
        svg, n = classify(trace(q), W, H, name, pal)
        open(os.path.join(out_dir, name + ".svg"), "w").write(svg)
        Image.fromarray(np.dstack([np.where(a[..., None], q, 0), (a * 255).astype(np.uint8)]).astype(np.uint8)).save(
            os.path.join(out_dir, name + ".quant.png"))
        ys, xs = np.nonzero(a)
        meta[name] = {"w": W, "h": H, "paths": n, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
        print(name, W, "x", H, n, "paths", os.path.getsize(os.path.join(out_dir, name + ".svg")) // 1024, "KB")
    json.dump(meta, open(os.path.join(out_dir, "parts.meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
