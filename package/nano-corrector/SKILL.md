---
name: nano-corrector
description: Match white or near-neutral studio backgrounds across an image batch to a trusted reference, with local Python processing and visual QA. Use for inconsistent background whiteness or pink/yellow background drift. Intended for similar studio scenes with exposed walls on both sides, not general creative grading or exact garment color matching.
---

# Nano Corrector

Make the **backgrounds** look consistent with the user's chosen reference. Measure
both tint and brightness, preserve natural lighting, and inspect the saved files.
A successful numerical fit is not by itself a successful visual result.

## Start

- Use the reference and objective already established in the conversation. If
  no reference is specified, ask which image's background should be matched.
  Do not silently choose the whitest image or assume a filename such as L.
- Inspect the reference and a representative problem group before running.
  Confirm similar studio lighting/layout with visible neutral wall on both sides.
  A white garment is not a wall sample. For a different scene or blocked margins,
  explain the limitation and use a suitable manual/color-managed workflow.
- If the request is primarily about garments, skin, or creative grading, this
  background matcher is not sufficient. Do not substitute those goals for the
  user's background-whiteness request, or vice versa.

## Run locally

Resolve paths relative to **this SKILL.md**, never to a developer's home folder.
Follow [README.md](README.md) for first-time setup, installation and platform commands.
Use the skill's virtual-environment Python; the script accepts arbitrary paths
and works from any current directory.

```sh
"<skill>/.venv/bin/python" "<skill>/scripts/match_backgrounds.py" "<input folder>" \
  --reference "<reference image>" --dry-run

"<skill>/.venv/bin/python" "<skill>/scripts/match_backgrounds.py" "<input folder>" \
  --reference "<reference image>" --out "<new output folder>" --jpeg
```

- Use original inputs and a **new output directory** for every iteration; the
  script refuses existing directories. Do not stack corrections on earlier output.
- The reference may live inside or outside the batch. Included reference pixels
  pass through unchanged after EXIF orientation and color-space normalization.
- `--focus name1 name2` adds a comparison sheet for image stems the user identified.
- PNG masters are always retained. `--jpeg` adds smaller quality-95 JPEG copies
  for sharing; `--jpeg-quality` is adjustable. Explain that larger lossless PNGs
  do not add detail. Sources are never overwritten.
- Preflight rejects unsupported images, duplicate output names, unreliable walls,
  and shifts beyond this small-drift method's range. Do not bypass a failure or
  silently exclude a requested image. Report what requires a better input/reference.

## Acceptance check

Read [references/quality-checks.md](references/quality-checks.md) when reviewing output
or adapting the default sample patches. Before claiming completion:

1. Open `review/reference.png`, every `review/before-after-*.png`, the focus sheet
   if requested, and `review/wall-samples-*.png`. Confirm sample boxes cover wall.
2. Inspect the user's troublesome group together, plus representative native-size
   subject/background edges. Check tint, perceived brightness, halos, pale clothing,
   skin, hair, natural shadows and highlights. Do not only inspect tiny thumbnails.
3. Check `report.json`: every requested image exported; dimensions retained after
   orientation; protected pixels verified; wall tint **and** lightness measures;
   fixed-patch differences; gamut limiting; reference treatment; file sizes.
4. The export status explicitly requires visual review. Report remaining variation
   and any regressions. If invalid samples distort the numbers, supply verified
   boxes with `--patches` and rerun from originals into a new directory. If the
   background model is unsuitable, stop treating this method as a successful match.

Deliver the output folder and a direct comparison link, state the reference, and
summarize the background checks. For coworker handoff, point to `jpeg/` for small
copies and PNGs for masters. Do not claim identical backgrounds or calibrated true
colors: lighting and scene content differ.

## Lessons that determine this workflow

Read [references/lessons.md](references/lessons.md) if selecting an approach or
investigating a mismatch. In particular:

- The failed highlight-protected pass left the backgrounds unchanged. Do not use
  `--protect-highlights` or a “small difference” deadband to ignore the user's target.
- Matching whole-image lightness-bin statistics can recolor cream trousers because
  the bins mix wall and clothing. This package fits exposed wall margins instead.
- A luminance-preserving white-balance adjustment cannot fix brightness differences.
- Report actual saved-pixel measurements, not predicted wall-gain results or hat
  statistics presented as evidence of background success.

## Scope

Runs locally without accounts, cloud uploads, image-generation services, or paid
APIs. Runtime packages are listed in requirements.txt. Tested on the AC-01 studio
set and synthetic checks; inspect each new shoot. Supports still 8-bit RGB/grayscale
JPEG/PNG; rejects transparency, high-bit-depth PNG, animation and unsupported modes.
Untagged input is assumed sRGB; embedded profiles are converted to sRGB. Matching
is smoothly restricted by brightness/chroma, not semantic segmentation: pale
neutral objects may change. Dark/saturated pixel preservation applies to PNG
masters, not lossy JPEG copies.
