#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 2 ]] || {
  printf "Usage: %s S3_OBJECT_KEY EMPTY_RESTORE_DIRECTORY\n" "$0" >&2
  exit 1
}

: "${SUPERSTORE_BACKUP_BUCKET:?Set SUPERSTORE_BACKUP_BUCKET}"
: "${AGE_IDENTITY_FILE:?Set AGE_IDENTITY_FILE}"

object_key=$1
restore_root=$2

[[ -f "$AGE_IDENTITY_FILE" ]] || {
  printf "AGE identity file does not exist.\n" >&2
  exit 1
}

for command in age aws tar python3 mktemp date; do
  command -v "$command" >/dev/null 2>&1 || {
    printf "Required command is missing: %s\n" "$command" >&2
    exit 1
  }
done

if command -v sha256sum >/dev/null 2>&1; then
  checksum_command=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  checksum_command=(shasum -a 256)
else
  printf "SHA-256 utility is missing.\n" >&2
  exit 1
fi

mkdir -p "$restore_root"

restore_root=$(cd "$restore_root" && pwd -P)

work_dir=""
restore_dir=""

restore_complete=false

cleanup() {
  exit_code=$?

  trap - EXIT

  if [[ -n "$work_dir" && -d "$work_dir" ]]; then
    rm -rf -- "$work_dir"
  fi

  if [[ "$restore_complete" != true && -n "$restore_dir" ]]; then
    rm -rf -- "$restore_dir"
  fi

  exit "$exit_code"
}

trap cleanup EXIT

work_dir=$(mktemp -d \
  "$restore_root/download-$(date +%Y%m%d-%H%M%S)-XXXXXX")

restore_dir=$(mktemp -d \
  "$restore_root/restore-$(date +%Y%m%d-%H%M%S)-XXXXXX")

encrypted_name=$(basename "$object_key")
checksum_name="${encrypted_name}.sha256"
archive_name="${encrypted_name%.age}"

aws s3 cp \
  --only-show-errors \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}" \
  "$work_dir/$encrypted_name"

aws s3 cp \
  --only-show-errors \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}.sha256" \
  "$work_dir/$checksum_name"

(
  cd "$work_dir"
  "${checksum_command[@]}" -c "$checksum_name"
)

age \
  --decrypt \
  --identity "$AGE_IDENTITY_FILE" \
  --output "$work_dir/$archive_name" \
  "$work_dir/$encrypted_name"

tar -xzf "$work_dir/$archive_name" -C "$restore_dir"

database="$restore_dir/data/staff/internal_users.db"

[[ -f "$database" ]] || {
  printf "Staff SQLite database is missing from backup.\n" >&2
  exit 1
}

python3 - "$database" <<'PY'
import sqlite3
import sys
from pathlib import Path

database = Path(sys.argv[1]).resolve()

if not database.is_file():
    raise SystemExit("Database file does not exist")

uri = database.as_uri() + "?mode=ro"

with sqlite3.connect(uri, uri=True) as connection:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

if result != "ok":
    raise SystemExit("Restored SQLite integrity check failed")

print(f"SQLite integrity check passed: {database}")
PY

restore_complete=true

printf "Restore artifact verified at: %s\n" "$restore_dir"
