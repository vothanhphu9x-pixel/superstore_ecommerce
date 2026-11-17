#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} -eq 0 ]] || {
  printf "Run with sudo.\n" >&2
  exit 1
}

source_dir=$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &&
  pwd -P
)

for file in \
  backup.sh \
  superstore-backup.service \
  superstore-backup.timer
do
  [[ -f "$source_dir/$file" ]] || {
    printf "Missing required file: %s\n" "$source_dir/$file" >&2
    exit 1
  }
done

bash -n "$source_dir/backup.sh"

install -d \
  -o root \
  -g root \
  -m 700 \
  /usr/local/lib/superstore-backup

install -o root -g root -m 700 \
  "$source_dir/backup.sh" \
  /usr/local/lib/superstore-backup/backup.sh

install -o root -g root -m 644 \
  "$source_dir/superstore-backup.service" \
  /etc/systemd/system/superstore-backup.service

install -o root -g root -m 644 \
  "$source_dir/superstore-backup.timer" \
  /etc/systemd/system/superstore-backup.timer

systemd-analyze verify \
  /etc/systemd/system/superstore-backup.service \
  /etc/systemd/system/superstore-backup.timer
systemctl daemon-reload
systemctl enable superstore-backup.timer
systemctl restart superstore-backup.timer
systemctl is-active --quiet superstore-backup.timer || {
  printf "Failed to activate backup timer.\n" >&2
  exit 1
}

printf "Backup timer installed successfully.\n"