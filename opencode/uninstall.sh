#!/usr/bin/env bash
# Remove the claude-seo OpenCode port from an OpenCode configuration.
#
# Only removes entries owned by this port: skills/seo, skills/seo-*,
# agents/seo-*.md and commands/seo.md. Other skills and agents are untouched.
#
# Usage:
#   bash opencode/uninstall.sh          # asks for confirmation
#   bash opencode/uninstall.sh --yes    # no prompt
#   bash opencode/uninstall.sh --dest DIR

set -euo pipefail

DEST="${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}"
YES=0

usage() {
  sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)
      [ $# -ge 2 ] || { echo "error: --dest needs a directory" >&2; exit 2; }
      DEST="$2"
      shift 2
      ;;
    --dest=*)
      DEST="${1#*=}"
      shift
      ;;
    --yes|-y)
      YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "${YES}" = 0 ]; then
  printf 'Remove claude-seo skills, agents and the /seo command from %s? [y/N] ' "${DEST}"
  read -r answer || true
  case "${answer:-}" in
    y|Y|yes|YES) ;;
    *) echo "Aborted. Nothing removed."; exit 1 ;;
  esac
fi

shopt -s nullglob
removed=0

for entry in "${DEST}"/skills/seo "${DEST}"/skills/seo-*; do
  if [ -e "${entry}" ]; then
    rm -rf -- "${entry}"
    removed=$((removed + 1))
  fi
done

for entry in "${DEST}"/agents/seo-*.md "${DEST}"/commands/seo.md; do
  if [ -e "${entry}" ]; then
    rm -f -- "${entry}"
    removed=$((removed + 1))
  fi
done

echo "Removed ${removed} claude-seo entries from ${DEST}."
