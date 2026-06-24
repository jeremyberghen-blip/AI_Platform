#!/usr/bin/env bash
# Pull latest code from GitHub and restart the harness module in-place.
# Called by POST /v1/system/update inside the running container.
# Usage: update.sh <install_dir> <branch> <module_pid_file>
set -euo pipefail

INSTALL_DIR="${1:?install_dir required}"
BRANCH="${2:-main}"
PID_FILE="${3:-/tmp/harness_module.pid}"

log() { echo "[update] $*"; }

cd "${INSTALL_DIR}"

# ── Pull latest ───────────────────────────────────────────────────────────────
log "Fetching latest from origin/${BRANCH}..."
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"
log "Code updated"

# ── Re-install Python deps in case requirements changed ───────────────────────
source venv/bin/activate
pip install -r harness_module/requirements.txt --quiet
deactivate
log "Dependencies refreshed"

# ── Stamp new version ─────────────────────────────────────────────────────────
VERSION=$(date -u +"%Y%m%dT%H%M%SZ")
echo "${VERSION}" > "${INSTALL_DIR}/.installed"
log "Version tag: ${VERSION}"

# ── Signal harness module to restart ─────────────────────────────────────────
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    log "Sending SIGTERM to module PID ${OLD_PID}..."
    kill "${OLD_PID}" 2>/dev/null || true
else
    log "No PID file found — module will be restarted by entrypoint on next pod boot"
fi

log "Update complete"
