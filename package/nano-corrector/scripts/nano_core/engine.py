"""sRGB color math and smooth neutral-wall detection."""
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
