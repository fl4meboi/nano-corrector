"""Saved-file measurements and paginated review sheets, independent of batch names."""
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw
from . import engine as E
from .io import SRGB_BYTES

DEFAULT_PATCHES = [
    {'name': 'upper_left', 'box': [.05, .10, .09, .16]},
    {'name': 'upper_right', 'box': [.90, .10, .94, .16]},
    {'name': 'middle_left', 'box': [.05, .45, .09, .51]},
    {'name': 'middle_right', 'box': [.90, .45, .94, .51]},
]


def validate_patches(patches):
    if not isinstance(patches, list) or not patches:
        raise ValueError('Patches must be a nonempty JSON list of {name, box}')
    names = set()
    for p in patches:
        if not isinstance(p, dict):
            raise ValueError('Each patch must be an object with name and box')
        if not isinstance(p.get('name'), str) or p['name'] in names:
            raise ValueError('Each patch needs a unique string name')
        names.add(p['name'])
        box = p.get('box', [])
        if len(box) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in box):
            raise ValueError('Patch box must be [left, top, right, bottom] fractions')
        x0, y0, x1, y1 = box
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError('Patch coordinates must be ordered fractions in [0,1]')
    return patches


def patches_of(rgb, patches):
    h, w = rgb.shape[:2]
    result = {}
    for p in patches:
        x0, y0, x1, y1 = p['box']
        crop = rgb[int(y0*h):max(int(y0*h)+1, int(y1*h)), int(x0*w):max(int(x0*w)+1, int(x1*w))]
        lab = cv2.cvtColor(crop.astype(np.float32)/255, cv2.COLOR_RGB2Lab).reshape(-1, 3)
        neutral = (lab[:, 0] >= 70) & (np.hypot(lab[:, 1], lab[:, 2]) < 18)
        med = np.median(lab, axis=0)
        spread = float(np.median(np.linalg.norm(lab[:, 1:]-med[1:], axis=1)))
        result[p['name']] = {'lab': med.tolist(), 'rgb': np.median(crop.reshape(-1, 3), axis=0).tolist(),
                             'bright_neutral_fraction': float(neutral.mean()),
                             'plausible_wall': bool(neutral.mean() >= .9 and spread < 2),
                             'chroma_spread': spread}
    return result


def protected_check(before, after):
    if before.shape != after.shape:
        raise ValueError('Saved output dimensions differ from oriented input')
    count = 0
    for y in range(0, len(before), 256):
        a, b = before[y:y+256], after[y:y+256]
        lab = cv2.cvtColor(a.astype(np.float32)/255, cv2.COLOR_RGB2Lab)
        mask = (lab[..., 0] <= 60) | (np.hypot(lab[..., 1], lab[..., 2]) >= 12)
        if not np.array_equal(a[mask], b[mask]):
            raise ValueError('Saved master changed protected dark/saturated pixels')
        count += int(mask.sum())
    return count


def thumbnail(rgb, patches=None):
    im = Image.fromarray(rgb)
    im.thumbnail((300, 400))
    if patches:
        d = ImageDraw.Draw(im)
        for i, p in enumerate(patches):
            x0, y0, x1, y1 = p['box']
            box = (x0*im.width, y0*im.height, x1*im.width, y1*im.height)
            d.rectangle(box, outline='#00cfff', width=2)
            d.text((box[0], max(0, box[1]-12)), str(i+1), fill='#0066aa', stroke_width=1, stroke_fill='white')
    return im


def sheets(items, directory, prefix='before-after'):
    # Every item is shown, in pages of six pairs; no assumptions about AC-01 names/count.
    files = []
    for start in range(0, len(items), 6):
        page = items[start:start+6]
        cols = min(2, len(page)); rows = math.ceil(len(page)/cols)
        sheet = Image.new('RGB', (cols*620, rows*436), '#242424')
        d = ImageDraw.Draw(sheet)
        for k, (name, before, after) in enumerate(page):
            x = (k % cols)*620; y = (k // cols)*436
            for j, im in enumerate((before, after)):
                sheet.paste(im, (x+j*310, y+30))
                d.text((x+j*310+4, y+8), name[:35]+(' BEFORE' if j==0 else ' AFTER'), fill='white')
        filename = f'{prefix}-{start//6+1:02d}.png'
        sheet.save(directory/filename, icc_profile=SRGB_BYTES)
        files.append(filename)
    return files


def summarize(rows, reference_patches, patch_defs):
    summary = {}
    for key, label in [('anchor_lab_before', 'before'), ('anchor_lab_after', 'after')]:
        vals = [np.array(r[key]) for r in rows if r.get(key) is not None]
        summary[label+'_wall_tint_spread_ab'] = max((float(np.linalg.norm(a[1:]-b[1:])) for a in vals for b in vals), default=0.)
        summary[label+'_wall_lightness_range'] = float(np.ptp([v[0] for v in vals])) if vals else None
    patches = {}
    for p in patch_defs:
        name = p['name']; target = reference_patches[name]
        valid = [r for r in rows if not r['reference'] and target['plausible_wall'] and r['patches_before'][name]['plausible_wall']]
        q = {'images_measured': len(valid)}
        for when in ['before', 'after']:
            vals = [np.array(r['patches_'+when][name]['lab']) for r in valid]
            ref = np.array(target['lab'])
            q[when+'_mean_tint_distance_to_reference'] = float(np.mean([np.linalg.norm(v[1:]-ref[1:]) for v in vals])) if vals else None
            q[when+'_mean_lightness_distance_to_reference'] = float(np.mean([abs(v[0]-ref[0]) for v in vals])) if vals else None
        patches[name] = q
    summary['fixed_patches'] = patches
    summary['automatic_acceptance'] = False
    summary['review_required'] = 'Inspect sample boxes for actual wall, subject edges, reference, and before/after sheets. Patch validity is heuristic; samples may overlap the fitting area. These are consistency checks, not calibrated color accuracy.'
    return summary
