"""
Functionality 3 (part 1): opcode k-gram birthmarks.

A "birthmark" is a fingerprint of a function that survives cosmetic edits.
We slide a window of size k over the function's opcode sequence and keep
the set of k-grams. Example, k = 3:

    opcodes:  alloca store load icmp br
    3-grams:  (alloca, store, load) (store, load, icmp) (load, icmp, br)
"""

from __future__ import annotations

from irprint.cfg_signature import compute_cfg_signature
from irprint.ir_parser import normalized_ir_text
from irprint.models import Birthmark, Function

DEFAULT_KS = (2, 3, 4, 5)


def extract_kgrams(opcodes: list[str], k: int) -> set[tuple[str, ...]]:
    """
    Set of all length-k windows over the opcode list.
    A sequence shorter than k gives one k-gram containing the whole
    sequence, so very short functions still have a fingerprint.
    """
    if not opcodes:
        return set()
    if len(opcodes) < k:
        return {tuple(opcodes)}
    return {tuple(opcodes[i:i + k]) for i in range(len(opcodes) - k + 1)}


# =====================================================================
# FUNCTIONALITY 3: Multi-k Opcode Birthmark Extractor
# =====================================================================
def build_birthmark(func: Function, ks: tuple[int, ...] = DEFAULT_KS) -> Birthmark:
    """
    Build the full fingerprint of one canonicalized function:
      - k-gram sets for every k in ks (default 2, 3, 4, 5)
      - its CFGSignature (blocks, edges, loop proxy)
      - normalized IR text for the dashboard diff view
    """
    opcodes = func.opcode_sequence()
    return Birthmark(
        function_name=func.name,
        source_path=func.source_path,
        language=func.language,
        kgrams={k: extract_kgrams(opcodes, k) for k in ks},
        cfg=compute_cfg_signature(func),
        opcode_count=len(opcodes),
        normalized_ir=normalized_ir_text(func),
    )
