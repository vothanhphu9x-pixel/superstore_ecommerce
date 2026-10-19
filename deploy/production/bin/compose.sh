#!/usr/bin/env bash
set -Eeuo pipefail

config_dir=$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &&
  pwd -P
)

release_dir=$(
  cd -- "$config_dir/../.." &&
  pwd -P
)

exec docker compose -p superstore \
  --env-file /etc/superstore/stack.env \
  --env-file "$release_dir/images.lock.env" \
  --env-file "$release_dir/release.env" \
  -f "$config_dir/compose.yaml" \
  "$@"