#!/usr/bin/env python3
"""Portable local studio background matching, with mandatory reference and saved-file QA."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from nano_core import engine as E
from nano_core.background import fit_background, apply_background
from nano_core.io import inputs, load, save_png, save_jpeg
from nano_core.qa import DEFAULT_PATCHES, validate_patches, patches_of, protected_check, thumbnail, sheets, summarize


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs', nargs='+', help='JPEG/PNG files, folders (nonrecursive), or quoted globs')
    ap.add_argument('--reference', type=Path, required=True, help='Trusted studio image; may be outside the batch')
    ap.add_argument('--out', type=Path, help='New output directory; existing directories are refused')
    ap.add_argument('--dry-run', action='store_true', help='Validate/read/fit all inputs; write nothing')
    ap.add_argument('--jpeg', action='store_true', help='Also export smaller JPEGs; lossless PNG masters always retained')
    ap.add_argument('--jpeg-quality', type=int, default=95, help='JPEG quality 1–100 (default 95), 4:4:4 sampling')
    ap.add_argument('--patches', type=Path, help='JSON list of named normalized wall rectangles; see references/quality-checks.md')
    ap.add_argument('--focus', nargs='+', default=[], help='Image stems for an additional comparison sheet')
    return ap


def main(argv=None):
    ap = parser(); args = ap.parse_args(argv)
    if not 1 <= args.jpeg_quality <= 100:
        ap.error('--jpeg-quality must be 1–100')
    if not args.dry_run and args.out is None:
        ap.error('--out is required unless --dry-run')
    paths = inputs(args.inputs); refpath = args.reference.expanduser().resolve()
    outdir = args.out.expanduser().resolve() if args.out else None
    if outdir and outdir.exists():
        raise ValueError('Output directory already exists; choose a new versioned folder')
    missing = set(args.focus)-{p.stem for p in paths}
    if missing:
        raise ValueError('Focus names absent from batch: '+', '.join(sorted(missing)))
    patch_defs = validate_patches(json.loads(args.patches.read_text()) if args.patches else DEFAULT_PATCHES)
    ref, refmeta = load(refpath)
    refanchor, refcoeff, _ = fit_background(ref)
    target = refanchor.lab
    refpatch = patches_of(ref, patch_defs)
    print(f'Reference: {refpath.name}; target wall Lab {np.round(target, 2).tolist()}')
    plans = []
    # Preflight every file before creating output, so unsupported inputs fail cleanly.
    for p in paths:
        rgb, meta = load(p)
        anchor, coeff, mask = fit_background(rgb)
        if abs(float(target[0]-anchor.lab[0])) > 5:
            raise ValueError(f'{p.name}: wall lightness difference exceeds 5 L*; inspect exposure/reference before using this small-drift matcher')
        if E.delta_ab(anchor.lab, target) > 5:
            raise ValueError(f'{p.name}: wall tint difference exceeds 5 a*b*; inspect the reference and anchor before continuing')
        plans.append((p, meta, anchor, coeff))
        print(f'  {p.name}: wall {np.round(anchor.lab, 2).tolist()}, sampled margin pixels {int(mask.sum())}', flush=True)
    if args.dry_run:
        print(f'Preflight passed for {len(paths)} images. No output written; visual QA is still required after export.')
        return 0
    outdir.mkdir(parents=True)
    review = outdir/'review'; review.mkdir()
    if args.jpeg:
        (outdir/'jpeg').mkdir()
    save_png(ref, review/'reference.png')
    thumbnails = []; sample_thumbnails = []; rows = []
    report = {'version': '1.0.0', 'status': 'in_progress', 'reference': refpath.name,
              'reference_metadata': refmeta, 'reference_target_lab': target.tolist(),
              'reference_coefficients_ab': refcoeff.tolist(), 'reference_patches': refpatch,
              'patch_definitions': patch_defs,
              'method': 'Spatial studio-wall tint matching and median wall lightness; no garment tonal matching.',
              'images': rows}
    def write_report():
        (outdir/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    write_report()
    try:
        for p, meta, anchor, coeff in plans:
            rgb, _ = load(p)
            isref = p == refpath
            if isref:
                corrected, limited = rgb, 0.
            else:
                corrected, limited = apply_background(rgb, anchor.lab, coeff, target, refcoeff)
            name = p.stem+'_wb.png'; destination = outdir/name
            save_png(corrected, destination)
            with Image.open(destination) as saved:
                actual = np.array(saved.convert('RGB'))
            count = protected_check(rgb, actual)
            if isref and not np.array_equal(rgb, actual):
                raise ValueError('Reference output is not pixel-identical after orientation/color normalization')
            aft = E.find_neutral_anchor(actual)
            row = {'name': p.name, 'output': name, 'reference': isref, **meta,
                   'output_dimensions': [actual.shape[1], actual.shape[0]], 'output_bytes': destination.stat().st_size,
                   'anchor_lab_before': anchor.lab.tolist(), 'anchor_lab_after': aft.lab.tolist() if aft.reliable else None,
                   'coefficients_ab': coeff.tolist(), 'gamut_limited_pct': limited*100,
                   'protected_pixels_verified_unchanged': count,
                   'patches_before': patches_of(rgb, patch_defs), 'patches_after': patches_of(actual, patch_defs)}
            if args.jpeg:
                jpg = outdir/'jpeg'/(p.stem+'_wb.jpg'); save_jpeg(corrected, jpg, args.jpeg_quality)
                with Image.open(jpg) as saved:
                    decoded = np.array(saved.convert('RGB'))
                if decoded.shape != actual.shape:
                    raise ValueError('JPEG dimensions changed')
                row['jpeg'] = {'output': str(Path('jpeg')/jpg.name), 'bytes': jpg.stat().st_size,
                               'quality': args.jpeg_quality, 'patches': patches_of(decoded, patch_defs)}
            rows.append(row)
            thumbnails.append((p.stem, thumbnail(rgb), thumbnail(actual)))
            sample_thumbnails.append((p.stem, thumbnail(rgb, patch_defs), thumbnail(actual, patch_defs)))
            write_report()
            print(f'Wrote {name}; {meta["source_bytes"]/1e6:.2f} MB -> {destination.stat().st_size/1e6:.2f} MB PNG', flush=True)
        report['review_sheets'] = sheets(thumbnails, review)
        report['sample_sheets'] = sheets(sample_thumbnails, review, 'wall-samples')
        if args.focus:
            report['focus_sheets'] = sheets([r for r in thumbnails if r[0] in args.focus], review, 'focus')
        report['summary'] = summarize(rows, refpatch, patch_defs)
        report['status'] = 'export_complete_visual_review_required'
        write_report()
    except Exception as exc:
        report['status'] = 'incomplete'; report['error'] = str(exc); write_report()
        raise
    print(f'Exported {len(rows)} masters to {outdir}. Inspect review/ and report.json before acceptance.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(2)
