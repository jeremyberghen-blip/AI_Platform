#!/usr/bin/env bash
# Pull latest code, refresh deps, run setup.
# Supervisor handles the restart — this script just does the update work.
# Usage: update.sh <install_dir> [branch]
set -uo pipefail

INSTALL_DIR="${1:?install_dir required}"
BRANCH="${2:-main}"
VOLUME_PATH="${VOLUME_PATH:-/workspace}"

log() { echo "[update] $*"; }

cd "${INSTALL_DIR}"

log "Pulling latest from origin/${BRANCH}..."
git fetch origin
git reset --hard "origin/${BRANCH}"
log "Code updated"

log "Refreshing harness Python dependencies..."
source venv/bin/activate
pip install -r harness_module/requirements.txt --quiet || log "WARNING: some harness deps failed"
deactivate

# Run setup from the freshly-pulled repo — handles ComfyUI, kohya, models, patches
export VOLUME_PATH INSTALL_DIR BRANCH
export PIP_CACHE_DIR="${VOLUME_PATH}/.pip_cache"

SETUP_SCRIPT="${INSTALL_DIR}/docker/setup.sh"
if [ -f "${SETUP_SCRIPT}" ]; then
    log "Running setup.sh..."
    bash "${SETUP_SCRIPT}" || log "WARNING: setup.sh reported errors"
else
    log "WARNING: setup.sh not found — skipping"
fi

VERSION=$(date -u +"%Y%m%dT%H%M%SZ")
echo "${VERSION}" > "${INSTALL_DIR}/.installed"
log "Update complete — version: ${VERSION}"
