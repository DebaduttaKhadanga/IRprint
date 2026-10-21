"""
Addition B: robustness to LLM paraphrasing (3-tier protocol).

  Tier 1: identifier renaming + formatting
  Tier 2: control-flow reversal + for <-> while conversion
  Tier 3: structural expression rewriting

For each tier and each k in {2,3,4,5} we score original vs paraphrase with
IRprint (raw Dice and hybrid) and with the source-token baseline. As a
control we also score each paraphrase against the OTHER originals, which
should stay low.

Two modes:
  offline (default)  uses the pre-generated files in corpus/llm_paraphrase/
  --live             asks Claude to paraphrase the originals right now.
                     Needs `pip install anthropic` and ANTHROPIC_API_KEY.

Run:  python experiments/llm_paraphrase_eval.py [--live] [--model claude-opus-5-5]
"""

from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from common import (C_DIR, KS, PARAPHRASE_DIR, PARAPHRASED, auc, load, mean,
                    pair_scores, print_table, token_dice, write_results)

TIERS = ("tier1", "tier2", "tier3")
DEFAULT_THRESHOLD = 0.80

TIER_INSTRUCTIONS = {
    "tier1": "Rename every function, parameter and local variable, and change the "
             "comments and code formatting. Do not change any logic or control flow.",
    "tier2": "Rename identifiers, convert every for loop to a while loop (or the "
             "reverse), and reverse conditions (negate if-conditions and swap the "
             "branches, use continue/break differently). Keep the same algorithm.",
    "tier3": "Rewrite the code structurally: use pointer arithmetic instead of "
             "indexing where possible, use ternary expressions, extract small helper "
             "functions, rewrite arithmetic expressions into equivalent forms. "
             "Keep the same algorithm and the same public function signature types.",
}


# =====================================================================
# FUNCTIONALITY 6: Live LLM Paraphrase Generation (Claude API)
# =====================================================================
def generate_live_paraphrases(out_dir: Path, model: str) -> None:
    """
    Ask Claude for tier 1/2/3 paraphrases of each original C file and write
    them to out_dir/<tier>/<name>.c. Uses the official Anthropic SDK.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("--live needs the anthropic package: pip install anthropic") from exc

    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY (or an `ant auth` profile)
    for tier in TIERS:
        (out_dir / tier).mkdir(parents=True, exist_ok=True)
        for name in PARAPHRASED:
            original = (C_DIR / f"{name}.c").read_text()
            prompt = (
                "You are helping build a plagiarism-detection benchmark. "
                f"{TIER_INSTRUCTIONS[tier]}\n\n"
                "Return only one complete, compilable C file in a single ```c code block, "
                "with no main() function and no #include lines.\n\n"
                f"```c\n{original}```"
            )
            try:
                response = client.beta.messages.create(
                    model=model,
                    max_tokens=16000,
                    output_config={"effort": "low"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    messages=[{"role": "user", "content": prompt}],
                )
            except anthropic.AuthenticationError as exc:
                raise SystemExit("Claude API: invalid or missing ANTHROPIC_API_KEY") from exc
            except anthropic.RateLimitError as exc:
                raise SystemExit("Claude API: rate limited, try again later") from exc
            except anthropic.APIStatusError as exc:
                raise SystemExit(f"Claude API error {exc.status_code}: {exc.message}") from exc
            except anthropic.APIConnectionError as exc:
                raise SystemExit("Claude API: network error") from exc

            if response.stop_reason == "refusal":
                raise SystemExit(f"Claude declined to paraphrase {name} ({tier})")
            text = "".join(b.text for b in response.content if b.type == "text")
            match = re.search(r"```(?:c)?\n(.*?)```", text, re.S)
            code = match.group(1) if match else text
            (out_dir / tier / f"{name}.c").write_text(code)
            print(f"  generated {tier}/{name}.c")


# =====================================================================
# FUNCTIONALITY 6: LLM-Paraphrasing Robustness Benchmark (Addition B)
# =====================================================================
def run_paraphrase_eval(paraphrase_dir: Path, threshold: float = DEFAULT_THRESHOLD) -> dict:
    results = {"source": str(paraphrase_dir), "threshold": threshold, "tiers": {}}
    rows = []
    for tier in TIERS:
        results["tiers"][tier] = {}
        for k in KS:
            pos = {"token": [], "dice": [], "hybrid": []}
            neg = {"token": [], "dice": [], "hybrid": []}
            for name in PARAPHRASED:
                para_path = paraphrase_dir / tier / f"{name}.c"
                for other in PARAPHRASED:
                    orig_path = C_DIR / f"{other}.c"
                    ir = pair_scores(load(orig_path), load(para_path), k)
                    bucket = pos if other == name else neg
                    bucket["token"].append(token_dice(orig_path, para_path, k))
                    bucket["dice"].append(ir["dice"])
                    bucket["hybrid"].append(ir["hybrid"])

            entry = {}
            for method in ("token", "dice", "hybrid"):
                detected = sum(v >= threshold for v in pos[method]) / len(pos[method])
                entry[method] = {
                    "mean_positive": mean(pos[method]),
                    "mean_negative": mean(neg[method]),
                    "detection_rate": detected,
                    "auc": auc(pos[method], neg[method]),
                    "per_program": dict(zip(PARAPHRASED, (round(v, 4) for v in pos[method]))),
                }
            results["tiers"][tier][k] = entry
            rows.append([tier, k,
                         entry["token"]["mean_positive"], entry["dice"]["mean_positive"],
                         entry["hybrid"]["mean_positive"], entry["hybrid"]["mean_negative"],
                         entry["hybrid"]["detection_rate"], entry["token"]["auc"],
                         entry["hybrid"]["auc"]])

    print_table(["tier", "k", "token pos", "IR dice pos", "IR hybrid pos", "IR hybrid neg",
                 f"detect@{threshold}", "token AUC", "hybrid AUC"], rows,
                "Original vs paraphrase (pos) and paraphrase vs other originals (neg)")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true",
                        help="generate fresh paraphrases with the Claude API")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    if args.live:
        with tempfile.TemporaryDirectory(prefix="irprint_live_") as tmp:
            print(f"Generating live paraphrases with {args.model} ...")
            generate_live_paraphrases(Path(tmp), args.model)
            results = run_paraphrase_eval(Path(tmp), args.threshold)
            results["mode"] = "live"
            results["model"] = args.model
            write_results("llm_paraphrase_live", results)
    else:
        print("Offline mode: using pre-generated corpus in experiments/corpus/llm_paraphrase/")
        results = run_paraphrase_eval(PARAPHRASE_DIR, args.threshold)
        results["mode"] = "offline"
        write_results("llm_paraphrase", results)


if __name__ == "__main__":
    main()
