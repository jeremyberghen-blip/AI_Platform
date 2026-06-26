#!/usr/bin/env bash
# First-time installation to the network volume.
# Usage: install.sh <install_dir> <repo_url> <branch>
set -euo pipefail

INSTALL_DIR="${1:?install_dir required}"
REPO_URL="${2:?repo_url required}"
BRANCH="${3:-main}"

log() { echo "[install] $*"; }

mkdir -p "${INSTALL_DIR}"

# ── Clone repo (keep .git so future updates can git pull) ─────────────────────
log "Cloning ${REPO_URL} @ ${BRANCH}..."
git clone --depth 1 --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
cd "${INSTALL_DIR}"

# ── Create venv and install Python deps ───────────────────────────────────────
log "Creating Python venv..."
python3 -m venv venv
source venv/bin/activate

log "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r harness_module/requirements.txt --quiet

deactivate

# ── Record installed version ──────────────────────────────────────────────────
VERSION=$(date -u +"%Y%m%dT%H%M%SZ")
echo "${VERSION}" > "${INSTALL_DIR}/.installed"
log "Installation complete. Version tag: ${VERSION}"
