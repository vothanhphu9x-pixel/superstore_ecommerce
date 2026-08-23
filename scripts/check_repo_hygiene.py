#!/usr/bin/env python3
"""Minimal repository hygiene checks for local use and CI."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = (
    ".gitignore",
    ".gitattributes",
    "CONTRIBUTING.md",
    "Makefile",
    ".github/pull_request_template.md",
    ".github/workflows/quality.yml",
)


def main() -> int:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    if missing:
        print("Missing required repository files:")
        print("\n".join(f"- {path}" for path in missing))
        return 1

    print("Repository hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
