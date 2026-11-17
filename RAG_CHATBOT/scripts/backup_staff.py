"""Create a consistent SQLite snapshot, including committed WAL data."""

import os
import sqlite3

from contextlib import closing
from pathlib import Path


def create_snapshot(
    source: Path,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.umask(0o077)

    source_uri = (
        source.resolve().as_uri()
        + "?mode=ro"
    )

    with closing(
        sqlite3.connect(
            source_uri,
            uri=True,
        )
    ) as source_connection:
        with closing(
            sqlite3.connect(destination)
        ) as destination_connection:
            source_connection.backup(
                destination_connection
            )

            result = destination_connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            if result != "ok":
                raise RuntimeError(
                    "SQLite backup integrity check failed"
                )

    destination.chmod(0o600)


def main():
    source = Path(
        os.environ.get(
            "STAFF_DB_PATH",
            "/app/data/internal_users.db",
        )
    )

    destination = Path(
        "/backup/internal_users.db"
    )

    create_snapshot(
        source,
        destination,
    )

    print(
        "SQLite snapshot created and verified"
    )


if __name__ == "__main__":
    main()