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
ROLES = list(PALETTE)
KEY = (0, 255, 0)  # transparent pixels are keyed to this and dropped afterwards


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


PAL_RGB = np.array([hex2rgb(PALETTE[r]) for r in ROLES], np.uint8)
PAL_LAB = cv2.cvtColor(PAL_RGB.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def quantize(rgb, alpha, scale):
    rgb = cv2.bilateralFilter(np.ascontiguousarray(rgb), 9, 35, 5)
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


def classify(svg, w, h, name):
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
    # draw order: lighter fills first, ink last, so seams read as linework
    order = {r: i for i, r in enumerate(["stone-hi", "stone", "stone-mid", "stone-sh", "toga-hi", "toga", "toga-sh", "ink"])}
    paths.sort(key=lambda p: order[p[0]])
    style = "\n".join(f"  .{r}{{fill:{PALETTE[r]};stroke:{PALETTE[r]}}}" for r in ROLES)
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
        target = 1400 if name.startswith("pose") else 720
        scale = target / im.shape[0]
        W, H = int(round(im.shape[1] * scale)), target
        rgb = cv2.resize(np.ascontiguousarray(im[..., :3]), (W, H), interpolation=cv2.INTER_CUBIC)
        al = cv2.resize(np.ascontiguousarray(im[..., 3]), (W, H), interpolation=cv2.INTER_LINEAR)
        q, a = quantize(rgb, al, scale)
        svg, n = classify(trace(q), W, H, name)
        open(os.path.join(out_dir, name + ".svg"), "w").write(svg)
        Image.fromarray(np.dstack([np.where(a[..., None], q, 0), (a * 255).astype(np.uint8)]).astype(np.uint8)).save(
            os.path.join(out_dir, name + ".quant.png"))
        ys, xs = np.nonzero(a)
        meta[name] = {"w": W, "h": H, "paths": n, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}
        print(name, W, "x", H, n, "paths", os.path.getsize(os.path.join(out_dir, name + ".svg")) // 1024, "KB")
    json.dump(meta, open(os.path.join(out_dir, "parts.meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
