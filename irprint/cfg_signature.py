"""
Functionality 3 (part 2): a 3-number summary of a function's control-flow
graph: (number of basic blocks, number of edges, loop-depth proxy).
"""

from __future__ import annotations

from irprint.ir_parser import branch_targets
from irprint.models import CFGSignature, Function


# =====================================================================
# FUNCTIONALITY 3: CFG Shape Signature Extractor
# =====================================================================
def compute_cfg_signature(func: Function) -> CFGSignature:
    """
    Walk every block's terminator and count:

      num_basic_blocks  - len(func.blocks)
      num_edges         - one edge per `label %X` target in br/switch/invoke
      max_loop_depth    - loop proxy built from back-edges. A back-edge is a
                          branch whose target block sits at an EARLIER OR
                          EQUAL position in the block order.
                          canonicalize_function() puts blocks in reverse
                          post-order, and in that order every retreating
                          edge is a loop back-edge. We count the DISTINCT
                          targets (loop headers), so a loop that jumps back
                          from two places (if/else both ending in
                          `continue`) still counts as one loop.

    BUG FIX (label resolution): canonicalize_function() renames bb.label to
    "bb0", "bb1", ... but the branch instructions still say `label %14`
    (the compiler's ORIGINAL name). So we build `label_order` from
    bb.original_label, NOT bb.label. Using bb.label would mean no target is
    ever found in label_order, and every loop would be missed (depth 0).
    """
    label_order = {bb.original_label or bb.label: index
                   for index, bb in enumerate(func.blocks)}

    num_edges = 0
    loop_headers: set[str] = set()
    for index, bb in enumerate(func.blocks):
        term = bb.terminator()
        if term is None:
            continue
        for target in branch_targets(term):
            num_edges += 1
            if target in label_order and label_order[target] <= index:
                loop_headers.add(target)      # back-edge found

    return CFGSignature(num_basic_blocks=len(func.blocks),
                        num_edges=num_edges,
                        max_loop_depth=len(loop_headers))
