"""
Addition C: compiler optimization-level drift and canonical -O0 extraction.

Problem: if birthmarks were taken from whatever optimization level a
student (or a build system) used, the SAME source would produce different
IR at -O0, -O1 and -O2, and similarity would drift.

Experiment:
  Part 1 (drift)      same source compiled at O0 / O1 / O2; Dice between levels.
  Part 2 (canonical)  IRprint ignores the submitter's level and always
                      re-extracts at -O0 from source, so same source -> Dice 1.000.
  Part 3 (clones)     original vs tier-1 paraphrase when the two sides were
                      compiled at different levels, vs both at canonical -O0.

Run:  python experiments/optimization_level_eval.py
"""

from __future__ import annotations

from common import (C_DIR, KS, PARAPHRASE_DIR, PARAPHRASED, load, mean,
                    pair_scores, print_table, write_results)

LEVELS = ("O0", "O1", "O2")
LEVEL_PAIRS = (("O0", "O1"), ("O0", "O2"), ("O1", "O2"))
# Each corpus file holds exactly one function, so compare it whatever its
# size: optimized code can shrink below the class-scan minimum (gcd at -O1
# is only 9 opcodes).
ALL = 1


def scores(a, b, k):
    return pair_scores(a, b, k, min_opcodes=ALL)["dice"]


# =====================================================================
# FUNCTIONALITY 7: Optimization-Level Drift & Canonical -O0 Study (Addition C)
# =====================================================================
def run_optimization_eval(k: int = 3) -> dict:
    programs = sorted(p.stem for p in C_DIR.glob("*.c"))
    results = {"k": k, "drift": {}, "canonical": {}, "clone_pairs": {}}

    # Part 1 + 2: same source at different levels vs canonical O0
    rows = []
    for name in programs:
        path = C_DIR / f"{name}.c"
        drift = {f"{a}-vs-{b}": scores(load(path, a), load(path, b), k)
                 for a, b in LEVEL_PAIRS}
        canonical = scores(load(path, "O0"), load(path, "O0"), k)
        results["drift"][name] = drift
        results["canonical"][name] = canonical
        rows.append([name, *drift.values(), canonical])
    rows.append(["MEAN", *(mean([r[i] for r in rows]) for i in range(1, 5))])
    print_table(["program", "O0 vs O1", "O0 vs O2", "O1 vs O2", "IRprint canonical O0"], rows,
                f"Part 1+2: same source, Dice at k={k}")

    # Part 3: real clone pairs, mixed levels vs canonical
    rows = []
    for name in PARAPHRASED:
        orig = C_DIR / f"{name}.c"
        clone = PARAPHRASE_DIR / "tier1" / f"{name}.c"
        mixed = {f"{a}-vs-{b}": scores(load(orig, a), load(clone, b), k)
                 for a, b in (("O0", "O2"), ("O2", "O0"), ("O1", "O2"))}
        canonical = scores(load(orig, "O0"), load(clone, "O0"), k)
        results["clone_pairs"][name] = {**mixed, "canonical_O0": canonical}
        rows.append([name, *mixed.values(), canonical])
    rows.append(["MEAN", *(mean([r[i] for r in rows]) for i in range(1, 5))])
    print_table(["clone pair (orig vs tier1)", "O0 vs O2", "O2 vs O0", "O1 vs O2",
                 "IRprint canonical O0"], rows,
                f"Part 3: original vs renamed clone, Dice at k={k}")

    # Drift across every k, for the paper table
    results["mean_drift_by_k"] = {}
    for kk in KS:
        per_pair = {}
        for a, b in LEVEL_PAIRS:
            per_pair[f"{a}-vs-{b}"] = mean([
                scores(load(C_DIR / f"{n}.c", a), load(C_DIR / f"{n}.c", b), kk)
                for n in programs])
        results["mean_drift_by_k"][kk] = per_pair
    print_table(["k", *results["mean_drift_by_k"][KS[0]].keys(), "canonical"],
                [[kk, *v.values(), 1.0] for kk, v in results["mean_drift_by_k"].items()],
                "Mean same-source Dice across optimization levels, by k")
    return results


if __name__ == "__main__":
    write_results("optimization_level", run_optimization_eval())
