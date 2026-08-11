#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DENIED_PREFIXES = (
    ".github/",
    "artifacts/",
    "fork_tests/",
    "fork_tools/",
    "scripts/fork/",
)
DENIED_PARTS = ("/__pycache__/", "/node_modules/")
DENIED_SUFFIXES = (".pyc", ".pyo")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject fork-only files from an upstream production diff.")
    parser.add_argument("--base", default="upstream/main")
    parser.add_argument("--feature", default="origin/feature/01-server-scope")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()

    changed = [
        line for line in git(args.repo, "diff", "--name-only", f"{args.base}...{args.feature}").splitlines() if line
    ]
    denied = [
        path
        for path in changed
        if path.startswith(DENIED_PREFIXES)
        or any(part in f"/{path}" for part in DENIED_PARTS)
        or path.endswith(DENIED_SUFFIXES)
    ]
    if denied:
        print("Fork-only paths found in the production diff:", file=sys.stderr)
        for path in denied:
            print(f"- {path}", file=sys.stderr)
        return 1

    print(f"Upstream diff safety: PASS ({len(changed)} production files, no fork-only paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
