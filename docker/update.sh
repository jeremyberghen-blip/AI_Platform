#!/usr/bin/env bash
# Pull latest code and refresh Python deps.
# Supervisor handles the restart — this script just does the code update.
# Usage: update.sh <install_dir> [branch]
set -euo pipefail

INSTALL_DIR="${1:?install_dir required}"
BRANCH="${2:-main}"

log() { echo "[update] $*"; }

cd "${INSTALL_DIR}"

log "Fetching latest from origin/${BRANCH}..."
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"
log "Code updated"

log "Refreshing Python dependencies..."
source venv/bin/activate
pip install -r harness_module/requirements.txt --quiet
deactivate
log "Dependencies refreshed"

VERSION=$(date -u +"%Y%m%dT%H%M%SZ")
echo "${VERSION}" > "${INSTALL_DIR}/.installed"
log "Update complete — version: ${VERSION}"
