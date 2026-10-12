"""Batch CLI: nano-corrector fix <files|dirs|globs...> --out DIR"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import engine as E

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def expand_inputs(items: list[str]) -> list[Path]:
    out: list[Path] = []
    for it in items:
        p = Path(it).expanduser()
        if p.is_dir():
            out += sorted(q for q in p.iterdir() if q.suffix.lower() in IMG_EXT and not q.name.startswith("."))
        elif any(c in it for c in "*?["):
            out += [Path(m) for m in sorted(glob.glob(str(p)))]
        elif p.exists():
            out.append(p)
        else:
            print(f"warning: not found: {it}", file=sys.stderr)
    seen, uniq = set(), []
    for p in out:
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(p)
    return uniq


def load_rgb(path: Path):
    """Return (rgb uint8 HxWx3, alpha or None, icc bytes or None). Decodes by content, not extension."""
    im = Image.open(path)
    icc = im.info.get("icc_profile")
    alpha = None
    if im.mode in ("RGBA", "LA", "PA"):
        alpha = np.asarray(im.getchannel("A"))
    return np.asarray(im.convert("RGB")), alpha, icc


def hex_to_chromaticity(hx: str) -> np.ndarray:
    hx = hx.lstrip("#")
    srgb = np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0
    return E.chromaticity(E.srgb_to_linear(srgb))


def save(path: Path, srgb_f: np.ndarray, alpha, icc, depth: int, dither: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if depth == 16:
        u16 = np.clip(np.rint(srgb_f * 65535.0), 0, 65535).astype(np.uint16)
        if alpha is not None:
            a16 = alpha.astype(np.uint16) * 257
            cv2.imwrite(str(path), cv2.cvtColor(np.dstack([u16, a16]), cv2.COLOR_RGBA2BGRA))
        else:
            cv2.imwrite(str(path), cv2.cvtColor(u16, cv2.COLOR_RGB2BGR))
        return
    x = srgb_f * 255.0
    if dither:  # opt-in: adds ~0.5 LSB of grain; only worth it if a strong curve leaves histogram gaps
        rng = np.random.default_rng(0)
        x = x + rng.random(x.shape, dtype=np.float32) + rng.random(x.shape, dtype=np.float32) - 1.0
    u8 = np.clip(np.rint(x), 0, 255).astype(np.uint8)
    im = Image.fromarray(np.dstack([u8, alpha]) if alpha is not None else u8)
    kw = {"icc_profile": icc} if icc else {}
    if path.suffix.lower() in (".jpg", ".jpeg"):
        im.convert("RGB").save(path, quality=97, subsampling=0, **kw)
    else:
        im.save(path, **kw)


def lab_to_rgb8(lab) -> tuple:
    px = cv2.cvtColor(np.array(lab, np.float32).reshape(1, 1, 3), cv2.COLOR_Lab2RGB).reshape(3)
    return tuple(int(round(float(np.clip(v, 0, 1)) * 255)) for v in px)


def contact_sheet(rows: list[dict], baseline_lab, path: Path):
    tw, th = 220, 293
    sheet = Image.new("RGB", (tw * len(rows), th + 92), (10, 10, 10))
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        x = i * tw
        if r.get("preview") is not None:
            t = Image.fromarray(r["preview"]); t.thumbnail((tw - 8, th))
            sheet.paste(t, (x + 4, 0))
        d.text((x + 6, th + 4), r["name"][:26], fill=(245, 245, 240))
        if r["status"] != "applied":
            d.text((x + 6, th + 20), r["status"], fill=(150, 150, 150))
            continue
        # chips: before | after | baseline, drawn at the image's own wall lightness so only chroma differs
        for j, lab in enumerate([r["anchor_lab_before"], r["anchor_lab_after"], baseline_lab]):
            lab = [r["anchor_lab_before"][0], lab[1], lab[2]]
            d.rectangle([x + 6 + j * 68, th + 38, x + 6 + j * 68 + 62, th + 62], fill=lab_to_rgb8(lab),
                        outline=(104, 201, 110) if j == 2 else (60, 60, 60))
        d.text((x + 6, th + 68), f"shift {r['correction_dE']:.2f} dE", fill=(134, 217, 138))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=90)


def cmd_fix(args) -> int:
    paths = expand_inputs(args.inputs)
    if not paths:
        print("no input images", file=sys.stderr)
        return 2
    if not args.out and not args.dry_run:
        print("error: --out is required unless --dry-run", file=sys.stderr)
        return 2
    out_dir = Path(args.out).expanduser() if args.out else Path(".")
    tonal = not args.no_tonal and not args.baseline_hex
    print(f"measuring neutral anchors in {len(paths)} images ...")

    anchors, profiles = [], []
    for p in paths:
        rgb, _, _ = load_rgb(p)
        anchors.append(E.find_neutral_anchor(rgb))
        profiles.append(E.cond_profile(rgb))

    ref_index = []
    for bi in args.baseline_image or []:
        ref = Path(bi).expanduser().resolve()
        hit = [i for i, p in enumerate(paths) if p.resolve() == ref]
        if hit:
            ref_index.append(hit[0])
        else:  # reference lives outside the batch
            rgb, _, _ = load_rgb(ref)
            anchors.append(E.find_neutral_anchor(rgb))
            profiles.append(E.cond_profile(rgb))
            ref_index.append(len(anchors) - 1)
    if args.baseline_hex:
        target = hex_to_chromaticity(args.baseline_hex)
        how, group = f"hex {args.baseline_hex}", []
    else:
        strategy = "reference" if ref_index else args.baseline
        target, how, group = E.choose_baseline(anchors, strategy, ref_index)
    ref_tone = E.cond_reference([profiles[i] for i in group]) if tonal else None
    base_lab = E.lab_of_linear(target / target.max() * 0.8)  # display only

    rows = []
    curves = {}
    for i, p in enumerate(paths):
        an = anchors[i]
        row = {"file": str(p), "name": p.name, "anchor_area_pct": round(an.area_frac * 100, 1),
               "anchor_lab_before": [round(float(v), 2) for v in an.lab], "status": "", "note": an.note}
        if not an.reliable:
            row.update(status="skipped: no reliable neutral anchor", gains=None, correction_dE=None)
            rows.append(row); continue
        if i in ref_index:
            row.update(status="reference (unchanged)", gains=[1.0, 1.0, 1.0], correction_dE=0.0,
                       anchor_lab_after=row["anchor_lab_before"])
            rows.append(row); continue
        g = E.gains_for(an.lin_rgb, target, args.strength)
        after = E.lab_of_linear(an.lin_rgb * g)
        shift = E.delta_ab(an.lab, after)
        if not tonal and shift < args.wall_deadband:  # below ~2 a*b* it is lighting variation
            g = np.ones(3, np.float32)
            after = an.lab
            row["note"] = (row["note"] + " " if row["note"] else "") + f"wall within {args.wall_deadband} of baseline: left alone"
        row.update(gains=[round(float(v), 4) for v in g], correction_dE=round(shift, 2),
                   anchor_lab_after=[round(float(v), 2) for v in after])
        if tonal:
            cv = E.cond_curve(profiles[i], ref_tone, args.strength)
            if cv is None:
                row["note"] = (row["note"] + " " if row["note"] else "") + "too few tone bins: wall gain only"
            else:
                if args.protect_highlights:
                    cv = E.protect_highlights(*cv)
                curves[i] = cv
                ys, gs = cv
                row["tonal_gains"] = [{"y": round(float(y), 4), "gains": [round(float(v), 4) for v in gg]}
                                      for y, gg in zip(ys, gs)]
        if shift > args.max_shift and not args.force:
            row["status"] = f"skipped: shift {shift:.1f} dE exceeds --max-shift {args.max_shift} (use --force)"
            rows.append(row); continue
        row["status"] = "applied"
        rows.append(row)

    rel = [(r, a) for r, a in zip(rows, anchors[:len(rows)]) if a.reliable]
    before = [np.array(r["anchor_lab_before"][1:]) for r, _ in rel]
    after = [np.array((r["anchor_lab_after"] if r["status"] == "applied" else r["anchor_lab_before"])[1:])
             for r, _ in rel]

    def spread(v):
        return float(max((np.hypot(*(x - y)) for x in v for y in v), default=0.0)) if len(v) > 1 else 0.0

    summary = {"baseline": how, "tonal": tonal, "protect_highlights": args.protect_highlights,
               "strength": args.strength, "images": len(paths),
               "baseline_files": [str(paths[i]) for i in group if i < len(paths)],
               "wall_spread_before_dE_ab": round(spread(before), 2),
               "wall_spread_after_dE_ab": None}
    print(f"baseline: {how}   tonal correction: {'on' if tonal else 'off'}")
    print(f"{'image':30s} {'wall a*,b*':>13s} {'wall dE':>7s}  {'tonal gain extremes (R,G,B)':30s} status")
    for r in rows:
        lab = r["anchor_lab_before"]
        sh = "-" if r["correction_dE"] is None else f"{r['correction_dE']:.2f}"
        tg = r.get("tonal_gains")
        if tg:
            allg = np.array([t["gains"] for t in tg])
            gtxt = ",".join(f"{v:.3f}" for v in allg.min(0)) + " .. " + ",".join(f"{v:.3f}" for v in allg.max(0))
        else:
            gtxt = "-"
        print(f"{r['name'][:30]:30s} {lab[1]:+6.2f},{lab[2]:+6.2f} {sh:>7s}  {gtxt:30s} {r['status']}")
    print(f"wall spread before: {summary['wall_spread_before_dE_ab']} (after measured during export)")

    previews = {}
    if not args.dry_run:
        for i, (p, r) in enumerate(zip(paths, rows)):
            if r["status"] == "reference (unchanged)":
                rgb, alpha, icc = load_rgb(p)
                dest = out_dir / f"{p.stem}{args.suffix}.png"
                dest.parent.mkdir(parents=True, exist_ok=True)
                kw = {"icc_profile": icc} if icc else {}
                Image.fromarray(np.dstack([rgb, alpha]) if alpha is not None else rgb).save(dest, **kw)
                r["output"] = str(dest)
                if args.sheet:
                    previews[i] = cv2.resize(rgb, None, fx=0.12, fy=0.12, interpolation=cv2.INTER_AREA)
                continue
            if r["status"] != "applied":
                continue
            rgb, alpha, icc = load_rgb(p)
            if tonal and i in curves:
                ys, gs = curves[i]
                out, clipped = E.apply_curve(rgb, ys, gs, return_clipped=True)
            else:
                out, clipped = E.apply_gains(rgb, np.array(r["gains"], np.float32), return_clipped=True)
            r["clipped_pct"] = round(clipped * 100, 3)
            if clipped > 0.005:
                r["note"] = (r["note"] + " " if r["note"] else "") + f"{clipped:.2%} of pixels clipped"
            dest = out_dir / f"{p.stem}{args.suffix}.{args.format}"
            save(dest, out, alpha, icc, args.depth, args.dither)
            r["output"] = str(dest)
            u8 = np.clip(np.rint(out * 255.0), 0, 255).astype(np.uint8)
            measured = E.find_neutral_anchor(u8)
            r["anchor_lab_after"] = [round(float(v), 2) for v in measured.lab] if measured.reliable else None
            r["correction_dE"] = round(E.delta_ab(anchors[i].lab, measured.lab), 2) if measured.reliable else None
            if tonal and i in curves:
                aft = E.cond_profile(u8)
                r["residual_pct_after"] = [
                    None if (a is None or q is None) else
                    [round(float((np.exp(q["r"] - a["r"]) - 1) * 100), 1), round(float((np.exp(q["q"] - a["q"]) - 1) * 100), 1)]
                    for a, q in zip(aft, ref_tone)]
            if args.sheet:
                previews[i] = cv2.resize(u8, None, fx=0.12, fy=0.12, interpolation=cv2.INTER_AREA)
        actual = [np.array(r["anchor_lab_after"][1:]) for r in rows
                  if r.get("output") and r.get("anchor_lab_after") is not None]
        summary["wall_spread_after_dE_ab"] = round(spread(actual), 2)
        summary["wall_after_measurement"] = "re-detected from quantized corrected pixels"
        print(f"measured wall spread: {summary['wall_spread_before_dE_ab']} -> {summary['wall_spread_after_dE_ab']}")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps({"summary": summary, "images": rows}, indent=2))
        with open(out_dir / "report.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "status", "wall_L", "wall_a", "wall_b", "area_pct", "gain_r", "gain_g", "gain_b", "wall_shift_dE"])
            for r in rows:
                g = r["gains"] or ["", "", ""]
                w.writerow([r["name"], r["status"], *r["anchor_lab_before"], r["anchor_area_pct"], *g, r["correction_dE"]])
        if args.sheet:
            contact_sheet([dict(r, preview=previews.get(i)) for i, r in enumerate(rows)], base_lab,
                          Path(args.sheet).expanduser())
            print(f"sheet: {args.sheet}")
        print(f"wrote {sum(r['status'] == 'applied' for r in rows)} images + report to {out_dir}")
    failed = [r for r in rows if r["status"].startswith("skipped")]
    return 1 if (failed and args.strict) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="nano-corrector",
                                 description="Match a batch of images to one white-balance baseline.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fix", help="measure neutral surfaces, pick a baseline, correct every image")
    f.add_argument("inputs", nargs="+", help="files, directories, or globs")
    f.add_argument("--out", help="output directory (inputs are never overwritten); required unless --dry-run")
    f.add_argument("--baseline", choices=["neutral-most", "consensus"], default="neutral-most",
                   help="how to pick the set baseline (default: cleanest image + near-twins)")
    f.add_argument("--baseline-image", nargs="+",
                   help="match everything to these image(s); several are averaged (e.g. the untouched originals)")
    f.add_argument("--baseline-hex", help="match every neutral surface to this color's chromaticity, e.g. '#EAE8E6'")
    f.add_argument("--no-tonal", action="store_true",
                   help="wall-only white balance; skip the shadow/midtone matching")
    f.add_argument("--protect-highlights", action="store_true",
                   help="tonal mode: fade correction to zero by L*=78; use when bright neutrals already agree")
    f.add_argument("--wall-deadband", type=float, default=2.0,
                   help="leave the wall alone when it is already within this many a*b* units of the baseline")
    f.add_argument("--strength", type=float, default=1.0, help="0..1, how much of the correction to apply")
    f.add_argument("--depth", type=int, choices=[8, 16], default=8, help="output bit depth for PNG")
    f.add_argument("--format", choices=["png", "jpg"], default="png",
                   help="output format (png is lossless; jpg re-encodes at q97)")
    f.add_argument("--suffix", default="_wb", help="appended to output file stems")
    f.add_argument("--dither", action="store_true", help="dither 8-bit output (off: measured gap-free on tested sets)")
    f.add_argument("--max-shift", type=float, default=8.0, help="skip images needing more than this a*b* shift")
    f.add_argument("--force", action="store_true")
    f.add_argument("--dry-run", action="store_true", help="measure and print only; write nothing")
    f.add_argument("--sheet", help="write a before/after QA contact sheet to this path")
    f.add_argument("--strict", action="store_true", help="exit 1 if any image was skipped")
    f.set_defaults(fn=cmd_fix)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
