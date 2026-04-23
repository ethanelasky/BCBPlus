"""Push a versioned BCBPlus build to a HuggingFace dataset repo.

Uploads three files at the dataset repo root:
  - tasks.jsonl     <- the canonical build/bcbplus_full_<version>.jsonl
  - metadata.json   <- {version, sha256, n_rows, by_status, by_version, ...}
  - README.md       <- generated card (or pass --readme to use a hand-written one)

Behavior:
  - Computes SHA256 of the canonical and refuses to push if HF already has the
    same SHA at the dataset HEAD (idempotent — no-op rebuilds).
  - Default: dry-run (prints what would happen). Pass --push to actually upload.

Usage:
    python scripts/push_hf.py --version v0.1.1
    python scripts/push_hf.py --version v0.1.1 --push
    python scripts/push_hf.py --version v0.1.1 --repo-id myorg/bcbplus --push
    HF_TOKEN=hf_xxx python scripts/push_hf.py --version v0.1.1 --push

Auth:
    Reads HF_TOKEN from env, or falls back to whatever ``huggingface-cli login``
    cached. ``huggingface_hub`` must be installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = "palaestraresearch/bcbplus"
UPSTREAM_REPO = "bubbleresearch/bigcodebench-plus"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_metadata(payload: bytes, version: str, repo_id: str) -> dict:
    rows = [json.loads(l) for l in payload.decode().splitlines() if l.strip()]
    by_status = Counter(r.get("status", "?") for r in rows)
    by_version = Counter(r.get("version", "?") for r in rows)
    return {
        "name": "BCBPlus",
        "description": ("BigCodeBench-Plus — a curated, fixed fork of "
                        f"{UPSTREAM_REPO}. Spec ambiguities, test bugs, "
                        "and broken canonical solutions corrected per the "
                        "Palaestra Research review philosophy "
                        "(deterministic examples binding, library conventions binding, "
                        "no exact RNG-realization tests, no error-message wording tests)."),
        "version": version,
        "sha256": sha256_bytes(payload),
        "repo_id": repo_id,
        "upstream": UPSTREAM_REPO,
        "n_rows": len(rows),
        "by_status": dict(sorted(by_status.items())),
        "by_version": dict(sorted(by_version.items())),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_readme(meta: dict) -> str:
    by_status_rows = "\n".join(
        f"| {s} | {n} |" for s, n in meta["by_status"].items()
    )
    return f"""---
license: apache-2.0
task_categories:
  - text-generation
language:
  - en
tags:
  - code
  - benchmark
  - python
pretty_name: BCBPlus
size_categories:
  - 1K<n<10K
configs:
  - config_name: default
    data_files:
      - split: train
        path: tasks.jsonl
---

# BCBPlus — BigCodeBench-Plus (Palaestra Curated)

A fixed fork of [{meta["upstream"]}](https://huggingface.co/datasets/{meta["upstream"]}) with spec ambiguities, test bugs, and broken canonical solutions corrected.

**Version**: {meta["version"]}
**Rows**: {meta["n_rows"]}
**SHA256**: `{meta["sha256"][:16]}...`
**Upstream**: `{meta["upstream"]}`

## Status breakdown

| Status | Count |
|--------|-------|
{by_status_rows}

## Curation philosophy

- **Deterministic docstring examples are spec.** Tests must agree with them.
- **Library conventions are binding.** A test that contradicts pandas/numpy/sklearn defaults is a test bug.
- **Function signatures are binding.** Spec prose that contradicts the signature loses.
- **No exact RNG-realization tests.** Tests assert ranges/properties/reproducibility, not seeded outputs.
- **No error-message wording tests.** Tests check exception types only.

Full philosophy: see source repo.

## Schema

Each row:

```json
{{
  "task_id": "BigCodeBench/N",
  "dataset": "bigcodebench",
  "version": <int>,
  "status": "active" | "excluded",
  "content": {{
    "complete_prompt": "...",
    "instruct_prompt": "...",
    "code_prompt": "...",
    "canonical_solution": "...",
    "test": "...",
    "entry_point": "task_func",
    "libs": [...]
  }}
}}
```

## Usage

```python
from datasets import load_dataset
ds = load_dataset("{meta["repo_id"]}", split="train")
print(ds[0]["content"]["complete_prompt"])
```

For reproducibility, pin to a commit:
```python
ds = load_dataset("{meta["repo_id"]}", revision="<commit_hash>")
```
"""


def remote_sha_if_present(api, repo_id: str):
    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import EntryNotFoundError, RepositoryNotFoundError
    except ImportError:
        return None
    try:
        path = hf_hub_download(repo_id=repo_id, filename="tasks.jsonl",
                               repo_type="dataset", force_download=True)
        return sha256_bytes(Path(path).read_bytes())
    except (EntryNotFoundError, RepositoryNotFoundError, FileNotFoundError):
        return None
    except Exception as e:
        print(f"  (couldn't read remote tasks.jsonl: {e})", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True, help="Build version, e.g. v0.1.1")
    ap.add_argument("--repo-id", default=DEFAULT_REPO,
                    help=f"HF dataset repo (default: {DEFAULT_REPO})")
    ap.add_argument("--root", default=Path(__file__).resolve().parent.parent,
                    type=Path, help="BCBPlus repo root")
    ap.add_argument("--push", action="store_true", help="Actually upload (default: dry-run)")
    ap.add_argument("--readme", type=Path, default=None,
                    help="Override README path (otherwise generated)")
    ap.add_argument("--commit-message", default=None,
                    help="Override commit message (default: 'Update to <version>')")
    args = ap.parse_args()

    root = args.root.resolve()
    canonical = root / "build" / f"bcbplus_full_{args.version}.jsonl"
    if not canonical.exists():
        sys.exit(f"Canonical not found: {canonical}\nRun: python scripts/build.py --version {args.version}")

    payload = canonical.read_bytes()
    meta = build_metadata(payload, args.version, args.repo_id)
    readme = (args.readme.read_text() if args.readme else generate_readme(meta))
    msg = args.commit_message or f"Update to {args.version}"

    print(f"Repo:    {args.repo_id}")
    print(f"Version: {args.version}")
    print(f"Rows:    {meta['n_rows']}")
    print(f"SHA[:16]:{meta['sha256'][:16]}")
    print(f"Commit:  {msg}")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("ERROR: pip install huggingface_hub")
    api = HfApi(token=os.environ.get("HF_TOKEN"))

    remote_sha = remote_sha_if_present(api, args.repo_id)
    if remote_sha == meta["sha256"]:
        print(f"\nNo-op: HF already at SHA {remote_sha[:16]}")
        return

    if remote_sha:
        print(f"\nRemote currently at SHA {remote_sha[:16]} -> will replace.")
    else:
        print(f"\nRemote has no tasks.jsonl yet (or repo is new) -> will create.")

    if not args.push:
        print("\n(dry run — pass --push to upload)")
        return

    print("\nUploading...")
    api.upload_file(path_or_fileobj=payload, path_in_repo="tasks.jsonl",
                    repo_id=args.repo_id, repo_type="dataset", commit_message=msg)
    print("  tasks.jsonl ✓")
    api.upload_file(path_or_fileobj=json.dumps(meta, indent=2).encode(),
                    path_in_repo="metadata.json", repo_id=args.repo_id,
                    repo_type="dataset", commit_message=msg)
    print("  metadata.json ✓")
    api.upload_file(path_or_fileobj=readme.encode(), path_in_repo="README.md",
                    repo_id=args.repo_id, repo_type="dataset", commit_message=msg)
    print("  README.md ✓")
    print(f"\nPublished: https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
