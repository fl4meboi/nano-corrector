# Workflow lessons

Identify the requested correction target before selecting an algorithm or metric.
For background matching, measure exposed background regions and review the saved
outputs directly.

## What failed and why

- **Whole-image tone-bin matching:** different crops and poses change the mix of wall,
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

The method fits wall tint spatially, adjusts median wall brightness, and fades the
adjustment near pure white to reduce clipping. Measurements from sampled wall
patches are consistency checks, not calibrated accuracy claims. Sample locations
can overlap the fitted wall, so they are not independent validation data.

Inspect sample locations and outputs for every new scene. The model uses
bright/low-chroma masking, not semantic subject segmentation. Bright neutral
objects can still be affected.
