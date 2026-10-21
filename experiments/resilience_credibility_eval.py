"""
Addition D: Resilience and Credibility of k-gram-only vs hybrid k-gram+CFG.

Definitions (standard in software-birthmark literature):
  Resilience  = fraction of TRUE clone pairs scored >= threshold
                (true-positive rate; "does the birthmark survive transformation?")
  Credibility = 1 - false-positive rate on INDEPENDENT programs
                ("does the birthmark tell different programs apart?")

Positive (clone) pairs:
  * C original vs its Rust port                        (10 pairs, Addition A)
  * C original vs tier-1/2/3 LLM paraphrase            (18 pairs, Addition B)
Negative (independent) pairs:
  * different algorithms, C vs C                        (45 pairs)
  * different algorithms, C vs Rust                     (90 pairs)
  * paraphrase of algorithm X vs original of algorithm Y (90 pairs)

Both methods are scored on the same pairs:
  k-gram only : raw Dice
  hybrid      : Dice x 1.15 if CFG signatures match, x 0.85 otherwise

Run:  python experiments/resilience_credibility_eval.py
"""

from __future__ import annotations

import itertools

from common import (C_DIR, KS, PARAPHRASE_DIR, PARAPHRASED, RUST_DIR, auc, load,
                    pair_scores, print_table, write_results)

THRESHOLDS = [round(0.50 + 0.05 * i, 2) for i in range(9)]   # 0.50 ... 0.90
DEFAULT_THRESHOLD = 0.80


def build_pairs():
    """Return (positives, negatives) as lists of (label, path_a, path_b)."""
    names = sorted(p.stem for p in C_DIR.glob("*.c"))
    positives, negatives = [], []
    for n in names:
        positives.append((f"{n}: C vs Rust", C_DIR / f"{n}.c", RUST_DIR / f"{n}.rs"))
    for tier in ("tier1", "tier2", "tier3"):
        for n in PARAPHRASED:
            positives.append((f"{n}: original vs {tier}", C_DIR / f"{n}.c",
                              PARAPHRASE_DIR / tier / f"{n}.c"))

    for a, b in itertools.combinations(names, 2):
        negatives.append((f"{a} vs {b} (C/C)", C_DIR / f"{a}.c", C_DIR / f"{b}.c"))
    for a, b in itertools.permutations(names, 2):
        negatives.append((f"{a} vs {b} (C/Rust)", C_DIR / f"{a}.c", RUST_DIR / f"{b}.rs"))
    for tier in ("tier1", "tier2", "tier3"):
        for a in PARAPHRASED:
            for b in PARAPHRASED:
                if a != b:
                    negatives.append((f"{tier} {a} vs {b}", PARAPHRASE_DIR / tier / f"{a}.c",
                                      C_DIR / f"{b}.c"))
    return positives, negatives


def resilience(scores: list[float], threshold: float) -> float:
    return sum(s >= threshold for s in scores) / len(scores)


def credibility(scores: list[float], threshold: float) -> float:
    return 1 - sum(s >= threshold for s in scores) / len(scores)


# =====================================================================
# FUNCTIONALITY 4: Resilience / Credibility Evaluation (Addition D)
# =====================================================================
def run_resilience_credibility_eval() -> dict:
    positives, negatives = build_pairs()
    print(f"{len(positives)} clone pairs, {len(negatives)} independent pairs")
    results = {"n_positive": len(positives), "n_negative": len(negatives), "k": {}}

    summary = []
    for k in KS:
        pos = {"kgram": [], "hybrid": []}
        neg = {"kgram": [], "hybrid": []}
        for _, a, b in positives:
            s = pair_scores(load(a), load(b), k)
            pos["kgram"].append(s["dice"])
            pos["hybrid"].append(s["hybrid"])
        for _, a, b in negatives:
            s = pair_scores(load(a), load(b), k)
            neg["kgram"].append(s["dice"])
            neg["hybrid"].append(s["hybrid"])

        entry = {}
        for method in ("kgram", "hybrid"):
            sweep = {t: {"resilience": resilience(pos[method], t),
                         "credibility": credibility(neg[method], t)}
                     for t in THRESHOLDS}
            # best balanced operating point: maximise (R + C) / 2
            best_t = max(THRESHOLDS, key=lambda t: sweep[t]["resilience"] + sweep[t]["credibility"])
            entry[method] = {
                "sweep": sweep,
                "at_default": sweep[DEFAULT_THRESHOLD],
                "best_threshold": best_t,
                "best": sweep[best_t],
                "auc": auc(pos[method], neg[method]),
            }
            d, b = sweep[DEFAULT_THRESHOLD], sweep[best_t]
            summary.append([k, method, d["resilience"], d["credibility"],
                            best_t, b["resilience"], b["credibility"], auc(pos[method], neg[method])])
        results["k"][k] = entry

    print_table(["k", "method", f"R@{DEFAULT_THRESHOLD}", f"C@{DEFAULT_THRESHOLD}",
                 "best t", "R@best", "C@best", "AUC"], summary,
                "Resilience (R) and Credibility (C): k-gram only vs hybrid k-gram+CFG")

    k3 = results["k"][3]
    rows = [[t, k3["kgram"]["sweep"][t]["resilience"], k3["kgram"]["sweep"][t]["credibility"],
             k3["hybrid"]["sweep"][t]["resilience"], k3["hybrid"]["sweep"][t]["credibility"]]
            for t in THRESHOLDS]
    print_table(["threshold", "kgram R", "kgram C", "hybrid R", "hybrid C"], rows,
                "Threshold sweep at k=3")
    return results


if __name__ == "__main__":
    write_results("resilience_credibility", run_resilience_credibility_eval())
