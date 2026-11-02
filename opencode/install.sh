#!/usr/bin/env bash
# Install claude-seo into OpenCode 2.x.
#
# Installs skills, agents, the /seo command and an isolated Python runtime into
# ${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}.
#
# Usage:
#   bash opencode/install.sh                 # full install, with Chromium
#   bash opencode/install.sh --skip-browser  # core runtime, no Chromium
#   bash opencode/install.sh --no-setup      # files only; run setup later
#   bash opencode/install.sh --no-extensions # core skills/agents only
#   bash opencode/install.sh --dest DIR      # custom OpenCode config dir
#   bash opencode/install.sh --dry-run       # show the plan, change nothing

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
DEST="${OPENCODE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode}"
SKIP_BROWSER=0
NO_SETUP=0
DRY_RUN=0
PORT_ARGS=()

usage() {
  sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
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
    --skip-browser)
      SKIP_BROWSER=1
      shift
      ;;
    --no-setup)
      NO_SETUP=1
      shift
      ;;
    --no-extensions)
      PORT_ARGS+=(--no-extensions)
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      PORT_ARGS+=(--dry-run)
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

command -v python3 >/dev/null 2>&1 || {
  echo "error: Python 3.11 to 3.14 is required (python3 not found)." >&2
  exit 1
}
python3 - <<'PY' || exit 1
import sys
if sys.version_info < (3, 11):
    raise SystemExit(
        "error: Python 3.11 or newer is required (found %d.%d)."
        % sys.version_info[:2]
    )
if sys.version_info >= (3, 15):
    print(
        "warning: Python 3.15 is not supported yet; use 3.11 to 3.14.",
        file=sys.stderr,
    )
PY

echo "Installing claude-seo into OpenCode..."
python3 "${SCRIPT_DIR}/port.py" --dest "${DEST}" ${PORT_ARGS[@]+"${PORT_ARGS[@]}"}

if [ "${DRY_RUN}" = 1 ]; then
  echo
  echo "Dry run only. Nothing was written."
  exit 0
fi

LAUNCHER="${DEST}/skills/seo/scripts/claude-seo"
if [ "${NO_SETUP}" = 1 ]; then
  echo
  echo "Skipped Python runtime setup."
  echo "Run later: \"${LAUNCHER}\" setup"
  exit 0
fi

if [ ! -x "${LAUNCHER}" ]; then
  echo "error: runtime launcher not found at ${LAUNCHER}" >&2
  exit 1
fi

echo
echo "Building the isolated Python runtime..."
SETUP_ARGS=()
if [ "${SKIP_BROWSER}" = 1 ]; then
  SETUP_ARGS+=(--skip-browser)
fi
"${LAUNCHER}" setup ${SETUP_ARGS[@]+"${SETUP_ARGS[@]}"}

echo
echo "claude-seo is installed for OpenCode."
echo "  config:  ${DEST}"
echo "  command: /seo audit https://example.com"
echo "  check:   \"${LAUNCHER}\" doctor --json"
echo
echo "Reload OpenCode (or run /reload) if the new skills do not appear."
