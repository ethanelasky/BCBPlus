# BCBPlus — BigCodeBench-Plus (Palaestra Curated)

Curated fork of [bubbleresearch/bigcodebench-plus](https://huggingface.co/datasets/bubbleresearch/bigcodebench-plus) with spec ambiguities, test bugs, and broken canonical solutions corrected per the Palaestra Research review philosophy.

**HuggingFace target**: [palaestraresearch/bcbplus](https://huggingface.co/datasets/palaestraresearch/bcbplus) (set in `scripts/push_hf.py`).

## Layout

- `problems/` — flat dir of per-problem JSONs. Filename `NNNN_BigCodeBench_M.json` where NNNN = 0-padded sort idx, M = task_id integer.
- `build/` — versioned canonical JSONL (`bcbplus_full_<version>.jsonl`).
- `scripts/` — build pipeline:
  - `build.py` — concatenates all `problems/*.json` into `build/bcbplus_full_<ver>.jsonl`. Sorts by task_id numeric order.
  - `verify_problem.py` — assembles + runs a single problem's tests against its canonical solution. Used by fix subagents to verify regenerated canonicals.
  - `push_hf.py` — pushes canonical + metadata + README to HuggingFace.
- `docs/` — review philosophy, fix conventions, etc.

## Workflow

1. Edit `problems/NNNN_BigCodeBench_M.json` directly (the per-problem JSON is the source of truth).
2. For canonical regenerations, run `python scripts/verify_problem.py --file <path>` to confirm the new canonical passes its own tests.
3. Build: `python scripts/build.py --version v0.1.1` concatenates all problems into `build/bcbplus_full_v0.1.1.jsonl`.
4. Publish: `python scripts/push_hf.py --version v0.1.1 --push` uploads to HuggingFace (defaults to `palaestraresearch/bcbplus`).

## Provenance

Baseline (v0.1.0) is a snapshot of `bubbleresearch/bigcodebench-plus` as of 2026-04-22T13:35:54. Subsequent commits apply per-problem fixes from the review pass at `~/ai-debate/ai_debate/results/bcbplus_public_review.csv`.

## Curation philosophy (binding)

- Deterministic docstring examples ARE spec — tests must agree.
- Library conventions are binding (pandas, numpy, sklearn defaults).
- Function signatures are binding; spec prose that contradicts signature loses.
- No exact RNG-realization tests; assert ranges / properties / reproducibility instead.
- No error-message wording tests; check exception types only.

Full source: `tools/transcript_viewer/evaluation_prompts/philosophy.py` in `~/ai-debate/ai_debate/`.

## Schema

Each row in `tasks.jsonl` (and each `problems/*.json`):

```json
{
  "task_id": "BigCodeBench/N",
  "dataset": "bigcodebench",
  "version": <int>,
  "version_id": "<upstream version stamp>",
  "status": "active" | "excluded",
  "exclusion_reason": null | "<reason>",
  "content": {
    "complete_prompt": "<docstring + signature + example>",
    "instruct_prompt": "<plain-text instruction>",
    "code_prompt": "<imports + def line>",
    "canonical_solution": "<function body>",
    "test": "<unittest module text>",
    "entry_point": "task_func",
    "libs": ["pandas", "numpy", ...]
  }
}
```
