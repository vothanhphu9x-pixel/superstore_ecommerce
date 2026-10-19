#!/usr/bin/env bash
set -Eeuo pipefail

[[ ${EUID} == 0 ]] || {
  printf 'Run with sudo.\n' >&2
  exit 1
}

mode=${1:?Usage: install-nginx.sh bootstrap|https}

case "$mode" in
  bootstrap)
    template=bootstrap.conf.template
    ;;
  https)
    template=api.conf.template
    ;;
  *)
    exit 1
    ;;
esac

config_dir=$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &&
  pwd -P
)

API_DOMAIN=$(
  sed -n 's/^API_DOMAIN=//p' /etc/superstore/stack.env
)

[[ "$API_DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || exit 1

export API_DOMAIN

if [[ "$mode" == https ]]; then
  [[ -s "/etc/letsencrypt/live/$API_DOMAIN/fullchain.pem" ]]
  [[ -s "/etc/letsencrypt/live/$API_DOMAIN/privkey.pem" ]]
fi

site=/etc/nginx/conf.d/superstore-api.conf
log_config=/etc/nginx/conf.d/00-superstore-logging.conf

umask 077

stage=$(mktemp -d /etc/nginx/superstore-stage.XXXXXX)

trap 'rm -f "$stage/site.old" "$stage/log.old" "$stage/site.new"; rmdir "$stage"' EXIT

had_site=0
had_log=0

if [[ -e "$site" ]]; then
  cp "$site" "$stage/site.old"
  had_site=1
fi

if [[ -e "$log_config" ]]; then
  cp "$log_config" "$stage/log.old"
  had_log=1
fi

restore() {
  code=$?

  trap - ERR

  if [[ "$had_site" == 1 ]]; then
    cp "$stage/site.old" "$site"
  else
    rm -f "$site"
  fi

  if [[ "$had_log" == 1 ]]; then
    cp "$stage/log.old" "$log_config"
  else
    rm -f "$log_config"
  fi

  printf 'Nginx update failed; previous files restored. Inspect nginx status.\n' >&2

  exit "$code"
}

trap restore ERR

envsubst '${API_DOMAIN}' \
  < "$config_dir/nginx/$template" \
  > "$stage/site.new"

install -m 644 \
  "$config_dir/nginx/logging.conf" \
  "$log_config"

install -m 644 \
  "$stage/site.new" \
  "$site"

/usr/sbin/nginx -t

systemctl reload nginx

trap - ERR

printf 'Nginx %s configuration installed for %s\n' \
  "$mode" \
  "$API_DOMAIN"