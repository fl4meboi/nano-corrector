# Lessons from the AC-01 trials

The user wanted white studio backgrounds to match. Initial work chased magenta
in clothing, judged success from hats/trousers, and protected the highlights.
That left the user's visible background problem untouched. The corrective lesson
is to identify the intended target before selecting an algorithm or metric.

## What failed and why

- **Whole-image tone-bin matching:** different crops/poses change the mix of wall,
  skin and clothing within a brightness bin. A small fitted residual can coexist
  with incorrect garment color. The early run made cream trousers less consistent.
- **Protecting all highlights:** helped trousers, but prevented the requested
  background correction. The v2 “success” claim was wrong for the user's goal.
- **Wall-only chromaticity with fixed luminance:** cannot fix a background that
  is darker as well as warmer. Tint and brightness need separate checks.
- **One global wall value:** can miss left-to-right tint changes. The final
  method models wall tint spatially using exposed margins.
- **Additive brightening without a shoulder:** clipped sunlit whites. The final
  implementation fades the adjustment near pure white and limits it at RGB gamut
  boundaries by scaling the whole adjustment instead of clipping channels.
- **Predicted numbers reported as output measurements:** previous reporting used
  a hypothetical gain-only result even when applying a different curve. This kit
  decodes saved masters and measures them directly.
- **Lossless exports without explanation:** JPEG sources became much larger PNGs
  without visibly sharper detail. Preserve masters and offer smaller JPEG copies.

## The final AC-01 result (case evidence, not a universal guarantee)

L was selected explicitly as the background reference. Processing restarted from
originals. A was also matched to L rather than being frozen as a second reference.
The final studio-background run measured:

| Check | Before | After |
|---|---:|---:|
| Wall-anchor tint spread, maximum pairwise a*b* | 1.77 | 0.35 |
| Wall-anchor brightness range, L* | 1.90 | 0.40 |
| I/J/K/L upper-left mean tint distance to L | 1.02 | 0.21 |
| I/J/K/L upper-right mean tint distance to L | 0.61 | 0.18 |
| I/J/K/L middle-left mean tint distance to L | 1.82 | 0.17 |
| I/J/K/L middle-right mean tint distance to L | 1.50 | 0.56 |

Those original case patch averages included L itself (distance zero), used median
RGB converted to Lab, and were not calibrated accuracy measurements. The packaged
QA improves the bookkeeping: it excludes the reference from mean mismatch and
measures median Lab of patch pixels. Its numbers need not equal those case values.
Some sample regions overlap the fitted wall; they are consistency checks, not
independent validation data. The final user-facing result retained natural
lighting and remaining small differences; no exact-match claim was justified.

Do not transplant the reference filename, scene coordinates, “safe” garment
thresholds or acceptance numbers unquestioningly to a new shoot. Inspect sample
locations and outputs. The model is bright/low-chroma masking, not semantic
subject segmentation. Bright neutral objects can still be affected.
