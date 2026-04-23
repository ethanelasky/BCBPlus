"""Verify a single problem's canonical solution passes its own tests.

Assembles code_prompt + canonical_solution + test into a single .py file,
runs unittest. Returns 0 on success, nonzero on failure.

Usage:
    python scripts/verify_problem.py --file problems/0046_BigCodeBench_46.json
    python scripts/verify_problem.py --task-id BigCodeBench/46
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Use the ai_debate uv venv if present (has pandas/numpy/scipy/sklearn/etc).
# Override with BCB_PYTHON env var if needed.
DEFAULT_PYTHON = os.environ.get(
    "BCB_PYTHON",
    "/Users/ethanelasky/ai-debate/ai_debate/.venv/bin/python"
    if Path("/Users/ethanelasky/ai-debate/ai_debate/.venv/bin/python").exists()
    else sys.executable,
)


def assemble_test_file(problem: dict) -> str:
    c = problem["content"]
    code_prompt = c.get("code_prompt", "").rstrip()
    canonical = c.get("canonical_solution", "")
    test = c.get("test", "")
    # The canonical_solution body is what comes inside the function body;
    # it's already indented. code_prompt ends with the def line. Concatenate.
    return f"""{code_prompt}
{canonical}

{test}

if __name__ == "__main__":
    import unittest
    unittest.main(verbosity=2)
"""


def run_problem(problem_path: Path, timeout: int = 60) -> tuple[int, str, str]:
    problem = json.loads(problem_path.read_text())
    src = assemble_test_file(problem)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(src)
        tmp = Path(f.name)
    try:
        env = {**os.environ, "MPLBACKEND": "Agg"}
        proc = subprocess.run(
            [DEFAULT_PYTHON, str(tmp)],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr
    finally:
        tmp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", type=Path, help="Path to problem JSON")
    g.add_argument("--task-id", help="e.g. BigCodeBench/46")
    ap.add_argument("--root", default=Path(__file__).resolve().parent.parent,
                    type=Path)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--show-output", action="store_true")
    args = ap.parse_args()

    if args.file:
        path = args.file
    else:
        # Look up by task_id
        n = args.task_id.split("/")[-1]
        cands = list((args.root / "problems").glob(f"*_BigCodeBench_{n}.json"))
        if not cands:
            sys.exit(f"No file found for {args.task_id}")
        path = cands[0]

    rc, out, err = run_problem(path, args.timeout)
    if args.show_output or rc != 0:
        print("--- stdout ---")
        print(out)
        print("--- stderr ---")
        print(err)
    print(f"{path.name}: {'PASS' if rc == 0 else f'FAIL (rc={rc})'}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
