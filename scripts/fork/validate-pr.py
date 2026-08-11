#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "fork_tools"
NODE_BIN = TOOLS / "node_modules" / ".bin"


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def require(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode:
        raise RuntimeError(f"{label} failed\n{result.stdout.strip()}")
    return result.stdout


def multiset_added(current: Iterable[str], baseline: Iterable[str]) -> list[str]:
    remaining = collections.Counter(baseline)
    added: list[str] = []
    for item in current:
        if remaining[item]:
            remaining[item] -= 1
        else:
            added.append(item)
    return added


def extract_ref(ref: str, target: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        bundle.extractall(target)


def changed_lines(base_ref: str, feature_ref: str, path: str) -> set[int]:
    output = require(
        run(["git", "diff", "--unified=0", f"{base_ref}...{feature_ref}", "--", path]),
        f"changed-line lookup for {path}",
    )
    lines: set[int] = set()
    for match in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", output, re.MULTILINE):
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        lines.update(range(start, start + count))
    return lines


def formatting_touches_changed_lines(source: Path, changed: set[int]) -> list[int]:
    with tempfile.TemporaryDirectory(prefix="server-panel-format-") as temp:
        candidate = Path(temp) / source.name
        candidate.write_bytes(source.read_bytes())
        require(
            run(
                [sys.executable, "-m", "ruff", "format", "--config", str(TOOLS / "ruff.toml"), str(candidate)],
                cwd=ROOT,
            ),
            f"Ruff formatter probe for {source.name}",
        )
        original = source.read_text(encoding="utf-8").splitlines()
        formatted = candidate.read_text(encoding="utf-8").splitlines()

    touched: set[int] = set()
    for tag, old_start, old_end, _new_start, _new_end in difflib.SequenceMatcher(
        None, original, formatted
    ).get_opcodes():
        if tag == "equal":
            continue
        if old_start == old_end:
            touched.add(max(1, old_start + 1))
        else:
            touched.update(range(old_start + 1, old_end + 1))
    return sorted(touched & changed)


def ruff_diagnostics(repo: Path) -> list[str]:
    result = run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(TOOLS / "ruff.toml"),
            "--output-format",
            "json",
            "app.py",
        ],
        cwd=repo,
    )
    payload = json.loads(result.stdout or "[]")
    return [f"{item['code']}:{item['message']}" for item in payload]


def mypy_diagnostics(repo: Path) -> list[str]:
    result = run(
        [sys.executable, "-m", "mypy", "--config-file", str(TOOLS / "mypy.ini"), "app.py"],
        cwd=repo,
    )
    output: list[str] = []
    for line in result.stdout.splitlines():
        line = re.sub(r"^app\.py:\d+:", "app.py:<line>:", line.strip())
        if line and not line.startswith(("Found ", "Success:")) and "By default the bodies" not in line:
            output.append(line)
    return output


def eslint_diagnostics(repo: Path) -> list[str]:
    result = run(
        [
            str(NODE_BIN / "eslint"),
            "--config",
            str(TOOLS / "eslint.config.mjs"),
            "--no-ignore",
            "--format",
            "json",
            "static/app.js",
        ],
        cwd=repo,
    )
    payload = json.loads(result.stdout or "[]")
    return [f"{item.get('ruleId')}:{item['message']}" for item in payload[0].get("messages", [])]


def typescript_diagnostics(repo: Path) -> list[str]:
    result = run(
        [
            str(NODE_BIN / "tsc"),
            "--allowJs",
            "--checkJs",
            "--noEmit",
            "--target",
            "ES2022",
            "--lib",
            "ES2022,DOM,DOM.Iterable",
            "--skipLibCheck",
            str(repo / "static" / "app.js"),
        ]
    )
    diagnostics: list[str] = []
    for line in result.stdout.splitlines():
        normalized = re.sub(r"^.*app\.js\(\d+,\d+\):\s*", "", line.strip())
        if normalized:
            diagnostics.append(normalized)
    return diagnostics


def stylelint_diagnostics(repo: Path) -> list[str]:
    result = run(
        [
            str(NODE_BIN / "stylelint"),
            "--config",
            str(TOOLS / "stylelint.config.mjs"),
            "--formatter",
            "json",
            str(repo / "static" / "style.css"),
        ]
    )
    payload = json.loads(result.stdout or "[]")
    diagnostics: list[str] = []
    for warning in payload[0].get("warnings", []):
        message = re.sub(r"\d+", "<n>", warning["text"])
        diagnostics.append(f"{warning['rule']}:{message}")
    return diagnostics


def djlint_diagnostics(repo: Path) -> list[str]:
    result = run(
        [
            sys.executable,
            "-m",
            "djlint",
            "--configuration",
            str(TOOLS / "djlint.toml"),
            "templates/index.html",
            "--lint",
        ],
        cwd=repo,
    )
    diagnostics: list[str] = []
    for line in result.stdout.splitlines():
        normalized = re.sub(r"^(H\d+)\s+\d+:\d+\s+", r"\1 ", line.strip())
        if re.match(r"^H\d+ ", normalized):
            diagnostics.append(normalized)
    return diagnostics


def ratchet(label: str, checker: Callable[[Path], list[str]], baseline: Path) -> dict[str, int]:
    old = checker(baseline)
    current = checker(ROOT)
    added = multiset_added(current, old)
    if added:
        raise RuntimeError(f"{label} added diagnostics\n" + "\n".join(added[:25]))
    return {"baseline": len(old), "current": len(current), "removed": len(multiset_added(old, current))}


def check_screenshots() -> dict[str, int]:
    manifest_path = ROOT / "artifacts" / "pr1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = manifest.get("captures", [])
    if len(captures) < 6:
        raise RuntimeError("Screenshot manifest must contain desktop and iPhone before/after evidence")
    for capture in captures:
        path = ROOT / capture["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != capture["sha256"]:
            raise RuntimeError(f"Screenshot hash mismatch: {capture['path']}")

    validation = json.loads(
        (ROOT / "artifacts" / "pr1" / "after" / "validation-results.json").read_text(encoding="utf-8")
    )
    if validation.get("consoleErrors") or validation.get("pageErrors"):
        raise RuntimeError("Browser evidence contains unexpected console or page errors")
    if len(validation.get("assertions", [])) != 8:
        raise RuntimeError("Browser evidence assertion count changed")
    if any(capture.get("horizontalOverflow") for capture in validation.get("captures", [])):
        raise RuntimeError("Browser evidence contains horizontal overflow")
    return {"captures": len(captures), "browser_assertions": len(validation["assertions"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete fork PR validation gate.")
    parser.add_argument("--base-ref", default="upstream/main")
    parser.add_argument("--feature-ref", default="origin/feature/01-server-scope")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--require-screenshots", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results: dict[str, object] = {}
    if not args.allow_dirty:
        status = require(run(["git", "status", "--porcelain"]), "git status")
        if status:
            raise RuntimeError("Full PR gate requires a clean worktree")

    require(run(["git", "diff", "--check", f"{args.base_ref}...{args.feature_ref}"]), "diff hygiene")
    require(
        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "fork" / "check-upstream-diff.py"),
                "--base",
                args.base_ref,
                "--feature",
                args.feature_ref,
            ]
        ),
        "upstream diff safety",
    )

    changed_app_lines = changed_lines(args.base_ref, args.feature_ref, "app.py")
    format_overlap = formatting_touches_changed_lines(ROOT / "app.py", changed_app_lines)
    if format_overlap:
        raise RuntimeError(f"Ruff formatter would alter changed app.py lines: {format_overlap[:20]}")
    results["ruff_format"] = {"changed_lines_clean": len(changed_app_lines)}

    with tempfile.TemporaryDirectory(prefix="server-panel-base-") as temp:
        baseline = Path(temp)
        extract_ref(args.base_ref, baseline)
        results["ruff"] = ratchet("Ruff", ruff_diagnostics, baseline)
        results["mypy"] = ratchet("Mypy", mypy_diagnostics, baseline)
        results["djlint_legacy"] = ratchet("djLint legacy template", djlint_diagnostics, baseline)
        results["eslint"] = ratchet("ESLint", eslint_diagnostics, baseline)
        results["typescript"] = ratchet("TypeScript checkJs", typescript_diagnostics, baseline)
        results["stylelint"] = ratchet("Stylelint", stylelint_diagnostics, baseline)

    require(
        run(
            [sys.executable, "-m", "ruff", "check", "--config", str(TOOLS / "ruff.toml"), "fork_tests", "scripts/fork"]
        ),
        "Ruff fork-code lint",
    )
    require(
        run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--config",
                str(TOOLS / "ruff.toml"),
                "fork_tests",
                "scripts/fork",
            ]
        ),
        "Ruff fork-code format",
    )
    require(
        run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--config-file",
                str(TOOLS / "mypy.ini"),
                "fork_tests",
                "scripts/fork",
            ]
        ),
        "Mypy fork-code type check",
    )
    results["fork_code"] = {"mypy": "pass", "ruff_format": "pass", "ruff_lint": "pass"}
    require(
        run(
            [
                sys.executable,
                "-m",
                "djlint",
                "--configuration",
                str(TOOLS / "djlint.toml"),
                "templates/servers.html",
                "--check",
                "--lint",
            ]
        ),
        "new server template format/lint",
    )
    require(run(["node", "--check", "static/app.js"]), "JavaScript syntax")
    require(run(["node", "--check", "scripts/fork/capture-pr1.cjs"]), "screenshot automation syntax")
    require(
        run(
            [
                str(NODE_BIN / "eslint"),
                "--config",
                str(TOOLS / "eslint.config.mjs"),
                "--no-ignore",
                "scripts/fork/capture-pr1.cjs",
            ]
        ),
        "screenshot automation lint",
    )
    results["javascript_syntax"] = {"app": "pass", "screenshot_automation": "pass"}

    for path in [
        ROOT / "app.py",
        *sorted((ROOT / "fork_tests").rglob("*.py")),
        *sorted((ROOT / "scripts" / "fork").rglob("*.py")),
    ]:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    results["compile"] = "pass"

    pytest_result = run([sys.executable, "-m", "pytest", "-q", "fork_tests"])
    require(pytest_result, "unit/integration tests")
    results["pytest"] = pytest_result.stdout.strip().splitlines()[-1]

    feature_diff = require(run(["git", "diff", f"{args.base_ref}...{args.feature_ref}"]), "feature diff read")
    secret_patterns = (
        r"AKIA[0-9A-Z]{16}",
        r"gh[pousr]_[A-Za-z0-9_]{30,}",
        r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
        r"op://",
    )
    if any(re.search(pattern, feature_diff) for pattern in secret_patterns):
        raise RuntimeError("Potential secret found in the production diff")
    results["secret_scan"] = "pass"

    if args.require_screenshots:
        results["screenshots"] = check_screenshots()

    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(results, indent=2, sort_keys=True))
    print("Full fork PR validation: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
