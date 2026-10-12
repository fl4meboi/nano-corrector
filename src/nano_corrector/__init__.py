"""nano-corrector: white-balance a batch of AI-generated images to a shared neutral baseline."""
from .engine import (  # noqa: F401
    Anchor,
    apply_curve,
    apply_gains,
    choose_baseline,
    find_neutral_anchor,
    gains_for,
    lab_of_linear,
    cond_curve,
    cond_profile,
    cond_reference,
)
