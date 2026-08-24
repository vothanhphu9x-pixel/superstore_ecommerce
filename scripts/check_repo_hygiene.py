#!/usr/bin/env python3
"""Fail when local secrets or generated runtime artifacts are tracked by Git."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_EXAMPLES = {
    "RAG_CHATBOT/.env.example",
    "RAG_CHATBOT/frontend/.env.example",
    "data_platform/.env.example",
    "data_platform/Data_warehouse/.env.example",
    "data_platform/Debezium_producer/.env.example",
    "data_platform/csv_loader/.env.example",
    "data_platform/minio_consumer/.env.example",
    "data_platform/superstore_db/.dbt/profiles.yml.example",
    "ml_platform/.env.example",
    "odoo_dev/.env.example",
    "odoo_dev/odoo.conf.example",
}

FORBIDDEN_EXACT = {
    "data_platform/superstore_db/.dbt/.user.yml",
    "data_platform/superstore_db/.dbt/profiles.yml",
    "odoo_dev/odoo.conf",
}

FORBIDDEN_GLOBS = (
    "*.db",
    "*.log",
    "*.sqlite",
    "*.sqlite3",
    "*/.next/*",
    "*/__pycache__/*",
    "*/node_modules/*",
    "*/qdrant_storage/*",
    "*/config/internal_users.json",
    "*/config/customer_accounts.db*",
    "*/~$*",
)

ENV_EXAMPLE_PAIRS = (
    ("RAG_CHATBOT/.env", "RAG_CHATBOT/.env.example"),
    ("RAG_CHATBOT/frontend/.env.local", "RAG_CHATBOT/frontend/.env.example"),
    ("data_platform/.env", "data_platform/.env.example"),
    ("data_platform/Data_warehouse/.env", "data_platform/Data_warehouse/.env.example"),
    ("data_platform/Debezium_producer/.env", "data_platform/Debezium_producer/.env.example"),
    ("data_platform/csv_loader/.env", "data_platform/csv_loader/.env.example"),
    ("data_platform/minio_consumer/.env", "data_platform/minio_consumer/.env.example"),
    ("ml_platform/.env", "ml_platform/.env.example"),
    ("odoo_dev/.env", "odoo_dev/.env.example"),
)


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def dotenv_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key.replace("_", "").isalnum() and key[0].isalpha():
            keys.add(key)
    return keys


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    # Include non-ignored untracked files so the check is useful before the first `git add`.
    # Ignored local secrets remain excluded by Git itself.
    tracked = set(git_lines("ls-files", "--cached", "--others", "--exclude-standard"))

    for path in sorted(tracked):
        name = Path(path).name
        if path in FORBIDDEN_EXACT:
            errors.append(f"local config is tracked: {path}")
        if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
            errors.append(f"environment secret file is tracked: {path}")
        if any(fnmatch.fnmatch(path, pattern) for pattern in FORBIDDEN_GLOBS):
            errors.append(f"runtime/generated file is tracked: {path}")

        absolute = ROOT / path
        if absolute.is_file() and absolute.stat().st_size > 10 * 1024 * 1024:
            warnings.append(f"tracked file is larger than 10 MiB: {path}")

    ignored_but_tracked = git_lines("ls-files", "-ci", "--exclude-standard")
    for path in ignored_but_tracked:
        errors.append(f"tracked file is also ignored: {path}")

    missing_examples = REQUIRED_EXAMPLES - tracked
    for path in sorted(missing_examples):
        errors.append(f"required safe example is not tracked: {path}")

    for local_name, example_name in ENV_EXAMPLE_PAIRS:
        local_path = ROOT / local_name
        example_path = ROOT / example_name
        if not local_path.exists() or not example_path.exists():
            continue
        missing_keys = dotenv_keys(local_path) - dotenv_keys(example_path)
        if missing_keys:
            errors.append(
                f"{example_name} misses keys used by {local_name}: "
                + ", ".join(sorted(missing_keys))
            )

    profile_example = ROOT / "data_platform/superstore_db/.dbt/profiles.yml.example"
    if profile_example.exists():
        profile_text = profile_example.read_text(encoding="utf-8")
        if "env_var('SNOWFLAKE_PASSWORD')" not in profile_text:
            errors.append("dbt profile example must read SNOWFLAKE_PASSWORD from the environment")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Repository hygiene failed with {len(errors)} error(s).")
        return 1

    print(f"Repository hygiene passed: {len(tracked)} versioned candidates checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
