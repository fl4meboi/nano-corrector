# Nano Corrector — coworker starter kit

Match white studio backgrounds to one trusted reference. This is the background
workflow developed after the earlier garment-focused attempts failed. It works
locally and includes the scripts, skill instructions, QA sheets and tests.

## 1. Unzip and install dependencies

Use Python 3.10 or newer; Python 3.12 was used for validation. Python and package
installation are the only setup requirements. No API key is needed. Network
access is needed to install dependencies; image processing runs offline.

From the extracted **nano-corrector** folder, on macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use `requirements.txt` for compatible dependencies. `requirements-tested.txt`
records the exact versions used in the validation environment; it is optional.
The virtual environment is local to the extracted folder; do not share it.

## 2. Run with an assistant

You can use the folder immediately, without global installation. Give your
assistant this prompt, replacing the paths and reference:

> Read `/path/to/nano-corrector/SKILL.md` and use its scripts to match the background
> whites in `/path/to/shoot` to `/path/to/shoot/reference.png`. Write a new folder
> `/path/to/shoot-matched-v1`, include smaller JPEG copies, and visually sanity-check
> the saved background comparisons before finishing.

Optional Codex installation: put the **nano-corrector** folder in your Codex
skills directory (normally `~/.codex/skills/`), then start a new session. If an
older nano-corrector skill is already installed, back it up outside the skill
search directories and replace it; avoid two active copies of the same skill.
Create the environment in its final location. Then invoke:

> `$nano-corrector` Match the background whites in `/path/to/shoot` to
> `/path/to/shoot/reference.png`. Save to `/path/to/shoot-matched-v1`, include JPEG
> copies, and check the background differences carefully.

For other assistants, use the explicit SKILL.md prompt above; folder discovery
and `$skill-name` syntax depend on the host application.

## 3. Or run directly in a terminal

From the skill folder, on macOS/Linux:

```sh
.venv/bin/python scripts/match_backgrounds.py "/path/to/shoot" \
  --reference "/path/to/shoot/reference.png" --dry-run

.venv/bin/python scripts/match_backgrounds.py "/path/to/shoot" \
  --reference "/path/to/shoot/reference.png" \
  --out "/path/to/shoot-matched-v1" --jpeg
```

PowerShell (single line):

```powershell
.\.venv\Scripts\python.exe scripts\match_backgrounds.py "C:\Photos\shoot" --reference "C:\Photos\shoot\reference.png" --out "C:\Photos\shoot-matched-v1" --jpeg
```

Replace the reference with the image whose **background** you want to match. The
script does not choose one for you. The reference can be outside the input folder.
Folder scanning is not recursive. JPEG/PNG files, multiple input paths and quoted
globs are supported. A reference outside the input batch appears in the review
folder but is not added as an extra corrected deliverable.

Useful options:

- `--focus image-I image-J image-K reference`: extra comparisons using file stems,
  without extensions; names must be in the input batch.
- `--jpeg-quality 95`: default sharing quality, with 4:4:4 chroma sampling.
- `--patches wall-patches.json`: customize the wall rectangles used for QA.
- `--dry-run`: checks/fits inputs without writing output; not visual approval.
- `--help`: full command syntax.

## What you receive

```text
shoot-matched-v1/
  image_wb.png              Lossless full-resolution masters
  jpeg/image_wb.jpg         Smaller copies when --jpeg is used
  report.json              Saved-file measurements, settings, dimensions, sizes
  review/reference.png     Reference after orientation/color normalization
  review/before-after-*.png
  review/wall-samples-*.png Sample locations for validating QA
  review/focus-*.png        When --focus is supplied
```

The script refuses an existing output directory and never overwrites originals.
Every successful export still requires visual review. Start with a representative
subset for a new shoot, then process the batch if the result is suitable. Multiple
input files allow a subset while the reference remains outside that subset.

PNG output can be several times larger than an original JPEG without looking
sharper. PNG avoids another lossy encoding; it cannot recover details already
lost from the original. Share the `jpeg/` copies when smaller files are useful.
Re-encoding can also make a PNG smaller without changing its pixels. Pixel-identical
reference claims refer to the PNG master after any orientation/profile normalization.

## What it can and cannot do

The method fits a smooth background tint across exposed left/right wall margins,
matches median wall brightness, and retains local shadows and sunlight. It is
intended for small drift across similar studio scenes. It will not make different
lighting patterns identical, accurately segment every pale garment, or repair
arbitrary outdoor/colorful backgrounds. It is not a calibrated product-color tool.
Do not interpret automatic QA as proof that a sample contains wall rather than clothes.

Input support: still 8-bit RGB/grayscale JPEG/PNG, opaque images. EXIF rotation is
applied; embedded ICC profiles are converted to sRGB; untagged files assume sRGB.
Other inputs need a deliberate conversion or a different workflow. Metadata other
than the output sRGB profile is not copied (including camera EXIF/GPS).

Read [quality checks](references/quality-checks.md) before approving output and
[the trial lessons](references/lessons.md) for the reasoning behind this approach.

## Validate the installation

```sh
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, substitute `.\.venv\Scripts\python.exe` for the Python executable.
These tests use synthetic images in temporary directories. No client images,
credentials, previous outputs or machine-specific paths are included in this kit.

See [release validation](references/validation.md) for tests, environment details
and the limits of the cross-platform checks.
