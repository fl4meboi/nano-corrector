# Reviewing a background match

## What to inspect

Open reference.png and the before/after PNG sheets in the same color-managed
viewer. Check the user's problem images together. Look at the complete frame,
several exposed wall areas, and native-size crops along hair/shoulders/clothing.
Confirm the correction makes the intended background less pink/yellow/gray
without visible halos or harsh transitions. Natural shadows and sunlight should
remain. Sample numerical tint and brightness separately; one can improve while
the other worsens. If sharing JPEGs, inspect representative JPEG copies too.

`wall-samples-*.png` marks rectangles numbered in the order of
`report.json.patch_definitions`. Ensure every measured box is actual background
in each pose and in the reference. Heuristics cannot distinguish a white sleeve
from a white wall. A visually incorrect sample must not be used as evidence of
success, even if `plausible_wall` is true.

## Report meaning

- `status=export_complete_visual_review_required`: export/checks completed; a human
  or image-capable assistant still needs to view the results. It is not a quality badge.
- `anchor_lab_before/after`: neutral wall re-detected from normalized input and the
  decoded saved PNG. Missing after values need inspection, not a zero-error claim.
- `summary.before/after_wall_tint_spread_ab`: maximum pairwise a*/b* distance among
  batch anchors. This excludes brightness.
- `summary.before/after_wall_lightness_range`: range of wall L*, separately.
- `summary.fixed_patches`: same original-coordinate pixels measured before/after,
  compared to the corresponding reference box. Only plausible original/reference
  patches count, and the reference is excluded from mismatch averages. Check the
  image count; omitted/invalid samples mean missing evidence, not perfect matching.
- `gamut_limited_pct`: where the requested adjustment was reduced to stay within
  RGB gamut, not a fraction of clipped output. Near-white taper is also applied.
- `protected_pixels_verified_unchanged`: dark (L*≤60) or saturated (C*≥12) source
  pixels verified unchanged in the PNG master. This does not promise all skin,
  hair, or clothing is protected. The mask is numerical, not semantic.
- `reference`: included reference was unchanged relative to the orientation/profile
  normalized source. Untagged sRGB sources without rotation retain identical RGB pixels.
- `jpeg.patches`: measurements from the actual decoded sharing JPEG. JPEG is lossy;
  pixel-preservation claims do not apply to it.

Some samples overlap the fitting area. Cross-pose consistency is not an independent
color calibration test. No universal acceptance threshold is provided: the user's
visual goal, sample validity and remaining variation matter.

## Custom QA rectangles

The default rectangles match the exposed side-wall layout of the case study.
For a different composition, create JSON in this format:

```json
[
  {"name": "left_wall", "box": [0.04, 0.15, 0.10, 0.25]},
  {"name": "right_wall", "box": [0.90, 0.15, 0.96, 0.25]}
]
```

Box coordinates are `[left, top, right, bottom]`, each a fraction from 0 to 1 of
image width/height after EXIF orientation. Use boxes that contain exposed wall
in all images and the reference. Pass `--patches /path/to/boxes.json`. This changes
QA regions only; it does not change the wall-fitting masks. The current solver
requires neutral margins on both sides. Use a different workflow when those
margins are obstructed; moving QA rectangles cannot fix an invalid model.

## If the result is still wrong

Check reference choice, wall sample validity, input color profiles, and whether
lighting/scene layout actually match. Start any correction from original files
in a new output folder. Do not keep stacking passes, force all highlights to pure
white, or rewrite a failed check as success. If the method is unsuitable, show
representative comparisons and identify the missing condition for a better match.
