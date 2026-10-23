#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} == 0 ]] || {
  printf 'Run with sudo.\n' >&2
  exit 1
}

release=${1:?Usage: deploy.sh COMMIT_SHA IMAGE_AT_DIGEST}
image=${2:?Provide a GHCR image digest}

[[ "$release" =~ ^[0-9a-f]{40}$ ]] || exit 1

[[ "$image" =~ ^ghcr\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$ ]] || exit 1

release_dir="/opt/superstore/releases/$release"

[[ -f "$release_dir/deploy/production/compose.yml" ]] || exit 1

api_domain=$(
  sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env
)

[[ "$api_domain" =~ ^[A-Za-z0-9.-]+$ ]] || exit 1

exec 9>/var/lock/superstore-deploy.lock

flock -n 9 || {
  printf 'Another operation is running.\n' >&2
  exit 1
}

previous=""

if [[ -L /opt/superstore/current ]]; then
  previous=$(readlink -f /opt/superstore/current)
fi

umask 077

if [[ ! -f "$release_dir/images.lock.env" ]]; then
  install -m 600 \
    /etc/superstore/images.lock.env \
    "$release_dir/images.lock.env"
fi

if [[ -f "$release_dir/release.env" ]]; then
  existing_image=$(
    sed -n 's/^API_IMAGE=//p' "$release_dir/release.env"
  )

  [[ "$existing_image" == "$image" ]] || {
    printf 'This release already has another image; create a new commit.\n' >&2
    exit 1
  }
else
  printf 'API_IMAGE=%s\nAPP_RELEASE=%s\n' \
    "$image" \
    "$release" \
    > "$release_dir/release.env"
fi

dc() {
  bash "$release_dir/deploy/production/bin/compose.sh" "$@"
}

recover() {
  code=$?

  trap - ERR

  printf 'Deploy failed (exit %s).\n' "$code" >&2

  if [[
    -n "$previous" &&
    "$previous" != "$release_dir" &&
    -f "$previous/release.env"
  ]]; then
    if bash "$previous/deploy/production/bin/compose.sh" \
      up -d --wait --wait-timeout 120
    then
      printf 'Previous containers restored; verify HTTPS and readiness.\n' >&2
    else
      printf 'Automatic recovery failed; manual diagnosis is required.\n' >&2
    fi
  else
    printf 'No earlier release to restore. Keep containers for diagnosis.\n' >&2
  fi

  exit "$code"
}

trap recover ERR

install -d \
  -m 750 \
  -o 10001 \
  -g 10001 \
  /opt/superstore/data/staff \
  /opt/superstore/logs/api

install -d \
  -m 750 \
  -o root \
  -g 10001 \
  /etc/superstore/snowflake

/usr/sbin/nginx -t

dc config --quiet

dc pull

dc run --rm --no-deps api python -c '
import os

from core.config import get_settings
from core.internal_auth import list_staff_users

settings = get_settings()

secret = settings.staff_jwt_secret
assert len(secret) >= 32 and not secret.startswith("CHANGE_ME"), "Configure STAFF_JWT_SECRET"

key = os.environ.get("API_KEY", "")
assert len(key) >= 32 and not key.startswith("CHANGE_ME"), "Configure API_KEY"

assert settings.staff_cookie_secure, "Secure cookies are required"

list_staff_users()
'

dc up -d --wait --wait-timeout 120

dc exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=8)"

curl \
  --fail \
  --silent \
  --show-error \
  --retry 6 \
  --retry-all-errors \
  --retry-delay 3 \
  --max-time 8 \
  "https://$api_domain/api/health/live" \
  | python3 -c \
      'import json,sys; assert json.load(sys.stdin)["release"] == sys.argv[1]' \
      "$release"

if [[ -n "$previous" && "$previous" != "$release_dir" ]]; then
  ln -sfn "$previous" /opt/superstore/previous
fi

ln -sfn "$release_dir" /opt/superstore/current

trap - ERR

printf 'Backend release healthy: %s\n' "$release"