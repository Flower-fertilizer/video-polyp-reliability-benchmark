#!/usr/bin/env python3
"""Regenerate the deterministic SHA-256 inventory for public files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SHA256SUMS"
CHECKPOINTS = ROOT / "CHECKPOINTS.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint_paths() -> set[Path]:
    payload = json.loads(CHECKPOINTS.read_text(encoding="utf-8"))
    return {
        (ROOT / item["repository_path"]).resolve()
        for item in payload["artifacts"]
    }


def main() -> None:
    excluded = {OUTPUT.resolve()} | checkpoint_paths()
    paths = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.resolve() not in excluded
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
    )
    records = [
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in paths
    ]
    OUTPUT.write_text("\n".join(records) + "\n", encoding="utf-8")
    print(f"WROTE {OUTPUT.name} records={len(records)}")


if __name__ == "__main__":
    main()
