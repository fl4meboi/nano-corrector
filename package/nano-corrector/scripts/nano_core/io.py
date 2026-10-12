"""Color-managed, orientation-aware 8-bit photo I/O; source files are read-only."""
from io import BytesIO
from pathlib import Path
import glob
import numpy as np
from PIL import Image, ImageCms, ImageOps

EXTENSIONS = {'.jpg', '.jpeg', '.png'}
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
SRGB_BYTES = SRGB.tobytes()


def inputs(items):
    paths = []
    for item in items:
        p = Path(item).expanduser()
        if p.is_dir():
            found = sorted(q for q in p.iterdir() if q.is_file() and q.suffix.lower() in EXTENSIONS and not q.name.startswith('.'))
        elif glob.has_magic(str(p)):
            found = [Path(q) for q in sorted(glob.glob(str(p))) if Path(q).is_file() and Path(q).suffix.lower() in EXTENSIONS]
        elif p.is_file() and p.suffix.lower() in EXTENSIONS:
            found = [p]
        else:
            raise ValueError(f'No supported JPEG/PNG input: {item}')
        paths.extend(found)
    unique = list(dict.fromkeys(p.resolve() for p in paths))
    if not unique:
        raise ValueError('No JPEG/PNG images found (folder scan is not recursive)')
    stems = [p.stem.casefold() for p in unique]
    if len(set(stems)) != len(stems):
        raise ValueError('Duplicate image stems would collide in outputs; rename or process separately')
    return unique


def load(path):
    path = Path(path)
    with Image.open(path) as raw:
        if raw.format not in {'JPEG', 'PNG'} or getattr(raw, 'n_frames', 1) != 1:
            raise ValueError(f'{path.name}: only still JPEG/PNG supported')
        # PNG IHDR bit depth; Pillow can silently down-convert 16-bit RGB.
        if raw.format == 'PNG':
            with path.open('rb') as handle:
                header = handle.read(25)
            if len(header) < 25 or header[24] != 8:
                raise ValueError(f'{path.name}: use an 8-bit PNG; high-bit-depth/indexed inputs need a dedicated workflow')
        if raw.mode not in {'RGB', 'RGBA', 'L', 'LA'}:
            raise ValueError(f'{path.name}: unsupported mode {raw.mode}; export an 8-bit sRGB photo first')
        profile = raw.info.get('icc_profile')
        oriented = ImageOps.exif_transpose(raw)
        if 'A' in oriented.getbands() and oriented.getchannel('A').getextrema() != (255, 255):
            raise ValueError(f'{path.name}: transparent background is not an exposed studio wall')
        if profile:
            try:
                im = ImageCms.profileToProfile(oriented.convert('RGB'), ImageCms.ImageCmsProfile(BytesIO(profile)), SRGB, outputMode='RGB')
            except Exception as exc:
                raise ValueError(f'{path.name}: could not convert embedded ICC profile to sRGB: {exc}') from exc
        else:
            im = oriented.convert('RGB')
        return np.asarray(im).copy(), {
            'source_format': raw.format,
            'encoded_dimensions': list(raw.size),
            'display_dimensions': list(im.size),
            'source_bytes': path.stat().st_size,
            'color_handling': 'embedded ICC converted to sRGB' if profile else 'untagged assumed sRGB',
        }


def save_png(rgb, path):
    Image.fromarray(rgb).save(path, icc_profile=SRGB_BYTES, compress_level=6)


def save_jpeg(rgb, path, quality):
    Image.fromarray(rgb).save(path, quality=quality, subsampling=0, optimize=True, icc_profile=SRGB_BYTES)
