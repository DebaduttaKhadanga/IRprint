import math

import pytest

from irprint.models import Birthmark, CFGSignature
from irprint.similarity import (cfg_signature_close, compare_birthmarks, cosine, dice,
                                hybrid_score, jaccard)

A = {("a",), ("b",), ("c",)}
B = {("b",), ("c",), ("d",)}


def test_set_metrics():
    assert dice(A, B) == pytest.approx(2 * 2 / 6)
    assert jaccard(A, B) == pytest.approx(2 / 4)
    assert cosine(A, B) == pytest.approx(2 / math.sqrt(9))
    assert dice(A, A) == jaccard(A, A) == cosine(A, A) == 1.0
    assert dice(A, set()) == 0.0


def test_cfg_signature_close_tolerance():
    base = CFGSignature(8, 10, 2)
    assert cfg_signature_close(base, CFGSignature(9, 11, 2))       # within 25 %
    assert not cfg_signature_close(base, CFGSignature(4, 10, 2))   # blocks differ too much
    assert not cfg_signature_close(base, CFGSignature(8, 10, 0))   # loops differ
    assert cfg_signature_close(CFGSignature(1, 0, 0), CFGSignature(1, 0, 0))


def test_hybrid_boost_and_penalty():
    assert hybrid_score(0.6, True) == pytest.approx(0.69)
    assert hybrid_score(0.9, True) == 1.0                    # capped
    assert hybrid_score(0.6, False) == pytest.approx(0.51)


def _bm(name, grams, cfg):
    return Birthmark(name, f"{name}.c", "c", {3: grams}, cfg, opcode_count=20)


def test_compare_birthmarks_keeps_raw_metrics():
    r = compare_birthmarks(_bm("x", A, CFGSignature(4, 4, 1)),
                           _bm("y", B, CFGSignature(4, 4, 1)), k=3, threshold=0.7)
    assert r.dice == pytest.approx(2 / 3)
    assert r.cfg_match is True
    assert r.hybrid_score == pytest.approx(min(1.0, 2 / 3 * 1.15))
    assert r.flagged is True
    d = r.to_dict()
    assert {"dice", "jaccard", "cosine", "hybrid_score", "cfg_a", "cfg_b"} <= set(d)
