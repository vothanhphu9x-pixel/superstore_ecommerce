#!/usr/bin/env bash
set -Eeuo pipefail

readonly BACKUP_ENV="/etc/superstore/backup.env"
readonly WORK_ROOT="/var/lib/superstore-backup"

[[ ${EUID} == 0 ]] || {
  printf "Run as root.\n" >&2
  exit 1
}

[[ -r "$BACKUP_ENV" ]] || {
  printf "Missing %s\n" "$BACKUP_ENV" >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$BACKUP_ENV"
set +a

for command in age aws docker tar sha256sum python3 flock; do
  command -v "$command" >/dev/null 2>&1 || {
    printf "Required command is missing: %s\n" "$command" >&2
    exit 1
  }
done

for variable in \
  AWS_DEFAULT_REGION \
  AWS_ACCESS_KEY_ID \
  AWS_SECRET_ACCESS_KEY \
  SUPERSTORE_BACKUP_BUCKET \
  SUPERSTORE_BACKUP_PREFIX \
  SUPERSTORE_AGE_RECIPIENT
do
  [[ -n "${!variable:-}" ]] || {
    printf "Missing required variable: %s\n" "$variable" >&2
    exit 1
  }
done


AWS_IDENTITY="$(aws sts get-caller-identity \
  --query 'Arn' \
  --output text)"

EXPECTED_IAM_USER="superstore-vps-backup-writer"

[[ "$AWS_IDENTITY" == *":user/${EXPECTED_IAM_USER}" ]] || {
  printf "Unexpected AWS identity: %s\n" "$AWS_IDENTITY" >&2
  exit 1
}

printf "AWS identity verified: %s\n" "$AWS_IDENTITY"


[[ "$SUPERSTORE_BACKUP_BUCKET" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] || {
  printf "Invalid SUPERSTORE_BACKUP_BUCKET.\n" >&2
  exit 1
}

mkdir -p "$WORK_ROOT"
chmod 700 "$WORK_ROOT"

exec 9>/var/lock/superstore-backup.lock

flock -n 9 || {
  printf "Another backup is already running.\n"
  exit 0
}

work_dir=""
api_container=""

cleanup() {
  exit_code=$?

  trap - EXIT

  if [[ -n "$api_container" ]]; then
    docker exec "$api_container" \
      rm -f /tmp/superstore-staff-backup.db \
      >/dev/null 2>&1 || true
  fi

  if [[ -n "$work_dir" && -d "$work_dir" ]]; then
    rm -rf -- "$work_dir"
  fi

  exit "$exit_code"
}

trap cleanup EXIT

mapfile -t api_containers < <(
  docker ps --quiet \
    --filter "label=com.docker.compose.project=superstore" \
    --filter "label=com.docker.compose.service=api"
)

[[ ${#api_containers[@]} -eq 1 ]] || {
  printf "Expected exactly one running Superstore API container.\n" >&2
  exit 1
}

api_container="${api_containers[0]}"

timestamp=$(date -u +"%Y%m%dT%H%M%SZ")
short_hostname=$(hostname -s)
backup_id="${timestamp}-$(cat /proc/sys/kernel/random/uuid)"

[[ "$short_hostname" =~ ^[A-Za-z0-9._-]+$ ]] || {
  printf "Hostname contains unsupported characters.\n" >&2
  exit 1
}

work_dir=$(mktemp -d "$WORK_ROOT/work.XXXXXX")

stage_dir="$work_dir/stage"
artifact_dir="$work_dir/artifacts"

mkdir -p \
  "$stage_dir/data/staff" \
  "$stage_dir/etc/superstore" \
  "$stage_dir/etc/nginx/conf.d" \
  "$stage_dir/etc/sudoers.d" \
  "$stage_dir/home/deploy/.ssh" \
  "$stage_dir/metadata" \
  "$artifact_dir"

copy_file() {
  source_path=$1
  relative_destination=$2

  [[ -f "$source_path" ]] || {
    printf "Required backup file is missing: %s\n" \
      "$source_path" >&2
    exit 1
  }

  install -D -o root -g root -m 600 \
    "$source_path" \
    "$stage_dir/$relative_destination"
}

docker exec "$api_container" \
  env STAFF_BACKUP_DESTINATION=/tmp/superstore-staff-backup.db \
  python -m scripts.backup_staff

docker cp \
  "$api_container:/tmp/superstore-staff-backup.db" \
  "$stage_dir/data/staff/internal_users.db"

docker exec "$api_container" \
  rm -f /tmp/superstore-staff-backup.db

python3 - "$stage_dir/data/staff/internal_users.db" <<'PY'
import sqlite3
import sys
from pathlib import Path

database = Path(sys.argv[1]).resolve()
uri = database.as_uri() + "?mode=ro"

with sqlite3.connect(uri, uri=True) as connection:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

if result != "ok":
    raise SystemExit("SQLite integrity check failed")
PY

copy_file /etc/superstore/app.env etc/superstore/app.env
copy_file /etc/superstore/stack.env etc/superstore/stack.env
copy_file /etc/superstore/grafana.env etc/superstore/grafana.env
copy_file /etc/superstore/images.lock.env etc/superstore/images.lock.env
copy_file /etc/superstore/images.source.env etc/superstore/images.source.env
copy_file /etc/nginx/conf.d/superstore-api.conf etc/nginx/conf.d/superstore-api.conf
copy_file /etc/nginx/conf.d/00-superstore-logging.conf etc/nginx/conf.d/00-superstore-logging.conf
copy_file /etc/sudoers.d/superstore-deploy etc/sudoers.d/superstore-deploy
copy_file /home/deploy/.ssh/authorized_keys home/deploy/.ssh/authorized_keys

if [[ -d /etc/superstore/snowflake ]]; then
  mkdir -p "$stage_dir/etc/superstore/snowflake"
  cp -a /etc/superstore/snowflake/. \
    "$stage_dir/etc/superstore/snowflake/"
  chmod -R go-rwx \
    "$stage_dir/etc/superstore/snowflake"
fi

CURRENT_RELEASE="/opt/superstore/current"
current_release="$(readlink -f "$CURRENT_RELEASE")"

[[ -n "$current_release" && -d "$current_release" ]] || {
  printf "Current release is missing or invalid.\n" >&2
  exit 1
}

release_sha="$(basename "$current_release")"

[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] || {
  printf "Invalid release SHA: %s\n" "$release_sha" >&2
  exit 1
}

printf "Current release verified: %s\n" "$release_sha"


api_image=$(docker inspect \
  --format '{{.Config.Image}}' \
  "$api_container")

[[ "$api_image" =~ ^ghcr\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$ ]] || {
  printf "Running API image is not pinned by GHCR digest.\n" >&2
  exit 1
}

printf "backup_format=superstore-v1\n" \
  > "$stage_dir/metadata/backup-manifest.env"

printf "created_at_utc=%s\n" "$timestamp" \
  >> "$stage_dir/metadata/backup-manifest.env"

printf "hostname=%s\n" "$short_hostname" \
  >> "$stage_dir/metadata/backup-manifest.env"

printf "release_sha=%s\n" "$release_sha" \
  >> "$stage_dir/metadata/backup-manifest.env"

printf "api_image=%s\n" "$api_image" \
  >> "$stage_dir/metadata/backup-manifest.env"

dpkg-query -W -f='${binary:Package}\t${Version}\n' \
  > "$stage_dir/metadata/apt-packages.tsv"

archive_name="superstore-${backup_id}.tar.gz"
encrypted_name="${archive_name}.age"
checksum_name="${encrypted_name}.sha256"

(
  cd "$artifact_dir"

  tar --create \
    --gzip \
    --file "$archive_name" \
    --directory "$stage_dir" \
    .

  age \
    --recipient "$SUPERSTORE_AGE_RECIPIENT" \
    --output "$encrypted_name" \
    "$archive_name"

  sha256sum "$encrypted_name" > "$checksum_name"
)

object_key="${SUPERSTORE_BACKUP_PREFIX%/}/${short_hostname}/${timestamp}/${encrypted_name}"

aws s3 cp \
  --only-show-errors \
  "$artifact_dir/$encrypted_name" \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}"

aws s3 cp \
  --only-show-errors \
  "$artifact_dir/$checksum_name" \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}.sha256"

# Create temporary verification directory.
verify_dir="$work_dir/verify"
mkdir -p "$verify_dir"
chmod 700 "$verify_dir"

# Download encrypted archive from S3.
aws s3 cp \
  --only-show-errors \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}" \
  "$verify_dir/$encrypted_name"

# Download checksum file from S3.
aws s3 cp \
  --only-show-errors \
  "s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}.sha256" \
  "$verify_dir/$checksum_name"

# Verify downloaded archive against downloaded checksum.
(
  cd "$verify_dir"
  sha256sum --check "$checksum_name"
)

printf "Remote SHA-256 verification successful.\n"

logger -t superstore-backup \
  "Backup uploaded: s3://${SUPERSTORE_BACKUP_BUCKET}/${object_key}"

printf "Backup completed: s3://%s/%s\n" \
  "$SUPERSTORE_BACKUP_BUCKET" \
  "$object_key"
