"""
Functionality 4: similarity metrics and the Addition D hybrid score.
"""

from __future__ import annotations

import math

from irprint.models import Birthmark, CFGSignature, ComparisonResult

HYBRID_BOOST = 1.15        # CFG shapes agree  -> raise Dice by 15 %
HYBRID_PENALTY = 0.85      # CFG shapes differ -> lower Dice by 15 %
CFG_TOLERANCE = 0.25       # each CFG number may differ by up to 25 %
DEFAULT_THRESHOLD = 0.80   # hybrid score at or above this is flagged


def dice(a: set, b: set) -> float:
    """Dice = 2|A ∩ B| / (|A| + |B|)."""
    if not a and not b:
        return 1.0
    return 2 * len(a & b) / (len(a) + len(b))


def jaccard(a: set, b: set) -> float:
    """Jaccard = |A ∩ B| / |A ∪ B|."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def cosine(a: set, b: set) -> float:
    """Cosine over binary vectors = |A ∩ B| / sqrt(|A| * |B|)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def cfg_signature_close(sig_a: CFGSignature, sig_b: CFGSignature,
                        tolerance: float = CFG_TOLERANCE) -> bool:
    """
    True when blocks, edges and loop depth are EACH within the tolerance:
        abs(a - b) <= tolerance * max(a, b, 1)
    """
    for a, b in zip(sig_a.as_tuple(), sig_b.as_tuple()):
        if abs(a - b) > tolerance * max(a, b, 1):
            return False
    return True


# =====================================================================
# FUNCTIONALITY 4: Hybrid Similarity Scoring Engine (Addition D)
# =====================================================================
def hybrid_score(dice_value: float, cfg_match: bool) -> float:
    """
    Addition D hybrid score:
        cfg_match True  -> min(1.0, dice * 1.15)
        cfg_match False -> dice * 0.85
    """
    if cfg_match:
        return min(1.0, dice_value * HYBRID_BOOST)
    return dice_value * HYBRID_PENALTY


def compare_birthmarks(a: Birthmark, b: Birthmark, k: int = 3,
                       threshold: float = DEFAULT_THRESHOLD) -> ComparisonResult:
    """
    Compare two function birthmarks at one k. Keeps the raw Dice, Jaccard
    and Cosine values next to the hybrid score, so reports show both.
    """
    grams_a, grams_b = a.kgrams[k], b.kgrams[k]
    dice_value = dice(grams_a, grams_b)
    cfg_match = cfg_signature_close(a.cfg, b.cfg)
    hybrid = hybrid_score(dice_value, cfg_match)
    return ComparisonResult(
        file_a=a.source_path, func_a=a.function_name,
        file_b=b.source_path, func_b=b.function_name,
        k=k,
        dice=dice_value,
        jaccard=jaccard(grams_a, grams_b),
        cosine=cosine(grams_a, grams_b),
        cfg_a=a.cfg, cfg_b=b.cfg,
        cfg_match=cfg_match,
        hybrid_score=hybrid,
        flagged=hybrid >= threshold,
    )
