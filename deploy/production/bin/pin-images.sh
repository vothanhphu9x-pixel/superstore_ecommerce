#!/usr/bin/env bash
set -Eeuo pipefail

source_file=${1:?Usage: pin-images.sh images.sources.env output.lock.env}
output_file=${2:?Provide a NEW output file}

if [[ -e "$output_file" ]]; then
  printf 'Refusing to overwrite %s. Review a new lock separately.\n' \
    "$output_file" >&2

  exit 1
fi

umask 077

temporary=$(mktemp)

trap 'rm -f "$temporary"' EXIT

while IFS='=' read -r key reference; do
  [[ -z "$key" || "$key" == \#* ]] && continue

  [[ "$key" =~ ^[A-Z_]+_IMAGE$ ]] || exit 1

  docker pull "$reference" >&2

  digest=$(
    docker image inspect \
      --format '{{index .RepoDigests 0}}' \
      "$reference"
  )

  [[ "$digest" =~ @sha256:[0-9a-f]{64}$ ]] || exit 1

  printf '%s=%s\n' \
    "$key" \
    "$digest" \
    >> "$temporary"

done < "$source_file"

install -m 600 \
  "$temporary" \
  "$output_file"

printf 'Pinned images saved to %s\n' "$output_file"