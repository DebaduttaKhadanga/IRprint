# IRprint — Engineering Decision Log

This file explains **why** IRprint is built the way it is. Every teammate
should be able to answer a "why did you do X?" question from the professor
using this file. Each decision has five parts:

- **Decision** — what we did
- **Plain-English explanation** — the idea, without jargon
- **Why we chose it**
- **Alternatives rejected**
- **Limitations to state in the paper**

All numbers quoted below come from the scripts in `experiments/` (results
saved in `experiments/results/*.json`) on our machine: clang 23.1.3,
rustc 1.99.1, Python 3.11. Re-running the scripts on another toolchain will
give slightly different values.

---

## Decision 1 — Fingerprint LLVM IR, not source code, ASTs, or Java bytecode

**Decision.** IRprint compiles every submission to LLVM IR and builds its
fingerprints ("birthmarks") from the IR instructions.

**Plain-English explanation.** Tools like MOSS and JPlag compare the *text*
(tokens) or the *syntax tree* of the source code. If a student renames
variables, reformats, or swaps a `for` loop for a `while` loop, those tools
see a different program. LLVM IR is what the compiler turns the program
into *before* it becomes machine code. Many surface changes disappear at
that level: variable names become anonymous registers, `for` and `while`
both become "compare, branch, jump back". And because clang (C/C++), rustc
(Rust) and swiftc (Swift) all produce LLVM IR, one fingerprint format
works across languages.

**Why we chose it.**
- One representation for C, C++, Rust and Swift (cross-language detection).
- Identifier renaming has zero effect: tier-1 paraphrases score Dice 1.000
  at every k (Addition B).
- `for`/`while` and condition reversal mostly disappear: tier-2 paraphrases
  score mean hybrid 1.000 at k=3, against 0.656 for the token baseline.
- The Java-bytecode birthmark study we build on (arXiv:2607.03014, as cited
  in our project brief) showed that compiled-code birthmarks resist LLM
  paraphrasing. Bytecode only covers JVM languages; LLVM IR covers the
  systems languages taught in our courses.

**Alternatives rejected.**
- *Source tokens (MOSS/JPlag style).* We implemented a simplified version as
  the baseline (`experiments/common.py: source_tokens`). It breaks under
  restructuring (tier-2 mean 0.656 at k=3), and its absolute scores across
  languages are low (mean 0.283 for true C↔Rust pairs at k=3).
- *ASTs.* Each language has a different AST, so cross-language comparison
  would need a hand-written mapping per language pair.
- *Java bytecode.* Not available for C/C++/Rust.
- *Machine code / assembly.* Depends on the target CPU and the register
  allocator; much noisier than IR.

**Limitations to state in the paper.**
- Code that does not compile cannot be fingerprinted (the CLI reports it as
  FAILED).
- **Ranking across languages is not better than tokens on our corpus.** On
  the 10-algorithm C↔Rust set the token baseline has AUC 0.971 and top-1
  accuracy 0.9 at k=3, against AUC 0.912 and top-1 0.8 for the IRprint
  hybrid. Our Rust files were written to mirror the C structure, which
  favours a token matcher. IRprint's advantage is the *absolute* level:
  true pairs score 0.718 (hybrid), not 0.283, so a fixed threshold can work
  across languages, and the positive–negative gap is larger (0.338 vs 0.178).
- Tier-3 rewrites (helper extraction, pointer arithmetic) drop IRprint to a
  mean hybrid of 0.619 at k=3, and 0 of 6 are detected at threshold 0.8.
  The token baseline ranks tier-3 slightly better (AUC 0.961 vs 0.900).
- The corpus is small (10 algorithms, 6 paraphrased) and written by us. It
  is a proof of concept, not a benchmark result.

---

## Decision 2 — `-Xclang -disable-O0-optnone` for clang, `--crate-type=lib` (and friends) for rustc

**Decision.** C/C++ are compiled with
`clang -S -emit-llvm -O0 -g0 -Xclang -disable-O0-optnone`. Rust is compiled
with
`rustc --emit=llvm-ir --crate-type=lib -C opt-level=0 -C debuginfo=0 -C overflow-checks=off -C panic=abort`.
Swift uses `swiftc -emit-ir -Onone -parse-as-library`.
See `irprint/compiler_wrapper.py: build_command`.

**Plain-English explanation.**
- At `-O0`, clang marks every function `optnone` ("never optimize this").
  `-disable-O0-optnone` removes that mark, so the IR is a normal, un-pinned
  `-O0` module. That makes our IR identical to what you would hand to `opt`
  if you later want to run a cleanup pass (e.g. `mem2reg`), and the IR has
  no attribute that differs from function to function.
- `--crate-type=lib` tells rustc "this is a library". Student files often
  have no `fn main()`, and a binary crate without `main` fails to compile.
  A library crate compiles without one. (Only `pub fn` items are emitted, so
  student Rust functions must be `pub`; all our fixtures are.)
- `overflow-checks=off`: in debug mode rustc adds an "add with overflow,
  panic if it overflowed" branch after every `+`, `-`, `*`. C has no such
  check. Turning it off removes a large source of fake C↔Rust difference.
- `panic=abort`: removes unwinding landing pads (`invoke`/`landingpad`)
  that C code never has.
- `-g0` / `debuginfo=0`: no debug info to strip in the first place.

**Why we chose it.** Every one of these flags removes compiler- or
language-specific noise that says nothing about the student's algorithm.

**Alternatives rejected.**
- Compiling Rust as a binary: fails on files without `main`.
- Keeping overflow checks and filtering them later: possible, but the
  pattern (`llvm.sadd.with.overflow` + `extractvalue` + branch) is spread
  over several blocks and much harder to remove reliably than a flag.

**Limitations to state in the paper.**
- Generic Rust functions are not emitted until they are instantiated, and
  private unused functions are dropped by rustc. Only public, concrete
  functions are fingerprinted.
- Turning off overflow checks means we fingerprint slightly different code
  from what `cargo build` produces in debug mode. Both are valid
  compilations of the same source.
- Swift support is implemented but untested on our machine (swiftc was not
  installed).

---

## Decision 3 — A small line-oriented regex parser instead of `llvmlite` or the LLVM C++ API

**Decision.** `irprint/ir_parser.py` reads textual `.ll` files line by line
with a handful of regular expressions.

**Plain-English explanation.** Textual LLVM IR is very regular:
`define ... @name(...) {` starts a function, a line like `14:` starts a
basic block, `}` ends the function, and every other line is one
instruction whose first word (after `%x =`) is the opcode. That is
enough structure to recover functions, blocks, instructions and branch
targets. The only multi-line instruction we need is `switch`, which
`_join_multiline_instructions` glues back into one line.

**Why we chose it.**
- **Version independence.** We used clang 23 and rustc 1.99 (which ships
  its own LLVM). `llvmlite` binds to one specific LLVM version and refuses
  IR written by a newer one. A text parser accepts IR from any of them.
- **No native dependencies.** `pip install` works anywhere; no LLVM
  development headers.
- **Explainability.** The whole parser is about 250 lines anyone on the
  team can walk through during the viva.

**Alternatives rejected.**
- `llvmlite.binding.parse_assembly`: version-locked (see above).
- LLVM C++ API / an `opt` pass: needs a C++ build, much harder to explain.
- Full LLVM grammar (e.g. a Lark grammar): far more work than our needs.

**Limitations to state in the paper.**
- We do not validate the IR; we trust the compiler's output.
- Only the features we need are understood (functions, labels,
  instructions, branch targets). Things like PHI incoming edges are not
  modelled, which is fine at `-O0` where clang emits almost no PHIs.

---

## Decision 4 — How registers, labels, Rust mangling and runtime boilerplate are normalized

**Decision.** Normalization happens in this order
(`ir_parser.py: parse_ir` → `canonicalize_function`):

1. `collect_demangle_hints` — read rustc's readable-name comments
   (`; m::max_val`) before comments are removed.
2. `strip_debug_lines` — drop `source_filename`, `target ...`,
   `attributes #N`, all `!` metadata lines, `@llvm.dbg.*` calls,
   `#dbg_*` records, `, !dbg !N` attachments and comments.
3. Skip runtime functions (`is_runtime_boilerplate`): Rust panic and
   bounds-check helpers, `__rust_*`, anything from the `core`/`alloc`/`std`
   crates, C++ `std::` template copies (`_ZNSt...`), LLVM intrinsics.
4. Drop calls to those helpers inside student functions (`is_runtime_call`).
5. `remove_panic_guards` — delete Rust bounds-check guards.
6. `merge_straight_line_blocks` — merge jump-only chains.
7. `canonicalize_function` — reverse post-order, then rename blocks
   `bb0, bb1, ...`, saving the original names in `label_map`.

**Plain-English explanation.**
- **Registers.** We never compare register names. `extract_opcode` keeps
  only the opcode (`load`, `icmp`, `br` ...), so `%5`, `%x.addr` and `%_7`
  all disappear. That is the register canonicalization. For the dashboard,
  `normalized_ir_text` also renames registers to `%v0, %v1 ...` in order of
  first use, so a human can read the diff.
- **Labels.** Clang numbers blocks (`14:`), rustc names them (`bb3:`,
  `start:`). We rename them by position to `bb0, bb1, ...`.
- **Rust mangling.** Modern rustc uses "v0" mangling
  (`_RNvCs8AlEeC1jcYO_1m7max_val`), older rustc and C++ use Itanium-style
  `_ZN...E`. We use rustc's own readable comment when present, a small v0
  reader otherwise, and an `_ZN` length-prefix reader for legacy/C++.
- **Bounds checks.** Every `a[i]` in Rust becomes "compare i with the
  length; if out of range jump to a panic block". C has no such check.
  `remove_panic_guards` deletes the panic block, turns the conditional
  branch into a plain jump, and deletes the guard comparison.
- **Jump-only chains.** C's `for` loop gets an extra block that only
  jumps to the increment block, and removing Rust guards leaves similar
  chains behind. Merging a block into its single predecessor when the
  predecessor jumps there unconditionally removes this layout noise.
- **Reverse post-order.** Clang and rustc write blocks in different
  orders. Reordering by a depth-first walk from the entry block gives a
  layout that depends only on the control flow.

**Why we chose it.** On the `max_val` example, C and Rust started at k=3
Dice 0.58 with CFG signatures (7,8,1) vs (9,10,2). After guard removal,
merging and RPO they reach Dice 0.667 and identical signatures (6,7,1).

**Alternatives rejected.**
- Renaming registers textually (`%5 → %r0`) and fingerprinting whole lines:
  types (`i32` vs `i64`) and operand order would then leak into the
  fingerprint and break cross-language matching.
- Keeping compiler file order for blocks: rustc's order made forward
  edges look like back-edges (see Decision 5).
- Running `rustfilt`/`c++filt`: an extra external tool, and we only need
  the base name.

**Limitations to state in the paper.**
- A student function whose name contains `panic` is treated as runtime
  code and skipped.
- C stores every parameter into a stack slot at `-O0` and widens `int`
  indexes with `sext`; Rust does neither. These differences remain and cap
  cross-language Dice below 1.0.
- Calls to LLVM intrinsics are dropped, so a struct copy (`llvm.memcpy`)
  is invisible.

---

## Decision 5 — Loop depth approximated from back-edges, not a dominator tree

**Decision.** `cfg_signature.py: compute_cfg_signature` reports
`(num_basic_blocks, num_edges, max_loop_depth)`. `max_loop_depth` is the
number of **distinct blocks targeted by a back-edge**, where a back-edge is
a branch to a block at an *earlier or equal* position in the
reverse-post-order layout.

**Plain-English explanation.** A loop is a place where control jumps
"backwards". Once blocks are in reverse post-order, a jump to an earlier
block can only be a loop's jump back to its header. Counting the distinct
headers counts the loops: a single loop → 1, a nested double loop → 2.

**The label-resolution bug fix.** Branch instructions still say
`label %14`, the compiler's original name, even after
`canonicalize_function` renamed the block to `bb3`. If the lookup table
were built from the *new* names, `%14` would never be found, so no
back-edge would be detected and every function would report 0 loops. We
build `label_order` from `bb.original_label` (also saved in
`func.label_map`). The test
`tests/test_ir_parser.py::test_cfg_signature_uses_original_labels_after_canonicalization`
guards against this regression.

**Two refinements found while testing.**
1. *Reverse post-order first.* rustc writes some loop-body blocks after
   the loop latch. With file order, the forward edge `bb6 → bb7` looked
   like a back-edge. RPO fixes this.
2. *Distinct headers, not raw back-edge count.* A loop body
   `if (...) lo = mid+1; else hi = mid-1;` can jump back to the header
   from two places (Rust's `binary_search` does). Counting raw back-edges
   gave 2 loops; counting distinct headers gives 1.

**Why we chose it.** A dominator tree plus natural-loop nesting is the
textbook approach, but it needs an iterative dataflow algorithm that is
hard to explain in a viva. The RPO + back-edge approach is a few lines,
and on reducible control flow (all structured C/Rust code) it finds
exactly the natural-loop headers.

**Alternatives rejected.**
- Dominator tree + loop nesting forest: more accurate nesting depth, much
  more code.
- `opt -passes=print<loops>`: needs the LLVM `opt` binary at runtime.

**Limitations to state in the paper.**
- The value is a **loop count**, not true nesting depth: two loops one
  after the other count as 2, the same as a nested pair.
- Irreducible control flow (from `goto`) may be miscounted.

---

## Decision 6 — The Addition D hybrid score (×1.15 boost / ×0.85 penalty)

**Decision.** `similarity.py: hybrid_score`:

```
cfg_match = blocks, edges and loops are EACH within 25 %:
            abs(a - b) <= 0.25 * max(a, b, 1)
hybrid    = min(1.0, Dice * 1.15)   if cfg_match
          = Dice * 0.85             otherwise
```

Raw Dice, Jaccard and Cosine are always kept next to `hybrid_score`.

**Plain-English explanation.** k-grams describe *what* instructions appear
in a row; the CFG signature describes the *shape* of the function. Two
independent programs can share many short instruction runs (every loop has
`load, icmp, br`), but they rarely have the same shape too. So when shapes
agree, we trust the k-gram score a bit more; when they disagree, a bit
less. The ±15 % is a soft adjustment: shape alone never flags a pair.

**How it improves Credibility (measured, `resilience_credibility_eval.py`,
28 clone pairs vs 225 independent pairs).**
- Threshold-free ranking (AUC) improves at every k:
  k=2 0.900 → 0.929, k=3 0.889 → 0.924, k=4 0.903 → 0.927,
  k=5 0.912 → 0.932.
- At k=3, threshold 0.60: Resilience 0.714 → 0.821 **and** Credibility
  0.858 → 0.871. Both rise together.
- At k=4, best thresholds: Resilience stays 0.714 while Credibility rises
  0.920 → 0.960.

Why: independent pairs mostly have different shapes (69 of 90
C-vs-Rust different-algorithm pairs fail `cfg_match` at k=3), so the
×0.85 penalty pushes them down. Most true clones keep their shape, so the
×1.15 boost lifts them.

**Limitations to state in the paper.**
- **Not better at every threshold.** At k=3 and threshold 0.80,
  Credibility *falls* 0.996 → 0.973: 6 of 225 independent pairs with the
  same shape are boosted over the line, e.g. `factorial` vs `fibonacci`
  (Dice 0.800 → hybrid 0.920) and `array_sum` vs `factorial`
  (0.791 → 0.909), all simple single-loop functions.
- The 1.15 / 0.85 factors and the 25 % tolerance were chosen by hand, not
  fitted. A paper should report the sweep, not a single threshold.
- Small single-loop functions (sum, factorial, fibonacci) look alike in
  both k-grams and shape; neither signal separates them well.

---

## Decision 7 — Always extract at canonical `-O0` (Addition C)

**Decision.** IRprint ignores how a student built their code and always
recompiles the source at `-O0`. The `--opt-level` CLI option exists only
for the drift experiment.

**Plain-English explanation.** The optimizer rewrites code heavily:
stack variables become registers (`alloca/load/store` → `phi`), loops get
rotated, small functions vanish. The same source at `-O0` and `-O2` looks
like two different programs. If two students' code were fingerprinted at
different levels, a copied program could look original.

**Measured (`optimization_level_eval.py`, 10 programs, k=3, same source):**

| comparison | mean Dice |
|------------|-----------|
| `-O0` vs `-O1` | 0.042 |
| `-O0` vs `-O2` | 0.047 |
| `-O1` vs `-O2` | 0.697 |
| IRprint canonical `-O0` vs `-O0` | **1.000** |

A renamed clone (tier-1) compiled at `-O0` on one side and `-O2` on the
other scores a mean Dice of 0.054. At canonical `-O0` it scores 1.000.

**Why `-O0` and not `-O2` as the canonical level.** `-O0` is a near
one-to-one translation of the source and changes least between compiler
versions. `-O2` output depends on inlining and vectorization heuristics
that change between releases.

**Limitations to state in the paper.**
- Canonical extraction needs the *source*; IRprint cannot fingerprint a
  binary someone compiled elsewhere.
- `-O0` keeps surface structure, which is why tier-3 rewrites still hurt.
  Adding `mem2reg` only (possible thanks to Decision 2) is future work.

---

## Decision 8 — SQLite + SQLAlchemy kept outside the core pipeline

**Decision.** The core pipeline (`compiler_wrapper` → `similarity`) works
entirely in memory with dataclasses (`models.py`). Saving to SQLite
happens only if `scan_directory(..., db_url=...)` is given, and the
SQLAlchemy import is inside that branch.

**Plain-English explanation.** The CLI and the four experiments just need
numbers; they should not create database files. The dashboard needs memory
between page loads (which scan is current, what verdict the instructor
gave), so it passes a database URL.

**Why we chose it.**
- Experiments and tests run without touching disk state.
- The pipeline can be read and tested without knowing SQLAlchemy.
- SQLite is a single file (`data/irprint.db`, git-ignored): no database
  server for a classroom demo.
- SQLAlchemy 2.x typed models (`db/schema.py`) are short and readable,
  and could point at PostgreSQL by changing the URL.

**What is stored.** Every submission, every function with its normalized
IR and CFG signature, and the comparisons the dashboard needs: the best
pair for each file pair (heat-map) plus every flagged pair, each with an
`instructor_verdict` (`pending` → `confirmed` / `false_positive` /
`needs_discussion`).

**Alternatives rejected.**
- Always writing to the database: slows the experiments and couples every
  test to a DB file.
- JSON files: no easy way to update a single verdict safely.
- Storing *all* function pairs: grows as n²·f²; we store only the pairs the
  dashboard can show.

**Limitations to state in the paper.** Single-user tool: no
authentication, and SQLite is not meant for many concurrent writers.

---

## Smaller decisions worth knowing

| Decision | Why |
|----------|-----|
| Compare every function with every function, take the best pair per file pair | Students reorder and rename functions; matching by name would miss copies. |
| Skip functions with fewer than 10 opcodes in class scans (`pipeline.MIN_OPCODES`) | Tiny getters look alike everywhere. The drift study turns this off because optimized `gcd` is only 9 opcodes. |
| Default k = 3, threshold = 0.80 | k=3 balances specificity and robustness in our sweeps; 0.80 is conservative (Credibility 0.973 at k=3). The CLI exposes both. |
| Sets of k-grams, not counts | Matches the Dice/Jaccard definitions in birthmark literature; repeated loops do not inflate scores. |
| Offline paraphrase corpus written by an LLM (Claude) at build time | The demo must run without internet. `--live` regenerates paraphrases with the Claude API (`claude-opus-5-5` by default, Anthropic SDK). |
| Token baseline is our own simplified re-implementation | Running real MOSS needs an account and network; we label it "MOSS/JPlag-style", not MOSS. |
| Dashboard heat-map in plain canvas, no chart library | No CDN/network needed in the classroom; ~150 lines of JS. |

## Known false positives in the demo class

`experiments/corpus/class_demo` contains independent submissions that
IRprint still flags or nearly flags. Show these honestly during the demo;
they are why the instructor triage step exists:

- `frank.c: selection_sort` vs `alice.c: sort_scores` (bubble sort), and
  likewise vs Bob's and Erin's copies: hybrid 0.933. Both are a nested loop
  around a compare-and-swap.
- `carol.rs: highest_score` vs `grace.rs: mode_bucket`: hybrid 0.826. Both
  are "scan for the maximum" loops.
- Near miss: `dave.c: insertion_sort` vs `frank.c: selection_sort`, hybrid
  0.7999 (shown as 0.800 in the heat-map), just under the threshold.

And one miss: `carol.rs`, a Rust port of Alice's code, scores 0.767 against
`alice.c` and is **not** flagged at 0.80. Lowering the threshold to 0.75
catches it but also flags more independent pairs (see Decision 6).
