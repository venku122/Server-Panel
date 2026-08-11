#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def git_sha(ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic fork screenshot manifest.")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    evidence_dir = (ROOT / config["evidenceDir"]).resolve()
    if ROOT not in evidence_dir.parents:
        raise RuntimeError("Evidence directory must stay within the repository")

    captures: list[dict[str, str]] = []
    for phase in ("before", "after"):
        for image_path in sorted((evidence_dir / phase).glob("*.png")):
            with Image.open(image_path) as image:
                viewport = f"{image.width}x{image.height}"
            captures.append(
                {
                    "kind": phase,
                    "path": image_path.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    "viewport": viewport,
                }
            )

    if not captures:
        raise RuntimeError("No before/after PNG captures found")
    manifest = {
        "base": {"ref": config["baseRef"], "sha": git_sha(config["baseRef"])},
        "feature": {"ref": config["featureRef"], "sha": git_sha(config["featureRef"])},
        "captures": captures,
    }
    output = evidence_dir / "manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
