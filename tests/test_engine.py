import numpy as np
from nano_corrector import engine as E


def scene(cast=(1.0, 1.0, 1.0), seed=0):
    """Gray studio wall + cream trousers + red hat, then a linear-light channel cast."""
    rng = np.random.default_rng(seed)
    h, w = 400, 300
    lin = np.full((h, w, 3), 0.80, np.float32)               # neutral wall
    lin[250:, :, :] = 0.84                                    # floor, slightly brighter
    lin[120:380, 100:170] = np.array([0.72, 0.64, 0.45])      # cream trousers
    lin[20:70, 120:160] = np.array([0.55, 0.02, 0.03])        # red hat
    lin += rng.normal(0, 0.002, lin.shape).astype(np.float32)
    lin = np.clip(lin * np.array(cast, np.float32), 0, 1)
    return np.clip(E.linear_to_srgb(lin) * 255 + 0.5, 0, 255).astype(np.uint8)


def test_anchor_finds_wall_not_trousers():
    an = E.find_neutral_anchor(scene())
    assert an.reliable
    assert abs(an.lab[1]) < 0.5 and abs(an.lab[2]) < 0.5


def test_magenta_cast_is_removed():
    clean = scene()
    bad = scene(cast=(1.0, 0.93, 1.0))
    a_clean, a_bad = E.find_neutral_anchor(clean), E.find_neutral_anchor(bad)
    assert E.delta_ab(a_clean.lab, a_bad.lab) > 3
    g = E.gains_for(a_bad.lin_rgb, E.chromaticity(a_clean.lin_rgb))
    fixed = (E.apply_gains(bad, g) * 255 + 0.5).astype(np.uint8)
    assert E.delta_ab(a_clean.lab, E.find_neutral_anchor(fixed).lab) < 0.5


def test_gains_preserve_anchor_luminance():
    w = np.array([0.83, 0.74, 0.80])
    g = E.gains_for(w, E.chromaticity([0.80, 0.80, 0.80]))
    y = np.array([0.2126, 0.7152, 0.0722])
    assert abs((y * w * g).sum() - (y * w).sum()) < 1e-4


def test_neutral_most_baseline_ignores_drifted_majority():
    imgs = [scene((1, 1, 1))] + [scene((1.0, 0.94, 1.0), seed=s) for s in range(1, 6)]
    anchors = [E.find_neutral_anchor(i) for i in imgs]
    target, how, group = E.choose_baseline(anchors, "neutral-most")
    # consensus would adopt the magenta majority; neutral-most must stay near neutral
    assert np.allclose(target, [1 / 3] * 3, atol=0.004), how


def test_no_surface_is_flagged_unreliable():
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)
    assert not E.find_neutral_anchor(noise).reliable


def test_cond_curve_removes_shadow_magenta_but_leaves_wall():
    """Red/blue excess that grows toward the darks: the curve must remove it from the dark tones
    without moving the bright wall (a single wall gain could not do both)."""
    h, w = 300, 300
    ramp = np.linspace(0.02, 0.85, w, dtype=np.float32)[None, :].repeat(h, 0)
    clean_lin = np.stack([ramp, ramp, ramp], -1)
    s = 1 + 0.25 * (1 - np.sqrt(ramp))
    cast_lin = clean_lin.copy(); cast_lin[..., 0] *= s; cast_lin[..., 2] *= s
    q = lambda x: np.clip(E.linear_to_srgb(np.clip(x, 0, 1)) * 255 + 0.5, 0, 255).astype(np.uint8)
    clean, bad = q(clean_lin), q(cast_lin)
    ref = E.cond_reference([E.cond_profile(clean)])
    ys, gs = E.cond_curve(E.cond_profile(bad), ref)
    fixed = (E.apply_curve(bad, ys, gs) * 255 + 0.5).astype(np.uint8)
    dark = slice(0, 90)
    tint = lambda im, sl: float(np.abs(im[:, sl, 0].astype(float) - im[:, sl, 1]).mean())
    assert tint(bad, dark) > 3 and tint(fixed, dark) < tint(bad, dark) * 0.35
    assert np.abs(fixed[:, 250:].astype(int) - clean[:, 250:].astype(int)).mean() < 2.0


def test_highlight_protection_preserves_cream_and_white():
    im = scene(cast=(1, .93, 1))
    ys = np.array([.02, .1, .3, .8], np.float32)
    gs = np.array([[.8, 1.07, .85]] * 4, np.float32)
    ys, gs = E.protect_highlights(ys, gs)
    out = np.rint(E.apply_curve(im, ys, gs) * 255).astype(np.uint8)
    # Both the white wall and cream garment are already bright enough to pass through.
    assert np.array_equal(out[:10], im[:10])
    assert np.array_equal(out[260:350, 110:160], im[260:350, 110:160])
    # Deep neutral tones still receive the correction.
    dark = np.full((10, 10, 3), 60, np.uint8)
    fixed = E.apply_curve(dark, ys, gs)
    assert fixed[0, 0, 1] > fixed[0, 0, 0]
