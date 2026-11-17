#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} == 0 ]] || { printf 'Run with sudo.\n' >&2; exit 1; }

kind=${1:?Usage: run.sh public|staff}
[[ "$kind" == public || "$kind" == staff ]] || exit 2
mode=${2:-manual}
[[ "$mode" == manual || "$mode" == timer ]] || exit 2

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
release_dir=$(cd -- "$script_dir/../../.." && pwd -P)
postman_dir="$release_dir/postman"
metrics_dir=/opt/superstore/metrics/newman
env_file=/etc/superstore/newman.env
image="superstore-newman:$(basename "$release_dir")"

[[ -d "$postman_dir/collections" ]] || {
  printf 'Postman YAML is missing from this release.\n' >&2
  exit 1
}
[[ -f "$env_file" ]] || {
  printf 'Create /etc/superstore/newman.env before running Newman.\n' >&2
  exit 1
}

exec 9>"/var/lock/superstore-newman-$kind.lock"
flock -w 120 9 || { printf 'Another %s run is still active.\n' "$kind" >&2; exit 1; }

install -d -m 750 -o 10001 -g 10001 "$metrics_dir"

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build --pull --tag "$image" "$script_dir"
fi

timeout 240s docker run --rm --pull never \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --user 10001:10001 \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 128 \
  --memory 512m \
  --cpus 1 \
  --env-file "$env_file" \
  --env POSTMAN_ROOT=/postman \
  --env METRICS_DIR=/metrics \
  --env "NEWMAN_RUN_MODE=$mode" \
  --mount "type=bind,source=$postman_dir,target=/postman,readonly" \
  --mount "type=bind,source=$metrics_dir,target=/metrics" \
  "$image" "$kind"
