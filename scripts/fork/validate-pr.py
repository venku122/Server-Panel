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
REVIEW_ONLY_PREFIXES = (
    ".github/",
    "artifacts/",
    "fork_tests/",
    "fork_tools/",
    "scripts/fork/",
)


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


def git_ref_sha(ref: str) -> str:
    return require(run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"]), f"resolve {ref}").strip()


def require_stacked_feature(base_ref: str, feature_ref: str) -> None:
    result = run(["git", "merge-base", "--is-ancestor", base_ref, feature_ref])
    if result.returncode:
        raise RuntimeError(f"Feature ref {feature_ref} is not stacked directly on an ancestor {base_ref}")


def require_review_production_identity(feature_ref: str) -> None:
    changed = require(run(["git", "diff", "--name-only", feature_ref, "HEAD"]), "review production identity")
    unexpected = [path for path in changed.splitlines() if path and not path.startswith(REVIEW_ONLY_PREFIXES)]
    if unexpected:
        raise RuntimeError(
            "Review HEAD contains production changes absent from the feature ref\n"
            + "\n".join(f"- {path}" for path in unexpected)
        )


def changed_existing_paths(base_ref: str, feature_ref: str, suffixes: tuple[str, ...]) -> list[str]:
    output = require(
        run(["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...{feature_ref}"]),
        "changed production path lookup",
    )
    return sorted(path for path in output.splitlines() if path.endswith(suffixes) and (ROOT / path).is_file())


def path_exists_at_ref(ref: str, path: str) -> bool:
    return run(["git", "cat-file", "-e", f"{ref}:{path}"]).returncode == 0


def resolve_repo_path(value: Path, *, label: str) -> Path:
    resolved = (value if value.is_absolute() else ROOT / value).resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise RuntimeError(f"{label} must stay within the repository: {value}")
    return resolved


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


def eslint_path_diagnostics(repo: Path, paths: list[str]) -> list[str]:
    result = run(
        [
            str(NODE_BIN / "eslint"),
            "--config",
            str(TOOLS / "eslint.config.mjs"),
            "--no-ignore",
            "--format",
            "json",
            *paths,
        ],
        cwd=repo,
    )
    payload = json.loads(result.stdout or "[]")
    diagnostics: list[str] = []
    for file_result in payload:
        source = Path(file_result["filePath"])
        try:
            relative = source.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            relative = source.name
        diagnostics.extend(
            f"{relative}:{item.get('ruleId')}:{item['message']}" for item in file_result.get("messages", [])
        )
    return diagnostics


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


def stylelint_path_diagnostics(repo: Path, paths: list[str]) -> list[str]:
    result = run(
        [
            str(NODE_BIN / "stylelint"),
            "--config",
            str(TOOLS / "stylelint.config.mjs"),
            "--formatter",
            "json",
            *paths,
        ],
        cwd=repo,
    )
    payload = json.loads(result.stdout or "[]")
    diagnostics: list[str] = []
    for file_result in payload:
        source = Path(file_result["source"])
        try:
            relative = source.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            relative = source.name
        for warning in file_result.get("warnings", []):
            message = re.sub(r"\d+", "<n>", warning["text"])
            diagnostics.append(f"{relative}:{warning['rule']}:{message}")
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


def check_changed_frontend(base_ref: str, feature_ref: str, baseline: Path) -> dict[str, object]:
    templates = changed_existing_paths(base_ref, feature_ref, (".html", ".jinja", ".jinja2", ".j2"))
    stylesheets = changed_existing_paths(base_ref, feature_ref, (".css",))
    scripts = changed_existing_paths(base_ref, feature_ref, (".js", ".mjs", ".cjs"))
    new_stylesheets = [path for path in stylesheets if not path_exists_at_ref(base_ref, path)]
    legacy_stylesheets = [path for path in stylesheets if path not in new_stylesheets]
    new_scripts = [path for path in scripts if not path_exists_at_ref(base_ref, path)]
    legacy_scripts = [path for path in scripts if path not in new_scripts]

    if templates:
        require(
            run(
                [
                    sys.executable,
                    "-m",
                    "djlint",
                    "--configuration",
                    str(TOOLS / "djlint.toml"),
                    *templates,
                    "--check",
                    "--lint",
                ]
            ),
            "changed Jinja template format/lint",
        )
        inline_styles = [
            path
            for path in templates
            if re.search(r"\sstyle\s*=", (ROOT / path).read_text(encoding="utf-8"), re.IGNORECASE)
        ]
        if inline_styles:
            raise RuntimeError(
                "Changed templates contain inline style attributes\n" + "\n".join(f"- {path}" for path in inline_styles)
            )

    if new_stylesheets:
        require(
            run(
                [
                    str(NODE_BIN / "stylelint"),
                    "--config",
                    str(TOOLS / "stylelint.config.mjs"),
                    *new_stylesheets,
                ]
            ),
            "new CSS lint",
        )

    if new_scripts:
        require(
            run(
                [
                    str(NODE_BIN / "eslint"),
                    "--config",
                    str(TOOLS / "eslint.config.mjs"),
                    "--no-ignore",
                    *new_scripts,
                ]
            ),
            "new JavaScript lint",
        )
    for path in scripts:
        require(run(["node", "--check", path]), f"JavaScript syntax for {path}")
    if new_scripts:
        require(
            run(
                [
                    str(NODE_BIN / "tsc"),
                    "--allowJs",
                    "--checkJs",
                    "--noEmit",
                    "--target",
                    "ES2022",
                    "--module",
                    "ES2022",
                    "--moduleResolution",
                    "node",
                    "--lib",
                    "ES2022,DOM,DOM.Iterable",
                    "--skipLibCheck",
                    *new_scripts,
                ]
            ),
            "new JavaScript module type check",
        )

    legacy_style_ratchet = (
        ratchet(
            "Changed legacy CSS",
            lambda repo: stylelint_path_diagnostics(repo, legacy_stylesheets),
            baseline,
        )
        if legacy_stylesheets
        else {"baseline": 0, "current": 0, "removed": 0}
    )
    legacy_script_ratchet = (
        ratchet(
            "Changed legacy JavaScript",
            lambda repo: eslint_path_diagnostics(repo, legacy_scripts),
            baseline,
        )
        if legacy_scripts
        else {"baseline": 0, "current": 0, "removed": 0}
    )

    return {
        "templates": len(templates),
        "stylesheets": len(stylesheets),
        "new_stylesheets": len(new_stylesheets),
        "legacy_stylesheet_lint": legacy_style_ratchet,
        "scripts": len(scripts),
        "new_script_typechecks": len(new_scripts),
        "legacy_script_lint": legacy_script_ratchet,
    }


def added_lines(base_ref: str, feature_ref: str, path: str) -> list[str]:
    diff = require(
        run(["git", "diff", "--unified=0", f"{base_ref}...{feature_ref}", "--", path]),
        f"added-line lookup for {path}",
    )
    return [
        line[1:].strip()
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++") and line[1:].strip()
    ]


def check_template_architecture(base_ref: str, feature_ref: str) -> dict[str, int]:
    matrix_path = TOOLS / "validation" / "pr02-route-parity.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    routes = matrix.get("routes", [])
    required_fields = {
        "name",
        "path",
        "role",
        "template",
        "context",
        "js_ids",
        "empty_state",
        "local_behavior",
        "remote_behavior",
        "response_diagnostics",
    }
    if len(routes) != 16:
        raise RuntimeError("PR2 route parity matrix must cover exactly 16 source-backed routes")

    app_script = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    critical_ids: set[str] = set()
    for route in routes:
        missing_fields = sorted(required_fields - set(route))
        if missing_fields:
            raise RuntimeError(f"Route parity entry {route.get('name', '<unnamed>')} is missing: {missing_fields}")
        template = ROOT / str(route["template"])
        if not template.is_file():
            raise RuntimeError(f"Route parity template does not exist: {route['template']}")
        source = template.read_text(encoding="utf-8")
        if re.search(r"\sstyle\s*=", source, re.IGNORECASE):
            raise RuntimeError(f"Converted template contains an inline style: {route['template']}")
        for dom_id in route["js_ids"]:
            if not re.search(rf'\bid=["\']{re.escape(dom_id)}["\']', source):
                raise RuntimeError(f"Critical DOM id {dom_id!r} is missing from {route['template']}")
            if dom_id not in app_script:
                raise RuntimeError(f"Critical DOM id {dom_id!r} is not referenced by static/app.js")
            critical_ids.add(dom_id)

    allowlist_path = TOOLS / "validation" / "legacy-css-allowlist.txt"
    allowed = {
        line.strip()
        for line in allowlist_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    legacy_additions = [
        line
        for line in added_lines(base_ref, feature_ref, "static/style.css")
        if not line.startswith("/*") and line not in allowed
    ]
    if legacy_additions:
        preview = "\n".join(f"- {line}" for line in legacy_additions[:20])
        raise RuntimeError(f"Legacy static/style.css received unallowlisted additions\n{preview}")

    return {"routes": len(routes), "critical_js_ids": len(critical_ids), "legacy_css_additions": 0}


def check_changed_python(base_ref: str, feature_ref: str) -> dict[str, object]:
    paths = changed_existing_paths(base_ref, feature_ref, (".py",))
    managed_paths = [path for path in paths if path.startswith("server_panel/")]
    if managed_paths:
        require(
            run([sys.executable, "-m", "ruff", "check", "--config", str(TOOLS / "ruff.toml"), *managed_paths]),
            "campaign-owned Python lint",
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
                    *managed_paths,
                ]
            ),
            "campaign-owned Python format",
        )
        require(
            run(
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "--config-file",
                    str(TOOLS / "mypy.ini"),
                    *managed_paths,
                ]
            ),
            "campaign-owned Python type check",
        )
    return {"changed": len(paths), "campaign_owned_strict": len(managed_paths)}


def check_screenshots(
    evidence_dir: Path,
    *,
    base_ref: str,
    feature_ref: str,
    browser_results: Path,
    expected_assertions: list[str],
    expected_viewports: list[str],
) -> dict[str, int]:
    evidence_root = resolve_repo_path(evidence_dir, label="evidence directory")
    manifest_path = evidence_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_base = manifest.get("base", {})
    if manifest_base.get("sha") != git_ref_sha(base_ref):
        raise RuntimeError("Screenshot manifest base SHA does not match the configured production base")
    manifest_feature = manifest.get("feature", {})
    if manifest_feature and manifest_feature.get("sha") != git_ref_sha(feature_ref):
        raise RuntimeError("Screenshot manifest feature SHA does not match the configured production feature")
    if not manifest_feature and evidence_root.name != "pr1":
        raise RuntimeError("Screenshot manifest must record the configured production feature SHA")

    captures = manifest.get("captures", [])
    if not captures:
        raise RuntimeError("Screenshot manifest contains no captures")
    for capture in captures:
        path = resolve_repo_path(Path(capture["path"]), label="screenshot path")
        if path != evidence_root and evidence_root not in path.parents:
            raise RuntimeError(f"Screenshot path is outside the configured evidence directory: {capture['path']}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != capture["sha256"]:
            raise RuntimeError(f"Screenshot hash mismatch: {capture['path']}")

    validation_path = resolve_repo_path(evidence_root / browser_results, label="browser results")
    if validation_path != evidence_root and evidence_root not in validation_path.parents:
        raise RuntimeError("Browser results must stay within the configured evidence directory")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if validation.get("consoleErrors") or validation.get("pageErrors"):
        raise RuntimeError("Browser evidence contains unexpected console or page errors")
    assertions = validation.get("assertions", [])
    if not assertions:
        raise RuntimeError("Browser evidence contains no assertions")
    assertion_ids = {assertion.get("id") if isinstance(assertion, dict) else assertion for assertion in assertions}
    failed = [
        assertion.get("id", "unnamed")
        for assertion in assertions
        if isinstance(assertion, dict) and assertion.get("passed") is False
    ]
    if failed:
        raise RuntimeError("Browser evidence contains failed assertions: " + ", ".join(failed))
    missing_assertions = sorted(set(expected_assertions) - assertion_ids)
    if missing_assertions:
        raise RuntimeError("Browser evidence is missing assertions: " + ", ".join(missing_assertions))
    if any(capture.get("horizontalOverflow") for capture in validation.get("captures", [])):
        raise RuntimeError("Browser evidence contains horizontal overflow")
    captured_viewports = {capture.get("viewport") for capture in captures}
    missing_viewports = sorted(set(expected_viewports) - captured_viewports)
    if missing_viewports:
        raise RuntimeError("Screenshot manifest is missing viewports: " + ", ".join(missing_viewports))
    return {"captures": len(captures), "browser_assertions": len(assertions)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete fork PR validation gate.")
    parser.add_argument("--base-ref", default="upstream/main")
    parser.add_argument("--feature-ref", default="origin/feature/01-server-scope")
    parser.add_argument("--evidence-dir", type=Path, default=Path("artifacts/pr1"))
    parser.add_argument("--browser-results", type=Path, default=Path("after/validation-results.json"))
    parser.add_argument("--capture-script", type=Path, default=Path("scripts/fork/capture-pr1.cjs"))
    parser.add_argument("--expected-browser-assertion", action="append", default=[])
    parser.add_argument("--expected-viewport", action="append", default=[])
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--require-screenshots", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results: dict[str, object] = {}
    if not args.allow_dirty:
        status = require(run(["git", "status", "--porcelain"]), "git status")
        if status:
            raise RuntimeError("Full PR gate requires a clean worktree")

    require_stacked_feature(args.base_ref, args.feature_ref)
    require_review_production_identity(args.feature_ref)
    results["stack"] = {
        "base": git_ref_sha(args.base_ref),
        "feature": git_ref_sha(args.feature_ref),
        "review_production_identity": "pass",
    }

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
    results["template_architecture"] = check_template_architecture(args.base_ref, args.feature_ref)
    changed_app_lines = changed_lines(args.base_ref, args.feature_ref, "app.py")
    format_overlap = formatting_touches_changed_lines(ROOT / "app.py", changed_app_lines)
    if format_overlap:
        raise RuntimeError(f"Ruff formatter would alter changed app.py lines: {format_overlap[:20]}")
    results["ruff_format"] = {"changed_lines_clean": len(changed_app_lines)}

    with tempfile.TemporaryDirectory(prefix="server-panel-base-") as temp:
        baseline = Path(temp)
        extract_ref(args.base_ref, baseline)
        results["changed_frontend"] = check_changed_frontend(args.base_ref, args.feature_ref, baseline)
        results["changed_python"] = check_changed_python(args.base_ref, args.feature_ref)
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
    require(run(["node", "--check", "static/app.js"]), "JavaScript syntax")
    capture_script = resolve_repo_path(args.capture_script, label="capture script")
    capture_relative = str(capture_script.relative_to(ROOT))
    require(run(["node", "--check", capture_relative]), "screenshot automation syntax")
    require(
        run(
            [
                str(NODE_BIN / "eslint"),
                "--config",
                str(TOOLS / "eslint.config.mjs"),
                "--no-ignore",
                capture_relative,
            ]
        ),
        "screenshot automation lint",
    )
    results["javascript_syntax"] = {"app": "pass", "screenshot_automation": "pass"}

    for path in [
        ROOT / "app.py",
        *sorted((ROOT / "server_panel").rglob("*.py")),
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
        results["screenshots"] = check_screenshots(
            args.evidence_dir,
            base_ref=args.base_ref,
            feature_ref=args.feature_ref,
            browser_results=args.browser_results,
            expected_assertions=args.expected_browser_assertion,
            expected_viewports=args.expected_viewport,
        )

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
