"""Background-first matching for studio images with exposed neutral side walls.

Fits smooth Lab tint fields to the two wall margins, then corrects bright,
low-chroma pixels. Not semantic segmentation: pale neutral objects may change.
"""
import cv2
import numpy as np
from . import engine as E


def basis(x, y):
    return np.stack([np.ones_like(x), x, y, x*x, x*y, y*y], axis=-1)


def fit_background(rgb):
    anchor = E.find_neutral_anchor(rgb, want_mask=True)
    if not anchor.reliable:
        raise ValueError('No reliable neutral wall; background match requires review')
    h, w = anchor.mask_preview.shape
    small = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small.astype(np.float32)/255, cv2.COLOR_RGB2Lab)
    yy, xx = np.mgrid[:h, :w].astype(np.float32)
    design = basis(xx/(w-1)*2-1, yy/(h-1)*2-1)
    mask = anchor.mask_preview & (yy < h*.8) & ((xx < w*.22) | (xx > w*.82))
    if any(np.count_nonzero(mask & side) < 500 for side in [xx < w*.22, xx > w*.82]):
        raise ValueError('Insufficient exposed neutral wall on both sides')
    coefficients = []
    for c in [1, 2]:
        A, v = design[mask], lab[..., c][mask]
        keep = np.ones(len(v), bool)
        for _ in range(4):
            co = np.linalg.lstsq(A[keep], v[keep], rcond=None)[0]
            error = v - A@co
            keep = np.abs(error) < max(.4, 3*np.median(np.abs(error-np.median(error))))
        coefficients.append(co)
    return anchor, np.array(coefficients, np.float32), mask


def apply_background(rgb, anchor_lab, coefficients, target_lab, target_coefficients=None):
    """Match wall tint and median lightness, retaining local shading.

    Smooth protection: no correction below L*=60 or above C*=12; full correction
    above L*=80 and below C*=5. Chroma shifts capped at 5 Lab units per component.
    Unaffected pixels bypass the Lab round trip and remain bit-identical.
    Returns (uint8 RGB, fraction of pixels whose adjustment was gamut-limited).
    """
    h, w = rgb.shape[:2]
    out = np.empty_like(rgb)
    limited = 0
    for start in range(0, h, 256):
        block = rgb[start:start+256]
        lab = cv2.cvtColor(block.astype(np.float32)/255, cv2.COLOR_RGB2Lab)
        yy, xx = np.mgrid[start:start+len(block), :w].astype(np.float32)
        design = basis(xx/(w-1)*2-1, yy/(h-1)*2-1)
        chroma = np.hypot(lab[...,1], lab[...,2])
        t = np.clip((lab[...,0]-60)/20, 0, 1); t = t*t*(3-2*t)
        s = np.clip((12-chroma)/7, 0, 1); s = s*s*(3-2*s)
        weight = t*s
        # Roll correction off above the wall anchor so existing sunlit whites
        # retain headroom instead of being pushed into clipping.
        light_weight = weight*np.clip((100-lab[...,0])/max(1.,100-anchor_lab[0]),0,1)
        weight *= np.clip((100-lab[...,0])/2,0,1)
        lab[...,0] += light_weight*(target_lab[0]-anchor_lab[0])
        for c in [1,2]:
            target = target_lab[c] if target_coefficients is None else design@target_coefficients[c-1]
            delta = np.clip(target-design@coefficients[c-1], -5, 5)
            lab[...,c] += weight*delta
        # Lab->XYZ->linear sRGB, without hidden clipping in cvtColor.
        fy = (lab[...,0]+16)/116
        f = np.stack([fy+lab[...,1]/500, fy, fy-lab[...,2]/200], -1)
        xyz = np.where(f > 6/29, f**3, 3*(6/29)**2*(f-4/29))
        xyz *= np.array([.95047, 1., 1.08883], np.float32)
        lin = xyz @ np.array([[3.2404542,-1.5371385,-.4985314],[-.969266,1.8760108,.041556],[.0556434,-.2040259,1.0572252]],np.float32).T
        original_lin = E.srgb_to_linear(block.astype(np.float32)/255)
        delta = lin-original_lin
        # Reduce the adjustment uniformly across RGB at gamut boundaries,
        # rather than clipping channels and losing highlight color/detail.
        bounds = np.where(delta>0, (1-original_lin)/np.maximum(delta,1e-12),
                          np.where(delta<0, original_lin/np.maximum(-delta,1e-12), 1.))
        amount = np.clip(bounds.min(-1),0,1)
        limited += int(np.count_nonzero((weight>0) & (amount<.999)))
        lin = original_lin + delta*amount[...,None]
        result = np.rint(E.linear_to_srgb(lin)*255).astype(np.uint8)
        result[weight==0] = block[weight==0]
        out[start:start+len(block)] = result
    return out, limited/(h*w)
