# Release 1.0.0 validation

Validated on macOS with Python 3.12 and requirements-tested.txt versions.

- Fourteen synthetic tests cover spatial wall matching, dark/saturated subject
  preservation, pure white, arbitrary filenames and batch size, multi-page QA,
  external/included references, paths with spaces, different working directory,
  optional JPEGs, source preservation, existing-output/collision protection,
  unsupported inputs, EXIF orientation and embedded profile handling.
- Full AC-01 rerun: all 12 packaged PNGs were pixel-identical to the reviewed
  final background correction. Original dimensions retained; L remained unchanged.
- Before/after sheets, sample locations, focus group and a native-resolution
  original/PNG/JPEG boundary comparison were visually inspected.
- Sharing JPEGs: about 17 MB total versus 71 MB for the PNG masters in that set.
  This is an example, not an expected compression ratio for every shoot.
- Skill frontmatter passed the skill-creator validator. The ZIP excludes input
  photos, environments, caches and local reports.

The runtime is platform-neutral Python; Windows/Linux instructions are provided,
but those operating systems were not executed in this validation environment.
Dependency download/fresh installation was not tested here because the execution
environment had restricted network resolution; runtime tests used the listed
installed packages. The exact tested versions are recorded separately from the
broader compatible installation ranges.

This is not validation on arbitrary shoots or a promise of exact product colors.
Review a representative subset whenever the scene, lighting, reference or framing
changes. See quality-checks.md for the required output review.
