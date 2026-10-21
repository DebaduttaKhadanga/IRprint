"""
Addition A: cross-language clone detection (C <-> Rust).

Every C algorithm in corpus/algorithms/c is compared with every Rust
algorithm in corpus/algorithms/rust.
  * same algorithm, different language  -> positive pair (should score high)
  * different algorithm                 -> negative pair (should score low)

We report, for each k:
  * mean score of positive and negative pairs, and the gap between them
  * top-1 retrieval accuracy: for each C file, is its Rust twin the
    highest-scoring Rust file?
  * AUC: chance that a random positive pair outscores a random negative
and compare IRprint with a source-token baseline (MOSS/JPlag style).

Run:  python experiments/cross_language_eval.py
"""

from __future__ import annotations

from common import (C_DIR, KS, RUST_DIR, auc, load, mean, pair_scores, print_table,
                    token_dice, write_results)


# =====================================================================
# FUNCTIONALITY 5: Cross-Language Clone Bridging Benchmark (Addition A)
# =====================================================================
def run_cross_language_eval() -> dict:
    c_files = sorted(C_DIR.glob("*.c"))
    rust_files = {p.stem: p for p in sorted(RUST_DIR.glob("*.rs"))}
    names = [p.stem for p in c_files if p.stem in rust_files]

    results = {"k": {}}
    summary_rows = []
    for k in KS:
        scores = {}   # (c_name, rust_name) -> dict of method -> score
        for c_name in names:
            for r_name in names:
                c_path, r_path = C_DIR / f"{c_name}.c", rust_files[r_name]
                ir = pair_scores(load(c_path), load(r_path), k)
                scores[(c_name, r_name)] = {
                    "token_baseline": token_dice(c_path, r_path, k),
                    "irprint_dice": ir["dice"],
                    "irprint_hybrid": ir["hybrid"],
                }

        per_method = {}
        for method in ("token_baseline", "irprint_dice", "irprint_hybrid"):
            pos = [scores[(n, n)][method] for n in names]
            neg = [scores[(a, b)][method] for a in names for b in names if a != b]
            top1 = sum(
                max(names, key=lambda r: scores[(c, r)][method]) == c for c in names
            ) / len(names)
            per_method[method] = {
                "mean_positive": mean(pos), "mean_negative": mean(neg),
                "gap": mean(pos) - mean(neg), "top1_accuracy": top1,
                "auc": auc(pos, neg),
                "positives": {n: round(scores[(n, n)][method], 4) for n in names},
            }
            summary_rows.append([k, method, mean(pos), mean(neg),
                                 mean(pos) - mean(neg), top1, auc(pos, neg)])
        results["k"][k] = per_method

        if k == 3:
            rows = [[n, scores[(n, n)]["token_baseline"], scores[(n, n)]["irprint_dice"],
                     scores[(n, n)]["irprint_hybrid"]] for n in names]
            print_table(["algorithm (C vs Rust)", "token", "IR dice", "IR hybrid"], rows,
                        "Same-algorithm C<->Rust pairs at k=3")

    print_table(["k", "method", "mean pos", "mean neg", "gap", "top-1 acc", "AUC"], summary_rows,
                "Summary: positives = same algorithm across languages, negatives = different algorithms")
    return results


if __name__ == "__main__":
    write_results("cross_language", run_cross_language_eval())
