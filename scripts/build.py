"""Concatenate all problems/*.json into build/bcbplus_full_<version>.jsonl.

Walks problems/, validates required fields, sorts by task_id (numeric suffix
order), and writes one JSONL row per problem. Refuses to overwrite an existing
build with a different SHA unless --force is passed.

Each per-problem JSON file is the source of truth. Edit problems/NNNN_BigCodeBench_M.json
to change spec / tests / canonical. Then rebuild.

Usage:
    python scripts/build.py --version v0.1.1
    python scripts/build.py --version v0.1.1 --update-latest
    python scripts/build.py --version v0.1.1 --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

REQUIRED_TOP = {"task_id", "dataset", "version", "status", "content"}
REQUIRED_CONTENT = {"complete_prompt", "test", "entry_point", "code_prompt", "canonical_solution"}
PN_RE = re.compile(r"^\d{4}_BigCodeBench_\d+\.json$")
TASK_ID_RE = re.compile(r"^BigCodeBench/(\d+)$")


def load_problem(p: Path):
    if not PN_RE.match(p.name):
        return None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        print(f"  SKIP {p.name}: invalid JSON ({e})", file=sys.stderr)
        return None
    missing_top = REQUIRED_TOP - set(d.keys())
    if missing_top:
        print(f"  SKIP {p.name}: missing top-level fields {sorted(missing_top)}", file=sys.stderr)
        return None
    content = d.get("content") or {}
    missing_content = REQUIRED_CONTENT - set(content.keys())
    if missing_content:
        # canonical_solution may legitimately be missing for excluded items;
        # warn but include for downstream filtering.
        if d.get("status") == "excluded":
            print(f"  WARN {p.name}: excluded item missing {sorted(missing_content)}", file=sys.stderr)
        else:
            print(f"  WARN {p.name}: active item missing content fields {sorted(missing_content)}", file=sys.stderr)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True, help="Version tag, e.g. v0.1.1")
    ap.add_argument("--root", default=Path(__file__).resolve().parent.parent,
                    type=Path, help="BCBPlus repo root")
    ap.add_argument("--update-latest", action="store_true",
                    help="Also write to build/bcbplus_full.jsonl as 'latest' pointer")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite an existing build file with a different SHA")
    args = ap.parse_args()

    root = args.root.resolve()
    out_path = root / "build" / f"bcbplus_full_{args.version}.jsonl"
    problems_dir = root / "problems"

    rows = []
    for p in sorted(problems_dir.iterdir()):
        row = load_problem(p)
        if row is not None:
            rows.append(row)

    def sort_key(r):
        m = TASK_ID_RE.match(r["task_id"])
        return int(m.group(1)) if m else 10**9
    rows.sort(key=sort_key)

    dups = [tid for tid, c in Counter(r["task_id"] for r in rows).items() if c > 1]
    if dups:
        print(f"ERROR: duplicate task_ids: {dups[:10]}", file=sys.stderr)
        sys.exit(1)

    payload = "\n".join(json.dumps(r, ensure_ascii=True) for r in rows) + "\n"
    sha = hashlib.sha256(payload.encode()).hexdigest()

    if out_path.exists() and not args.force:
        existing_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
        if existing_sha != sha:
            print(f"ERROR: {out_path.name} exists with different SHA.", file=sys.stderr)
            print(f"  existing[:16] = {existing_sha[:16]}", file=sys.stderr)
            print(f"  rebuild [:16] = {sha[:16]}", file=sys.stderr)
            print(f"  pass --force to overwrite, or bump --version.", file=sys.stderr)
            sys.exit(2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload)

    by_status = Counter(r.get("status", "?") for r in rows)
    by_version = Counter(r.get("version", "?") for r in rows)
    print(f"Wrote {out_path}")
    print(f"  rows: {len(rows)}")
    print(f"  sha256[:16]: {sha[:16]}")
    print(f"  by status: {dict(by_status.most_common())}")
    print(f"  by version: {dict(by_version.most_common())}")

    if args.update_latest:
        latest = root / "build" / "bcbplus_full.jsonl"
        latest.write_text(payload)
        print(f"  updated {latest.name} (latest pointer)")


if __name__ == "__main__":
    main()
