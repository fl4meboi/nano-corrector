"""Portable unittest suite; synthetic fixtures only, no private photos required."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import cv2
import numpy as np
from PIL import Image, ImageCms

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from nano_core.background import apply_background, fit_background
from nano_core.io import load


def photo(cast=True):
    lab = np.zeros((400, 300, 3), np.float32)
    lab[..., 0] = 91
    lab[..., 1] = np.linspace(1, 3, 300) if cast else .15
    lab[..., 2] = 2 if cast else .6
    rgb = np.rint(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)*255).astype(np.uint8)
    rgb[100:350, 100:200] = [170, 20, 25]
    return rgb


class EngineTests(unittest.TestCase):
    def test_spatial_tint_match_and_subject_preservation(self):
        rgb = photo()
        anchor, coeff, _ = fit_background(rgb)
        target = np.array([92, .15, .6])
        out, limited = apply_background(rgb, anchor.lab, coeff, target)
        lab = cv2.cvtColor(out.astype(np.float32)/255, cv2.COLOR_RGB2Lab)
        self.assertLess(np.abs(np.median(lab[:80], axis=(0, 1))-target).max(), .5)
        self.assertTrue(np.array_equal(out[100:350, 100:200], rgb[100:350, 100:200]))
        self.assertEqual(limited, 0)

    def test_pure_white_retained(self):
        rgb = np.full((200, 200, 3), 255, np.uint8); rgb[:100] = [228, 225, 224]
        out, _ = apply_background(rgb, np.array([90, 1, 1]), np.array([[1,0,0,0,0,0],[1,0,0,0,0,0]]), np.array([92,.15,.6]))
        self.assertTrue(np.array_equal(rgb[100:], out[100:]))


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nano skill test ')
        self.root = Path(self.tmp.name)
        self.source = self.root/'photos with spaces'; self.source.mkdir()
        self.ref = self.root/'trusted.png'; Image.fromarray(photo(False)).save(self.ref)
        self.out = self.root/'new output'

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *extra, code=0):
        cmd = [sys.executable, str(ROOT/'scripts/match_backgrounds.py'), str(self.source), '--reference', str(self.ref), '--out', str(self.out), *extra]
        result = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout+'\n'+result.stderr)
        return result

    def add_photo(self, name='arbitrary-name.png'):
        path = self.source/name; Image.fromarray(photo()).save(path); return path

    def test_arbitrary_batch_external_reference_jpeg_pagination_and_inputs_unchanged(self):
        for i in range(13): self.add_photo(f'photo-{i:02d}.png')
        (self.source/'notes.txt').write_text('not an image')
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir()}
        self.run_cli('--jpeg', '--focus', 'photo-00', 'photo-12')
        report = json.loads((self.out/'report.json').read_text())
        self.assertEqual(len(report['images']), 13)
        self.assertEqual(len(report['review_sheets']), 3)
        self.assertEqual(report['status'], 'export_complete_visual_review_required')
        self.assertTrue((self.out/'review/reference.png').exists())
        self.assertEqual(len(list((self.out/'jpeg').glob('*.jpg'))), 13)
        self.assertEqual(report['summary']['fixed_patches']['upper_left']['images_measured'], 13)
        self.assertLess(report['summary']['fixed_patches']['upper_left']['after_mean_tint_distance_to_reference'], .6)
        for p in self.source.iterdir(): self.assertEqual(hashes[p.name], hashlib.sha256(p.read_bytes()).hexdigest())

    def test_dry_run_writes_nothing(self):
        self.add_photo(); self.run_cli('--dry-run'); self.assertFalse(self.out.exists())

    def test_reference_pass_through_and_single_image_sheet(self):
        p = self.source/'reference-copy.png'; p.write_bytes(self.ref.read_bytes())
        result = subprocess.run([sys.executable, str(ROOT/'scripts/match_backgrounds.py'), str(p), '--reference', str(p), '--out', str(self.out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(np.array_equal(np.array(Image.open(p)), np.array(Image.open(self.out/'reference-copy_wb.png'))))
        self.assertTrue((self.out/'review/before-after-01.png').exists())

    def test_existing_output_refused(self):
        self.add_photo(); self.out.mkdir(); sentinel = self.out/'keep.txt'; sentinel.write_text('keep')
        self.run_cli(code=2); self.assertEqual(sentinel.read_text(), 'keep')

    def test_duplicate_stems_refused_before_writing(self):
        self.add_photo('same.png'); self.add_photo('same.jpg'); self.run_cli(code=2); self.assertFalse(self.out.exists())

    def test_transparency_refused_before_writing(self):
        Image.new('RGBA', (300,400), (230,230,230,0)).save(self.source/'transparent.png')
        self.run_cli(code=2); self.assertFalse(self.out.exists())

    def test_high_bit_depth_refused(self):
        Image.fromarray(np.full((400,300),60000,np.uint16)).save(self.source/'16bit.png')
        self.run_cli(code=2); self.assertFalse(self.out.exists())

    def test_unreliable_wall_refused(self):
        Image.new('RGB',(300,400),(170,20,25)).save(self.source/'red.png')
        self.run_cli(code=2); self.assertFalse(self.out.exists())

    def test_exif_orientation_is_applied(self):
        p=self.source/'oriented.jpg'; exif=Image.Exif(); exif[274]=6
        Image.fromarray(photo()).save(p,exif=exif)
        rgb,meta=load(p)
        self.assertEqual(meta['encoded_dimensions'],[300,400])
        self.assertEqual(meta['display_dimensions'],[400,300])
        self.assertEqual(rgb.shape,(300,400,3))

    def test_invalid_patches_refused(self):
        self.add_photo(); patches=self.root/'patches.json'; patches.write_text('[{"name":"oops","box":[0.8,0.1,0.2,0.2]}]')
        self.run_cli('--patches',str(patches),code=2); self.assertFalse(self.out.exists())

    def test_embedded_srgb_profile(self):
        p=self.source/'tagged.png'
        profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        original=photo(); Image.fromarray(original).save(p,icc_profile=profile)
        rgb,meta=load(p)
        self.assertTrue(np.array_equal(original,rgb))
        self.assertEqual(meta['color_handling'],'embedded ICC converted to sRGB')

    def test_invalid_color_profile_refused(self):
        p=self.source/'bad-profile.png'
        Image.fromarray(photo()).save(p,icc_profile=b'not an ICC profile')
        self.run_cli(code=2); self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
