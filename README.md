# IRprint: Language-Agnostic, Optimization-Robust Code Plagiarism Detection via LLVM Intermediate Representation Birthmarking

> **Development Notice:** No work is permitted on the main branch. All development is conducted on dedicated developer branch (dev) and will be merged only upon final project completion.

IRprint compiles C, C++, Rust and Swift submissions to LLVM IR at a fixed
`-O0`, normalizes the IR, and compares functions using opcode k-gram
birthmarks combined with a control-flow-graph shape signature.

- **How it works, step by step:** [`flow.md`](flow.md)
- **Why it is built this way (and its limitations):** [`decision.md`](decision.md)

## Setup

Requirements: Python 3.11+, `clang`/`clang++`, and `rustc` (optionally `swiftc`).

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
irprint doctor            # shows which compilers were found
```

No root access? Both compilers can be installed per-user:

```bash
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal        # rustc -> ~/.cargo/bin
# clang from conda-forge into ~/.local/llvm-env (IRprint looks there automatically)
mkdir -p ~/.local/micromamba
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C ~/.local/micromamba bin/micromamba
~/.local/micromamba/bin/micromamba create -y -p ~/.local/llvm-env -c conda-forge clang clangxx
```

Or use Docker: `docker build -t irprint . && docker run --rm -p 8000:8000 irprint`.

## Live demo script

```bash
# 1. CLI scan of a class (C, Rust and C++ submissions)
irprint scan experiments/corpus/class_demo --json-out class_report.json

# 2. The four research experiments (all offline, ~10 s each)
python experiments/cross_language_eval.py          # Addition A: C <-> Rust
python experiments/llm_paraphrase_eval.py          # Addition B: 3-tier paraphrasing
python experiments/optimization_level_eval.py      # Addition C: -O0/-O1/-O2 drift
python experiments/resilience_credibility_eval.py  # Addition D: k-gram vs hybrid

# 3. Instructor dashboard -> http://127.0.0.1:8000
irprint serve
#    click "Scan built-in demo class", then click any heat-map cell or flagged pair

# 4. Tests
pytest
```

Live LLM paraphrasing (optional, needs network): `pip install anthropic`,
set `ANTHROPIC_API_KEY`, then `python experiments/llm_paraphrase_eval.py --live`.

## Layout

| Path | Purpose |
|------|---------|
| `irprint/compiler_wrapper.py` | Functionality 1: source → LLVM IR |
| `irprint/normalizer.py`, `irprint/ir_parser.py` | Functionality 2: clean, parse, canonicalize IR |
| `irprint/birthmark.py`, `irprint/cfg_signature.py` | Functionality 3: k-gram birthmarks + CFG signature |
| `irprint/similarity.py` | Functionality 4: Dice/Jaccard/Cosine + hybrid score |
| `irprint/pipeline.py`, `irprint/cli.py`, `irprint/db/`, `irprint/api/`, `dashboard/` | Functionality 8: scan, CLI, SQLite, web dashboard |
| `experiments/` | Functionalities 4–7: Additions A–D and their corpora |
| `tests/` | pytest suite |
