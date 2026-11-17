# Nano Corrector: from magenta-drift fix to background matcher

All times are America/New_York. Sources: Claude Code transcripts for this folder, Codex rollouts for this folder, the folder's own reports and tests, and the public GitHub repository, checked on 2026-10-14. Client and shoot names are deliberately left out so this file can ship in the public repository.

## Outcome and context

Nano Corrector is a local Python tool that colour-matches a batch of AI-generated images without a round trip to Photoshop. It started on Oct 10, 2026 from a problem raised on a customer workshop call (Oct 9): Nano Banana generations drift towards magenta over successive edits, and DJ was fixing that by hand with a 16-bit Photoshop curves layer about every three generations. The call suggested a custom FLORA action; DJ asked for a skill instead.

Two different tools came out of three days of work, and they are not the same algorithm:

| | Workbench (Claude Code, Oct 10-11) | Packaged skill (Codex, Oct 12) |
|---|---|---|
| Goal | Remove magenta in shadows and midtones | Make studio background whites match one reference |
| Method | Per-lightness-bin red/green and blue/green gains in linear light, fitted to chosen baseline images | Spatial wall-tint fit plus median wall brightness, masked to bright low-chroma pixels |
| Where | `src/nano_corrector`, `nano-corrector` wrapper | `package/nano-corrector`, ZIP in `releases/` |
| Installed as skill | Yes: `~/.agents/skills/nano-corrector/SKILL.md` still describes this one | No: published on GitHub as `fl4meboi/nano-corrector` (personal account) |

## Stages

**1. Scoping (Oct 10, Claude Code).** DJ asked for a plan to build a colour corrector, either as a Photoshop action or a FLORA custom action. Claude read the workshop notes through the Granola connector and recommended a code-first engine with thin wrappers (skill, CLI, later a FLORA action). A copy of this thread also appears as an imported Codex rollout (Oct 10, 18:20); it is the same conversation and is counted once.

**2. First build on real images (Oct 11, 19:03-19:22, Claude Code).** DJ's custom action "didn't really work", so Claude built the engine on 12 images from one shoot. It reported almost no cast because it measured the bright wall, which was nearly neutral. It also found that ten ".png" files were really JPEGs. DJ could see that image H was more magenta than I; Claude re-measured by tone band and agreed the magenta lived in shadows and midtones. The earlier "nothing to fix" claim was wrong.

**3. Tonal engine (Oct 11, 19:41-20:40).** With images A and L named as the baseline, Claude replaced a capped wall-only fix with ten lightness bins and smooth per-channel gains (capped at +/-35%) in float32 linear light, luminance-preserving, with an optional 16-bit output. Checks: a* heat maps, an injected-cast recovery test, no clipping, and two held-out colours. The red hat's colour spread improved (11.8 to 8.9) but the cream trousers' spread worsened (2.1 to 2.8) because their bin mixes wall and trousers. The thread ended with 6 passing tests and a caveat: "Photoshop-equivalent" cannot be claimed without a Photoshop-corrected reference.

**4. A rerun that missed the goal (Oct 12, 05:39-06:06, Codex).** A new thread re-ran the set with a highlight-protected variant: hat spread 11.66 to 8.85, trousers unchanged, A and L pixel-identical. DJ's actual concern was background whiteness (I/J/K/L visibly differed), and the delivery had deliberately left backgrounds alone. The agent said so and the variant was rejected.

**5. Background matching (06:47-06:54).** Using L as the reference, the fit corrects tint spatially and brightness at the wall. Brightening first clipped sunlit areas, so the adjustment now tapers near white and scales uniformly at gamut edges. Saved-file results on the trial set: wall tint spread 1.77 to 0.35 (Lab a*b* units), wall lightness range 1.90 to 0.40 L*, and four I/J/K/L patches each moved closer to L. The review sheets are in the gitignored `deliverables/*-v3-background/review/`.

**6. Output format (07:15).** DJ asked why files were so much larger. JPEG sources were saved as lossless PNG to avoid another compression pass (one 3584 x 4800 frame: 2.01 MB JPEG, 13.74 MB PNG). An optional JPEG copy (quality 95) was added: about 17 MB against 71 MB for the PNG masters across the set.

**7. Packaging (07:19-07:29).** The workflow was packaged as a portable skill: one script, `SKILL.md`, setup README, quality-check guide, lessons, `requirements-tested.txt`, a build script and a v1.0.0 ZIP. The packaged script reproduced all 12 reviewed corrections pixel for pixel.

**8. Publication and an audit (10:19-11:18).** DJ asked for a public GitHub repo under `fl4meboi`. The agent published 33 reviewed files from a clean temporary checkout (commit `9de39943`, 10:24) because this working folder had no commits. DJ then asked for a check that no client context was public. The audit found trial-set names and measurements in `lessons.md`, `SKILL.md`, `requirements-tested.txt`, the ZIP, and two QA scripts. A sanitised replacement (commit `5264780`, prepared in the thread's temporary checkout) removed them and the working tree here is already clean, but the thread ended before the push was confirmed. On 2026-10-14 the public `main` was still `9de39943` with the two QA scripts present.

**9. Demo film (Oct 13-14, Claude Code; separate project).** A 41.7 s film (16:9 and 4:5) showing what the tool does was made in `~/VSCode/content-creator-video-editor/short-form/projects/nano-corrector-demo/` from a new set of three to four images with deliberate white-balance offsets, corrected with this tool. It has its own README and is not part of this repository.

## Final delivery and verification

- Distribution: `releases/nano-corrector-skill-v1.0.0.zip` and the package folder. Entry point: `package/nano-corrector/SKILL.md`.
- Checks performed: 14 package tests pass (re-run 2026-10-14, 4.7 s); the earlier workbench's 9 tests pass when run with `PYTHONPATH=src` (without it, pytest fails at collection); saved-file measurements and visual review of sheets in the Oct 12 thread.
- Not done: Windows/Linux runs, a clean dependency install, and any comparison against a Photoshop-corrected image (none exists in the folder). The method is not semantic segmentation: pale neutral clothing can shift.

## Time and cost

- Elapsed spans (not labour): Claude thread Oct 10 17:26 to Oct 11 20:40 with the context-compaction marker at 20:40; Codex threads Oct 12 05:39 to 11:18 across three rollouts. Active human time: not recorded. Agent execution time: not recorded.
- Measured runtimes: package test suite 4.7 s (2026-10-14); full-set export timings not recorded.
- Cost: the tool itself needs no paid service. Model usage appears in transcripts as token counts but was not converted to currency; subscriptions are not allocated. Cost of the trial-set generations and of the demo film's FLORA canvas and music generations: not recorded here.
- Note on tokens: a diagnostic in the Oct 12 thread printed two GitHub account tokens; rotation was advised and is not verifiable from this folder.

## Maintenance and handoff

1. Decide which flavour is canonical for the installed skill. Today the installed `SKILL.md` runs the workbench; the public package runs the background matcher.
2. Push the sanitised commit (or an equivalent) so the public repository matches this folder; confirm the two project-specific QA scripts under `scripts/` are gone upstream (they are not in this folder).
3. This working folder has no commits and no remote. Initialise or clone the public repo here before further edits. `_work/` and `deliverables/` are gitignored and hold private trial images; back them up separately.
4. To close the Photoshop-equivalence question, supply one Photoshop-corrected image pair or the curves preset and compare numerically.
5. Setup: Python 3.10+; `package/nano-corrector/requirements-tested.txt` records the validated versions.
