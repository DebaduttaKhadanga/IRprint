# IRprint — Execution Flow

How one submission travels through the code, file by file and function by
function, with the exact data structure handed over at every step. The
examples are real output for `tests/fixtures/max_a.c` (clang 23.1.3).

## Professor viva pinpoint table

Every functionality has a banner comment
`# FUNCTIONALITY N: <name>` directly above the function that implements it.
Search for `FUNCTIONALITY 3` (etc.) to jump there.

| # | Functionality / Addition | File | Function(s) | Key variables / constants |
|---|--------------------------|------|-------------|---------------------------|
| 1 | Multi-language LLVM-IR compilation | `irprint/compiler_wrapper.py` | `compile_to_ir` (line 111), `build_command` (72), `find_tool` (54) | `LANGUAGE_BY_EXTENSION`, `COMPILER_BY_LANGUAGE`, `DEFAULT_TIMEOUT_SECONDS`, `cmd`, `workdir` |
| 2 | Debug/metadata stripping | `irprint/normalizer.py` | `strip_debug_lines` (52) | `METADATA_ATTACHMENT`, `DEFINE_METADATA`, `DEBUG_INTRINSIC_CALL`, `DEBUG_RECORD` |
| 2 | Demangling + runtime filtering | `irprint/normalizer.py` | `demangle_symbol` (228), `is_runtime_boilerplate` (239), `is_runtime_call` (257), `collect_demangle_hints` (111), `rust_v0_crate` (144) | `RUNTIME_NAME_MARKERS`, `RUST_STD_CRATES`, `CPP_STD_PREFIXES`, `hints` |
| 2 | Rust bounds-check guard removal | `irprint/normalizer.py` | `remove_panic_guards` (270) | `dead`, `survivor`, `cond` |
| 2 | Jump-only block merging | `irprint/normalizer.py` | `merge_straight_line_blocks` (324) | `predecessors`, `UNCONDITIONAL_BR` |
| 2 | Line-oriented function parser | `irprint/ir_parser.py` | `parse_ir` (114), `extract_opcode` (43), `_split_into_blocks`, `_join_multiline_instructions` | `DEFINE_LINE`, `LABEL_LINE`, `ASSIGNMENT`, `ENTRY_LABEL` |
| 2 | Label canonicalization | `irprint/ir_parser.py` | `canonicalize_function` (209), `reverse_postorder` (171), `normalized_ir_text` (237) | `func.label_map`, `bb.original_label`, `bb.label` |
| 3 | Multi-k opcode birthmarks | `irprint/birthmark.py` | `build_birthmark` (37), `extract_kgrams` (21) | `DEFAULT_KS = (2, 3, 4, 5)`, `opcodes`, `kgrams` |
| 3 | CFG shape signature (+ label bug fix) | `irprint/cfg_signature.py` | `compute_cfg_signature` (15); helper `branch_targets` in `ir_parser.py` (160) | `label_order` (built from `original_label`), `num_edges`, `loop_headers` |
| 4 | Dice / Jaccard / Cosine / CFG closeness | `irprint/similarity.py` | `dice` (17), `jaccard` (24), `cosine` (31), `cfg_signature_close` (40) | `CFG_TOLERANCE = 0.25` |
| 4 / D | Hybrid score | `irprint/similarity.py` | `hybrid_score` (55), `compare_birthmarks` (66) | `HYBRID_BOOST = 1.15`, `HYBRID_PENALTY = 0.85`, `DEFAULT_THRESHOLD = 0.80` |
| 4 / D | Resilience & Credibility evaluation | `experiments/resilience_credibility_eval.py` | `run_resilience_credibility_eval`, `build_pairs`, `resilience`, `credibility` | `THRESHOLDS`, `pos`, `neg`, `sweep`, `best_t` |
| 5 / A | Cross-language clone benchmark | `experiments/cross_language_eval.py` | `run_cross_language_eval` | `scores[(c_name, r_name)]`, `top1`, `auc` |
| 6 / B | LLM-paraphrase benchmark (offline + live) | `experiments/llm_paraphrase_eval.py` | `run_paraphrase_eval`, `generate_live_paraphrases` | `TIERS`, `TIER_INSTRUCTIONS`, `--live`, `--model` |
| 7 / C | Optimization-level drift study | `experiments/optimization_level_eval.py` | `run_optimization_eval` | `LEVELS`, `LEVEL_PAIRS`, `drift`, `canonical` |
| 8 | Batch pipeline | `irprint/pipeline.py` | `scan_directory` (124), `process_file` (74), `best_match` (105) | `MIN_OPCODES = 10`, `matrix`, `best_pairs`, `flagged` |
| 8 | CLI | `irprint/cli.py` | `scan` (43), `serve` (81), `doctor` (93) | `--k`, `--threshold`, `--opt-level`, `--json-out`, `--db` |
| 8 | Database | `irprint/db/schema.py`, `irprint/db/crud.py` | `Submission`, `FunctionRecord`, `ComparisonRecord`; `save_scan` (27), `set_verdict` (120) | `VERDICTS`, `DEFAULT_DB_URL` |
| 8 | Web API | `irprint/api/main.py` | `index` (82), `scan_upload` (98), `scan_demo` (118), `pair_detail` (148), `pair_verdict` (162), `side_by_side_rows` (127) | `latest_scan_payload`, `pair_ids` |
| 8 | Heat-map + dashboard | `dashboard/static/heatmap.js`, `dashboard/templates/*.html` | `colorFor`, `draw`, `cellAt` | `RAMP`, `data.matrix`, `data.pair_ids` |
| 8 | Container | `Dockerfile` | `builder` and `runtime` stages | `IRPRINT_DB_URL` |

Data structures are all in `irprint/models.py`: `CompileResult` (21),
`Instruction` (35), `BasicBlock` (41), `Function` (52), `CFGSignature` (73),
`Birthmark` (83), `ComparisonResult` (97).

---

## The pipeline at a glance

```
cli.py: scan                 api/main.py: POST /scan, POST /scan/demo
          \                    /
           pipeline.py: scan_directory(directory, k, threshold, opt_level, db_url)
             |  collect_source_files()                      -> list[Path]
             |  for each file: process_file(path)
             |     1 compiler_wrapper.compile_to_ir()        -> CompileResult
             |     2 ir_parser.parse_ir()                    -> list[Function]
             |          normalizer.collect_demangle_hints / strip_debug_lines
             |          normalizer.is_runtime_boilerplate / is_runtime_call
             |          normalizer.remove_panic_guards / merge_straight_line_blocks
             |     3 ir_parser.canonicalize_function()       -> Function (bb0, bb1, ...)
             |     4 birthmark.build_birthmark()             -> Birthmark
             |          cfg_signature.compute_cfg_signature  -> CFGSignature
             |  for each pair of files: compare_submissions()
             |     5 similarity.compare_birthmarks()         -> ComparisonResult
             |  build matrix / best_pairs / flagged          -> ScanReport
             |     6 (optional) db/crud.save_scan()          -> rows in SQLite
             v
cli.py prints the table / writes JSON      dashboard/templates render the DB rows
```

---

## Step 0 — Entry points

**CLI.** `irprint scan tests/fixtures --k 3 --json-out report.json`
→ `irprint/cli.py: scan()` → `pipeline.scan_directory(directory, k=3, threshold=0.8, opt_level="O0", db_url=None)`.
`--db` sets `db_url="sqlite:///data/irprint.db"`.

**Web.** `irprint serve` → `cli.serve()` sets `IRPRINT_DB_URL` and starts
uvicorn on `irprint.api.main:app`.
- `POST /scan` → `scan_upload()` saves uploaded files (basename only) to a
  temporary folder, then calls `scan_directory(workdir, k, threshold, db_url=db_url())`.
- `POST /scan/demo` → `scan_demo()` scans `experiments/corpus/class_demo`.

`scan_directory` calls `collect_source_files(directory)`, which returns the
sorted list of `.c/.cpp/.cc/.cxx/.rs/.swift` files (hidden folders
skipped), and calls `process_file()` on each one.

---

## Step 1 — `compiler_wrapper.compile_to_ir(path, opt_level="O0")` → `CompileResult`

1. `detect_language("max_a.c")` → `"c"`.
2. `find_tool("clang")` → path of clang (env var `IRPRINT_CLANG`, then
   `$PATH`, then `~/.cargo/bin`, `~/.local/llvm-env/bin`, ...).
3. The source is copied into a fresh `tempfile.TemporaryDirectory`.
4. `build_command(...)` builds:
   ```
   clang -S -emit-llvm -O0 -g0 -Xclang -disable-O0-optnone -o <tmp>/out.ll <tmp>/max_a.c
   ```
   (Rust: `rustc --emit=llvm-ir --crate-type=lib -C opt-level=0 -C debuginfo=0 -C overflow-checks=off -C panic=abort ...`)
5. `subprocess.run(cmd, timeout=30)`. A timeout or a non-zero exit returns
   `success=False` with the compiler's stderr in `error`.

**Output:**
```python
CompileResult(
    source_path="tests/fixtures/max_a.c", language="c", success=True,
    ir_text="; ModuleID = 'max_a.c'\nsource_filename = ...",   # 71 lines
    error="", command=["clang", "-S", "-emit-llvm", ...], opt_level="O0")
```

---

## Step 2 — `ir_parser.parse_ir(ir_text, source_path, language)` → `list[Function]`

1. `normalizer.collect_demangle_hints(ir_text)` — reads rustc's
   `; crate::function` comments *before* comments are removed.
   For C this is `{}`; for Rust e.g. `{"_RNvCs..._1m7max_val": "m::max_val"}`.
2. `normalizer.strip_debug_lines(ir_text)` — removes `source_filename`,
   `target ...`, `attributes #0 = {...}`, every `!N = ...` line,
   `, !dbg !N` / `, !llvm.loop !N`, `!dbg`/`!guid` on `define` lines,
   `#N` attribute references, and `; comments`. **71 lines → 46 lines.**
3. Loop over lines. `DEFINE_LINE` matches
   `define dso_local i32 @max_val(ptr noundef %0, i32 noundef %1) {` and
   captures `raw_name = "max_val"`. Lines until `}` are the body.
4. `is_runtime_boilerplate(raw_name, hint)` — `False` for `max_val`
   (would be `True` for `panic_bounds_check`, `core::...`, `std::vector`...).
5. `demangle_symbol(raw_name, hint)` → `"max_val"`
   (`_Z7max_valPii` → `max_val`; `_RNv..._1m7max_val` → `max_val`).
6. `_join_multiline_instructions(body)` — glues `switch ... [ ... ]` onto
   one line.
7. `_split_into_blocks(lines)` — the first block has no label and is
   called `%entry`; every `LABEL_LINE` (`10:`) starts a new `BasicBlock`.
   Each other line becomes
   `Instruction(opcode=extract_opcode(line), raw_line=line)`, except calls
   to runtime helpers (`is_runtime_call`), which are dropped.
   `extract_opcode("%11 = load i32, ptr %6, align 4")` → `"load"`.
8. `remove_panic_guards(blocks)` — no effect for C. For Rust, removes
   `panic:` blocks and turns `br i1 %_14, label %bb4, label %panic1` into
   `br label %bb4`.
9. `merge_straight_line_blocks(blocks)` — clang's `28: br label %29` block
   absorbs block `29`. **7 blocks → 6 blocks** for `max_val`.

**Output (one element):**
```python
Function(name="max_val", raw_name="max_val", source_path="max_a.c", language="c",
         blocks=[BasicBlock(label="%entry", original_label="%entry", instructions=[12 x Instruction]),
                 BasicBlock(label="10", original_label="10", ...),   # loop header
                 BasicBlock(label="14", ...), BasicBlock(label="22", ...),
                 BasicBlock(label="28", ...),                        # merged 28+29
                 BasicBlock(label="32", ...)],                       # return
         label_map={})
```

---

## Step 3 — `ir_parser.canonicalize_function(func)` → `Function` (canonical)

1. `reverse_postorder(func.blocks)` — depth-first walk from the entry
   block, following `branch_targets(terminator)` in written order.
   File order `%entry,10,14,22,28,32` → RPO `%entry,10,32,14,22,28`.
2. Block *i* is renamed `bb<i>`. The original name stays in
   `bb.original_label`, and `func.label_map` records the mapping:
   ```python
   {"%entry": "bb0", "10": "bb1", "32": "bb2", "14": "bb3", "22": "bb4", "28": "bb5"}
   ```
3. Register names are never compared; only opcodes are used from here on.
   `func.opcode_sequence()` →
   ```
   alloca alloca alloca alloca store store load getelementptr load store store br
   load load icmp br  load ret  load load sext getelementptr load load icmp br
   load load sext getelementptr load store br  load add store br          (37 opcodes)
   ```

---

## Step 4 — `birthmark.build_birthmark(func)` → `Birthmark` (+ `CFGSignature`)

1. `extract_kgrams(opcodes, k)` for k = 2, 3, 4, 5. For k=3 there are 25
   distinct 3-grams, e.g. `("alloca","alloca","store")`, `("add","store","br")`.
2. `cfg_signature.compute_cfg_signature(func)`:
   - `label_order` is built from **`bb.original_label`**
     (`{"%entry":0, "10":1, "32":2, "14":3, "22":4, "28":5}`). This is the
     label-resolution bug fix: branch lines still say `label %10`, not
     `label %bb1`.
   - For each block's terminator, `branch_targets()` lists the targets.
     Each target adds one edge. If `label_order[target] <= index`, the
     target is a loop header (`bb5 → 10` is the back-edge).
   - Result: `CFGSignature(num_basic_blocks=6, num_edges=7, max_loop_depth=1)`.
3. `normalized_ir_text(func)` — readable canonical IR for the dashboard:
   ```
   define @max_val
   bb0:
     %v0 = alloca ptr, align 8
     ...
     br label %bb1
   ```

**Output:**
```python
Birthmark(function_name="max_val", source_path="max_a.c", language="c",
          kgrams={2: {...}, 3: {25 tuples}, 4: {...}, 5: {...}},
          cfg=CFGSignature(6, 7, 1), opcode_count=37,
          normalized_ir="define @max_val\nbb0:\n  %v0 = alloca ptr, align 8 ...")
```

---

## Step 5 — `pipeline.compare_submissions` → `similarity.compare_birthmarks` → `ComparisonResult`

`scan_directory` loops over every pair of files (`itertools.combinations`).
`compare_submissions(a, b, k)` compares every function of `a` with every
function of `b`, skipping functions shorter than `MIN_OPCODES = 10`.

Inside `compare_birthmarks(bm_a, bm_b, k=3, threshold=0.8)`:
1. `dice(A, B) = 2|A∩B| / (|A|+|B|)`, `jaccard = |A∩B|/|A∪B|`,
   `cosine = |A∩B| / sqrt(|A||B|)` on the k=3 sets.
2. `cfg_signature_close(cfg_a, cfg_b)` — each of the three numbers within
   `0.25 * max(a, b, 1)`.
3. `hybrid_score(dice, cfg_match)` — `min(1, dice*1.15)` or `dice*0.85`.
4. `flagged = hybrid >= threshold`.

**Real outputs:**
```python
# max_a.c vs max_b_renamed.c (renamed copy)
ComparisonResult(file_a="max_a.c", func_a="max_val", file_b="max_b_renamed.c", func_b="biggest",
                 k=3, dice=1.0, jaccard=1.0, cosine=1.0,
                 cfg_a=CFGSignature(6,7,1), cfg_b=CFGSignature(6,7,1),
                 cfg_match=True, hybrid_score=1.0, flagged=True)

# max_a.c vs max_rust.rs (cross-language port)
ComparisonResult(..., func_b="max_val", k=3, dice=0.6667, jaccard=0.5, cosine=0.6708,
                 cfg_a=CFGSignature(6,7,1), cfg_b=CFGSignature(6,7,1),
                 cfg_match=True, hybrid_score=0.7667, flagged=False)
```

Per file pair, the best result (highest hybrid) goes to `best_pairs` and
into `matrix[i][j]` (the heat-map). Every result with `flagged=True` goes
to `flagged`. All of it is returned as a `ScanReport`.

---

## Step 6 — `db/crud.save_scan(db_url, report)` (only if `db_url` is set)

1. New `scan_id = uuid4()`.
2. One `Submission` row per file (`filename`, `language`, `compiled`,
   `error`).
3. One `FunctionRecord` row per birthmark: `name`, `ir_text`
   (= `normalized_ir`), `num_blocks`, `num_edges`, `loop_depth`,
   `opcode_count`.
4. One `ComparisonRecord` per entry of `best_pairs + flagged`
   (de-duplicated): the scores, `cfg_match`, `flagged`, and
   `instructor_verdict = "pending"`.
5. `report.scan_id` is set; the CLI prints it.

---

## Step 7 — Output

**CLI** (`cli.scan`): prints one line per submission (`ok`/`FAILED`,
language, function count), then the flagged pairs sorted by hybrid score.
`--json-out` writes `ScanReport.to_dict()`: `labels`, `matrix`,
`flagged_pairs`, `best_pairs`, `submissions`.

**Dashboard:**
- `GET /` → `api/main.index()` → `latest_scan_payload()` reads the newest
  scan with `crud.latest_scan_id / get_submissions / get_comparisons`,
  rebuilds `matrix` and `pair_ids`, and renders `templates/index.html`.
  The payload is embedded as JSON (`<script id="scan-data">`).
  `static/heatmap.js` draws the N×N canvas grid (`colorFor` maps 0..1 to
  a light→dark blue ramp; cells ≥ threshold get an outline); hover shows
  the score, click opens `/pair/<id>`.
- `GET /pair/{index}` → `pair_detail()` → `crud.get_comparison(id)`
  (includes `ir_a`, `ir_b`) → `side_by_side_rows(ir_a, ir_b)` aligns the
  two normalized IR listings with `difflib.SequenceMatcher` → renders
  `templates/pair_detail.html`: Dice, Jaccard, Cosine, both CFG
  signatures, hybrid score, the side-by-side IR, and the verdict buttons.
- `POST /pair/{index}/verdict` (form field `verdict`) →
  `pair_verdict()` → `crud.set_verdict()` stores `confirmed`,
  `false_positive` or `needs_discussion`, then redirects back to the pair.

---

## Experiment scripts (Additions A–D)

All four import `experiments/common.py`, which provides `load(path, opt)`
(cached `process_file`), `pair_scores(a, b, k)` (best Dice and best hybrid
over all function pairs), the `token_dice` baseline, `auc`, and table/JSON
output. Results go to `experiments/results/<name>.json`.

| Script | Input corpus | Loop | Output |
|--------|--------------|------|--------|
| `cross_language_eval.py` (A) | `corpus/algorithms/c`, `corpus/algorithms/rust` | every C × every Rust file, k = 2..5 | mean pos/neg, gap, top-1, AUC per method |
| `llm_paraphrase_eval.py` (B) | `corpus/algorithms/c` + `corpus/llm_paraphrase/tier{1,2,3}` (or `--live` Claude output) | original vs paraphrase (pos), paraphrase vs other originals (neg) | per tier and k: mean scores, detection rate, AUC |
| `optimization_level_eval.py` (C) | `corpus/algorithms/c`, tier-1 clones | same source at O0/O1/O2; clones at mixed levels | drift table vs canonical O0 |
| `resilience_credibility_eval.py` (D) | all of the above | 28 clone pairs, 225 independent pairs, thresholds 0.50–0.90 | Resilience, Credibility, AUC for k-gram vs hybrid |
