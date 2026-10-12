# Nano Corrector

Match white or near-neutral studio backgrounds across an image batch to a trusted
reference. Runs locally, preserves your originals, and produces before/after
comparisons so you can check the result.

The reusable skill is in **[package/nano-corrector](package/nano-corrector)**.
It includes the scripts, assistant instructions, tests, and lessons from the
background-matching trials. No account, API key, or image upload is required.

## Quick start

Install Python 3.10+ and Git. Then, on macOS/Linux:

```sh
git clone https://github.com/fl4meboi/nano-corrector.git
cd nano-corrector/package/nano-corrector
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

.venv/bin/python scripts/match_backgrounds.py "/path/to/photos" \
  --reference "/path/to/photos/reference.png" \
  --out "/path/to/photos-matched-v1" --jpeg
```

Replace the paths with your own. Choose the reference whose **background** you
want to match, and use a new output folder. On Windows, use `py -3 -m venv .venv`
and `.\.venv\Scripts\python.exe`; full PowerShell examples are in the
[setup guide](package/nano-corrector/README.md).

To check the batch before exporting, use the same command with `--dry-run`.
`--focus image-I image-J image-K` adds a comparison sheet for those file stems.

## Use it as an assistant skill

Open the cloned repository in Codex or another assistant with local file and
Python access, then ask:

> Read `package/nano-corrector/SKILL.md` and set up its dependencies. Match the
> background whites in `/path/to/photos` to `/path/to/reference.png`. Save to
> `/path/to/photos-matched-v1`, include smaller JPEG copies, and visually check the
> saved background comparisons before finishing.

For a persistent installation, place the **inner** `package/nano-corrector`
folder in your assistant's skills directory. For Codex this is normally
`~/.codex/skills/nano-corrector`; start a new session and invoke `$nano-corrector`.
If replacing an older version, back it up outside the skill search directories
first. Create the virtual environment after putting the skill in its final location.

## Outputs

- Full-resolution **PNG masters** with no additional lossy compression.
- Smaller **JPEG copies** in `jpeg/` when `--jpeg` is used.
- Before/after and sample-location sheets in `review/`.
- `report.json` with measurements taken from the saved files, dimensions, sizes,
  reference treatment, and checks for protected pixels.

PNG masters can be much larger than JPEG originals without looking sharper.
Use the JPEG copies for sharing and keep the PNGs as masters. Processing happens
locally; internet access is needed only for installation and repository updates.

## What this is designed for

Small background tint/brightness drift across similar studio scenes with exposed
neutral wall on both sides of the subject. The method matches wall tint spatially
and median wall brightness while retaining natural shadows and sunlight.

This is **not** semantic subject segmentation or calibrated product color grading.
Pale neutral clothes can also change. Different lighting patterns will not become
identical. Review a representative subset of a new shoot before processing it all.

Supports still, opaque, 8-bit RGB/grayscale JPEG/PNG. EXIF orientation is applied;
embedded color profiles are converted to sRGB; untagged files assume sRGB.
Transparent, high-bit-depth, animated or unsupported images are rejected.

Read the [quality-check guide](package/nano-corrector/references/quality-checks.md)
and [trial lessons](package/nano-corrector/references/lessons.md). Earlier attempts
focused on garments and protected the very highlights that needed correction;
the packaged workflow explicitly checks the user's background-whiteness goal.

## Tests

From `package/nano-corrector`, after installing dependencies:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Fourteen synthetic tests cover fitting, pixel preservation, input/output safety,
arbitrary filenames and batch counts, color profiles, orientation and portable
execution. The packaged engine also reproduced all 12 reviewed case-study outputs
pixel-for-pixel. See [validation details](package/nano-corrector/references/validation.md)
for platform and dependency-installation limits.

## Repository layout

- `package/nano-corrector/`: maintained, portable skill; **start here**.
- `releases/`: ready-to-share ZIP of the skill.
- `scripts/build_skill.py`: rebuild and verify the distribution archive.
- `src/`, root `tests/`, other root `scripts/`, and `nano-corrector`: earlier
  experimental workbench kept for reference. These are not the recommended entry
  point; some QA scripts are specific to the original twelve-image case study.

Private shoot images, generated corrections, reports, caches, and virtual
environments are excluded from version control. Dependencies are installed
separately and remain under their respective licenses.

## License

[MIT](LICENSE).
