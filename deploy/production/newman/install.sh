#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} == 0 ]] || { printf 'Run with sudo.\n' >&2; exit 1; }
[[ -f /etc/superstore/newman.env ]] || {
  printf 'Configure /etc/superstore/newman.env first.\n' >&2
  exit 1
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
install -d -m 750 -o 10001 -g 10001 /opt/superstore/metrics/newman

install -m 644 "$script_dir/superstore-newman@.service" /etc/systemd/system/
install -m 644 "$script_dir/superstore-newman@public.timer" /etc/systemd/system/
install -m 644 "$script_dir/superstore-newman@staff.timer" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now superstore-newman@public.timer superstore-newman@staff.timer
systemctl restart superstore-newman@public.timer superstore-newman@staff.timer
systemctl list-timers 'superstore-newman@*'
