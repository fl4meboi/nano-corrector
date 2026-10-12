"""Core math. Pure functions on numpy arrays, no file I/O, so the same code can back a CLI,
a skill, or a hosted action.

Idea: every image in a set shares a neutral surface (studio wall, floor, paper). Measure that
surface's color in each image, pick one set-wide baseline, and apply per-channel gains in linear
light so each image's surface lands on the baseline. Gain-only, so hue relationships between
other colors are preserved and nothing clips.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy import ndimage as ndi

WORK_MAX_SIDE = 800  # anchor detection runs on a downscaled copy
CLEAN_RADIUS = 1.0   # a*b* units: images this close to the cleanest one define the baseline


# --------------------------------------------------------------------------- color helpers
def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


def lab_of_linear(lin_rgb) -> np.ndarray:
    """CIELAB (D65) of a single linear-light RGB triplet."""
    px = linear_to_srgb(np.asarray(lin_rgb, np.float32).reshape(1, 1, 3))
    return cv2.cvtColor(px, cv2.COLOR_RGB2Lab).reshape(3)


def delta_ab(lab1, lab2) -> float:
    """Chromatic difference only (ignores lightness): what a white-balance error looks like."""
    return float(np.hypot(lab1[1] - lab2[1], lab1[2] - lab2[2]))


# --------------------------------------------------------------------------- anchor detection
@dataclass
class Anchor:
    lin_rgb: np.ndarray            # median linear-light RGB of the neutral surface
    lab: np.ndarray                # same color in CIELAB
    area_frac: float               # share of the image the surface covers
    spread: float                  # MAD of a*/b* inside the surface (lower = cleaner)
    reliable: bool
    note: str = ""
    mask_preview: np.ndarray | None = field(default=None, repr=False)


def find_neutral_anchor(rgb_u8: np.ndarray, want_mask: bool = False) -> Anchor:
    """Locate the dominant bright, smooth, near-neutral surface and measure its color.

    Adaptive: it finds the peak of the (a*, b*) histogram among bright smooth pixels, so a
    wall that already drifted pink is still found, and cream trousers (a different chroma
    cluster) are excluded.
    """
    h, w = rgb_u8.shape[:2]
    s = min(1.0, WORK_MAX_SIDE / max(h, w))
    small = cv2.resize(rgb_u8, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    srgb = small.astype(np.float32) / 255.0
    lab = cv2.cvtColor(srgb, cv2.COLOR_RGB2Lab)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)

    grad = np.hypot(ndi.sobel(L, 0), ndi.sobel(L, 1))
    grad = ndi.uniform_filter(grad, 7)
    cand = (L >= 70) & (grad < 3.5) & (chroma < 18)
    cand = ndi.binary_opening(cand, iterations=2)
    if cand.sum() < 500:
        return Anchor(np.ones(3, np.float32), np.array([100, 0, 0], np.float32), 0.0, 99.0, False,
                      "no bright smooth surface found")

    # peak of the a*/b* histogram, 0.5-unit bins
    ab = np.stack([a[cand], b[cand]], 1)
    edges = np.arange(-18, 18.5, 0.5)
    hist, _, _ = np.histogram2d(ab[:, 0], ab[:, 1], bins=[edges, edges])
    hist = ndi.gaussian_filter(hist, 1.5)
    ia, ib = np.unravel_index(np.argmax(hist), hist.shape)
    pa, pb = edges[ia] + 0.25, edges[ib] + 0.25

    near = np.hypot(a - pa, b - pb) < 2.5
    mask = ndi.binary_opening(cand & near, iterations=2)
    area = float(mask.mean())
    if mask.sum() < 500:
        return Anchor(np.ones(3, np.float32), np.array([100, 0, 0], np.float32), area, 99.0, False,
                      "neutral cluster too small")

    lin = srgb_to_linear(srgb)
    lin_med = np.median(lin[mask], axis=0)
    lab_med = np.array([np.median(L[mask]), np.median(a[mask]), np.median(b[mask])], np.float32)
    spread = float(np.median(np.hypot(a[mask] - lab_med[1], b[mask] - lab_med[2])))
    reliable = area >= 0.03 and spread < 1.5
    note = "" if reliable else f"weak anchor (area {area:.1%}, spread {spread:.2f})"
    return Anchor(lin_med, lab_med, area, spread, reliable, note, mask if want_mask else None)


# --------------------------------------------------------------------------- baseline + gains
def chromaticity(lin_rgb) -> np.ndarray:
    v = np.asarray(lin_rgb, np.float64)
    return v / v.sum()


def choose_baseline(anchors: list[Anchor], strategy: str = "neutral-most", ref_index: int | None = None):
    """Return (target_chromaticity, description, group_indices). Only reliable anchors vote.

    neutral-most: the cleanest image (lowest a*b* chroma) and its near-twins define "right".
                  Drift only ever adds cast, so the cleanest images are the best witnesses; a
                  majority vote would adopt the drift when most of the batch has it.
    consensus:    median of all reliable anchors.
    reference:    use anchors[ref_index].
    """
    ok = [i for i, an in enumerate(anchors) if an.reliable]
    if not ok:
        raise ValueError("no image has a reliable neutral anchor; supply --baseline-hex or a reference")
    if strategy == "reference":
        refs = [ref_index] if isinstance(ref_index, int) else list(ref_index or [])
        refs = [i for i in refs if anchors[i].reliable]
        if not refs:
            raise ValueError("reference image(s) have no reliable neutral anchor")
        c = np.median([chromaticity(anchors[i].lin_rgb) for i in refs], axis=0)
        return c / c.sum(), f"reference image(s) #{', #'.join(map(str, refs))}", refs
    if strategy == "consensus":
        c = np.median([chromaticity(anchors[i].lin_rgb) for i in ok], axis=0)
        return c / c.sum(), f"median of {len(ok)} images", ok
    # neutral-most: the cleanest image, plus any image within CLEAN_RADIUS a*b* units of it
    cast = {i: float(np.hypot(anchors[i].lab[1], anchors[i].lab[2])) for i in ok}
    best = min(ok, key=cast.get)
    pick = [i for i in ok if delta_ab(anchors[i].lab, anchors[best].lab) <= CLEAN_RADIUS]
    c = np.median([chromaticity(anchors[i].lin_rgb) for i in pick], axis=0)
    return (c / c.sum(),
            f"cleanest image + {len(pick) - 1} within {CLEAN_RADIUS} a*b* (#{', #'.join(map(str, pick))} of {len(ok)})",
            pick)


def gains_for(anchor_lin_rgb, target_chromaticity, strength: float = 1.0) -> np.ndarray:
    """Per-channel linear-light gains moving the anchor onto the target chromaticity.

    Scaled so the anchor keeps its luminance: the image gets no brighter or darker overall,
    which matters because Lab a*/b* of saturated colors (a red hat) move if lightness moves.
    The cost is that near-white pixels can clip on the boosted channel; apply_gains reports it.
    """
    w = np.asarray(anchor_lin_rgb, np.float64)
    g = np.asarray(target_chromaticity, np.float64) / np.maximum(w, 1e-6)
    g = g ** float(np.clip(strength, 0.0, 1.0))
    y = np.array([0.2126, 0.7152, 0.0722])
    g /= float((y * w * g).sum() / (y * w).sum())
    return g.astype(np.float32)


def apply_gains(rgb: np.ndarray, gains: np.ndarray, return_clipped: bool = False):
    """rgb: uint8 or uint16 HxWx3. Returns float32 sRGB in [0,1] (caller quantizes once).

    With return_clipped=True also returns the fraction of pixels pushed past 1.0 in any channel.
    """
    scale = 255.0 if rgb.dtype == np.uint8 else 65535.0
    lin = srgb_to_linear(rgb.astype(np.float32) / scale)
    lin *= gains.reshape(1, 1, 3)
    out = linear_to_srgb(lin)
    if return_clipped:
        return out, float((lin.max(axis=2) > 1.0005).mean())
    return out


# --------------------------------------------------------------------------- tonal correction
# Generation drift is a tone curve, not a single gain: shadows pick up far more red/blue relative
# to green than highlights do (measured 20-28% in deep shadows vs 2-3% at the wall). So we estimate,
# per lightness bin, the median log(R/G) and log(B/G) of low-chroma pixels, compare to the
# reference images' same bins, and build smooth per-channel gains over luminance. This is the same
# object as a Photoshop RGB curves layer, computed in linear light at float precision.
COND_BINS = [(10, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 80),
             (80, 88), (88, 94), (94, 101)]  # CIELAB L*
COND_MAX_CHROMA = 20.0   # excludes the saturated hat, skin, suede bag
COND_MIN_PIXELS = 3000
MAX_LOG_GAIN = 0.35      # ~ +/-35% per channel
SMOOTH_SIGMA = 0.8       # in bins


def cond_profile(rgb_u8: np.ndarray) -> list:
    """Per lightness bin: median log(R/G), log(B/G), linear luminance, pixel count (or None)."""
    h, w = rgb_u8.shape[:2]
    s = min(1.0, WORK_MAX_SIDE / max(h, w))
    small = cv2.resize(rgb_u8, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    srgb = small.astype(np.float32) / 255.0
    lab = cv2.cvtColor(srgb, cv2.COLOR_RGB2Lab)
    L = lab[..., 0]
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    lin = np.maximum(srgb_to_linear(srgb), 1e-4)
    r = np.log(lin[..., 0] / lin[..., 1])
    q = np.log(lin[..., 2] / lin[..., 1])
    y = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    out = []
    for lo, hi in COND_BINS:
        m = (L >= lo) & (L < hi) & (chroma < COND_MAX_CHROMA)
        if m.sum() < COND_MIN_PIXELS:
            out.append(None)
            continue
        out.append({"r": float(np.median(r[m])), "q": float(np.median(q[m])),
                    "y": float(np.median(y[m])), "n": int(m.sum())})
    return out


def cond_reference(profiles: list[list]) -> list:
    """Mean over reference images, per bin (None where no reference has the bin)."""
    ref = []
    for k in range(len(COND_BINS)):
        got = [p[k] for p in profiles if p[k] is not None]
        ref.append({"r": float(np.mean([g["r"] for g in got])), "q": float(np.mean([g["q"] for g in got]))}
                   if got else None)
    return ref


def cond_curve(profile: list, ref: list, strength: float = 1.0):
    """Control points (luminance Y, gains Nx3) taking this image's tone-by-tone color to the
    reference's. Gains are luminance-preserving at every control point (green is the pivot, so a
    pull-down of red/blue shows up as a green lift, as in a Photoshop Green-curve push)."""
    idx = [k for k, (p, r) in enumerate(zip(profile, ref)) if p is not None and r is not None]
    if len(idx) < 2:
        return None
    dr = np.array([ref[k]["r"] - profile[k]["r"] for k in idx])
    dq = np.array([ref[k]["q"] - profile[k]["q"] for k in idx])
    if len(idx) > 2:
        dr = ndi.gaussian_filter1d(dr, SMOOTH_SIGMA, mode="nearest")
        dq = ndi.gaussian_filter1d(dq, SMOOTH_SIGMA, mode="nearest")
    st = float(np.clip(strength, 0.0, 1.0))
    dr = np.clip(dr * st, -MAX_LOG_GAIN, MAX_LOG_GAIN)
    dq = np.clip(dq * st, -MAX_LOG_GAIN, MAX_LOG_GAIN)
    gains = np.stack([np.exp(dr), np.ones_like(dr), np.exp(dq)], axis=1)
    gains /= (gains @ np.array([0.2126, 0.7152, 0.0722]))[:, None]
    ys = np.array([profile[k]["y"] for k in idx], np.float32)
    order = np.argsort(ys)
    return ys[order], gains[order].astype(np.float32)


def apply_curve(rgb: np.ndarray, ys: np.ndarray, gs: np.ndarray, return_clipped: bool = False):
    """Luminance-dependent gains: each pixel gets the gains interpolated (in log Y) at its own
    linear luminance, held constant beyond the first and last control point."""
    scale = 255.0 if rgb.dtype == np.uint8 else 65535.0
    out = np.empty(rgb.shape, np.float32)
    ly = np.log(ys)
    clipped = 0
    wts = np.array([0.2126, 0.7152, 0.0722], np.float32)
    step = max(1, (8_000_000 // max(1, rgb.shape[1])))
    for r0 in range(0, rgb.shape[0], step):
        lin = srgb_to_linear(rgb[r0:r0 + step].astype(np.float32) / scale)
        y = np.log(np.maximum(lin @ wts, 1e-4))
        for c in range(3):
            lin[..., c] *= np.interp(y, ly, gs[:, c]).astype(np.float32)
        clipped += int((lin.max(axis=2) > 1.0005).sum())
        out[r0:r0 + step] = linear_to_srgb(lin)
    if return_clipped:
        return out, clipped / float(rgb.shape[0] * rgb.shape[1])
    return out


def protect_highlights(ys: np.ndarray, gs: np.ndarray):
    """Keep fitted controls below L*=65; fade to identity by L*=78.

    Opt-in for sets whose bright neutrals already agree. This prevents light garments
    from being recolored by statistical differences in wall/garment proportions.
    It deliberately leaves existing highlight white balance unchanged.
    """
    keep = ys < ((65.0 + 16.0) / 116.0) ** 3
    points = np.r_[ys[keep], ((78.0 + 16.0) / 116.0) ** 3, 1.0]
    gains = np.vstack([gs[keep], np.ones((2, 3))])
    return points.astype(np.float32), gains.astype(np.float32)
