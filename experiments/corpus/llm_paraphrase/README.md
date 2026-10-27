# Offline LLM-paraphrase corpus (Addition B)

Pre-generated paraphrases of six originals from `../algorithms/c/`, so
`experiments/llm_paraphrase_eval.py` runs with no internet and no API key.

| Tier | Transformation (3-tier protocol) |
|------|----------------------------------|
| tier1 | identifier renaming, comments and formatting changes only |
| tier2 | control-flow reversal (negated conditions, swapped branches, `continue`/`break` restructuring) and `for` <-> `while` conversion |
| tier3 | structural expression rewriting: pointer arithmetic instead of indexing, ternaries, extracted helper functions, early exits, arithmetic identities |

Provenance: these files were written by an LLM (Claude) when the project
was built, by following the tier definitions above. They were not
produced by the `--live` mode of the experiment script. Run
`python experiments/llm_paraphrase_eval.py --live` (needs `ANTHROPIC_API_KEY`
and the `anthropic` package) to generate and score a fresh set.
