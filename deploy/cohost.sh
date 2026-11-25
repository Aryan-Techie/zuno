#!/usr/bin/env bash
# Serve ZUNO through a Caddy that another stack on the same box already runs.
#
# Only one process can own :80 and :443. Where that is already a Caddy
# container, ZUNO runs without its own (the compose file keeps that service
# behind the "standalone" profile) and this script teaches the existing Caddy
# ZUNO's two hostnames instead:
#
#   bash deploy/cohost.sh <caddy container> <that Caddy's Caddyfile on the host>
#
# Safe to re-run: the ZUNO block is replaced, never duplicated, and the new
# config is validated inside the container before Caddy reloads it. On a
# failed validation the original file is put back untouched.
set -euo pipefail
cd "$(dirname "$0")/.."

CADDY="${1:?caddy container name}"
CADDYFILE="${2:?path to the Caddyfile that container mounts}"
ENV_FILE="deploy/.env.production"

value() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2- | tr -d '\r'; }
ZUNO_DOMAIN="$(value ZUNO_DOMAIN)"
ZUNO_CRM_DOMAIN="$(value ZUNO_CRM_DOMAIN)"
[ -n "$ZUNO_DOMAIN" ] && [ -n "$ZUNO_CRM_DOMAIN" ] || { echo "set ZUNO_DOMAIN and ZUNO_CRM_DOMAIN in $ENV_FILE" >&2; exit 1; }

# The other Caddy reaches ZUNO over ZUNO's compose network. Service names
# like "backend" exist on both networks once it is attached to two, so the
# block below addresses ZUNO by container name, which is unambiguous.
docker network connect zuno_default "$CADDY" 2>/dev/null || true

BEGIN="# >>> zuno (managed by zuno/deploy/cohost.sh)"
END="# <<< zuno"
block="$(grep -v '^#' deploy/Caddyfile \
  | sed -e "s/{\$ZUNO_DOMAIN}/$ZUNO_DOMAIN/" \
        -e "s/{\$ZUNO_CRM_DOMAIN}/$ZUNO_CRM_DOMAIN/" \
        -e 's/espocrm-websocket:8080/zuno-espocrm-ws:8080/' \
        -e 's/espocrm:80/zuno-espocrm:80/' \
        -e 's/backend:8000/zuno-backend:8000/' \
        -e 's/frontend:3000/zuno-frontend:3000/')"

backup="$(mktemp)"
cp "$CADDYFILE" "$backup"
rendered="$(mktemp)"
awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} !skip{print} $0==e{skip=0}' "$backup" > "$rendered"
printf '\n%s\n%s\n%s\n' "$BEGIN" "$block" "$END" >> "$rendered"

# Write through the existing file rather than replacing it: the Caddyfile is
# bind-mounted into the container as a single file, and a new inode (what
# mv or sed -i create) would leave the container reading the old one.
cat "$rendered" > "$CADDYFILE"

if docker exec "$CADDY" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null; then
  docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
  echo "Caddy now serves https://$ZUNO_DOMAIN and https://$ZUNO_CRM_DOMAIN"
else
  cat "$backup" > "$CADDYFILE"
  echo "New config did not validate; original Caddyfile restored." >&2
  exit 1
fi
