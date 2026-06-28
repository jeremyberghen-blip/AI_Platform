#!/usr/bin/env bash
set -euo pipefail

VOLUME_PATH="${VOLUME_PATH:-/workspace}"
INSTALL_DIR="${INSTALL_DIR:-${VOLUME_PATH}/ai_harness}"
REPO_URL="${REPO_URL:-https://github.com/jeremyberghen-blip/AI_Platform.git}"
BRANCH="${BRANCH:-main}"
HARNESS_API_KEY="${HARNESS_API_KEY:?HARNESS_API_KEY env var is required}"
HARNESS_PORT="${HARNESS_PORT:-8080}"
HARNESS_BACKEND_TYPE="${HARNESS_BACKEND_TYPE:-ollama}"

log() { echo "[entrypoint] $*"; }

# ── 1. Start Ollama ───────────────────────────────────────────────────────────
log "Starting Ollama..."
OLLAMA_MODELS_PATH="${VOLUME_PATH}/ollama_models"
mkdir -p "${OLLAMA_MODELS_PATH}"
export OLLAMA_MODELS="${OLLAMA_MODELS_PATH}"
ollama serve &

for i in $(seq 1 30); do
    if curl -sf "http://localhost:11434/api/tags" >/dev/null 2>&1; then
        log "Ollama ready"; break
    fi
    sleep 1
done

# ── 2. Install harness if not present ────────────────────────────────────────
if [ ! -f "${INSTALL_DIR}/.installed" ]; then
    log "No harness installation found — running install..."
    /opt/harness/install.sh "${INSTALL_DIR}" "${REPO_URL}" "${BRANCH}"
fi

# ── 3. Write runtime .env ────────────────────────────────────────────────────
cat > "${INSTALL_DIR}/harness_module/.env" <<EOF
HARNESS_API_KEY=${HARNESS_API_KEY}
HARNESS_BACKEND_TYPE=${HARNESS_BACKEND_TYPE}
HARNESS_OLLAMA_BASE_URL=http://localhost:11434
HARNESS_PORT=${HARNESS_PORT}
HARNESS_STORAGE_PATH=${VOLUME_PATH}/harness_storage
HARNESS_VOLUME_PATH=${VOLUME_PATH}
EOF
log ".env written"

# ── 4. Run setup from the git repo ───────────────────────────────────────────
# setup.sh lives in the repo so it can be updated without a Docker rebuild.
export VOLUME_PATH INSTALL_DIR HARNESS_PORT BRANCH
export PIP_CACHE_DIR="${VOLUME_PATH}/.pip_cache"
mkdir -p "${PIP_CACHE_DIR}"

SETUP_SCRIPT="${INSTALL_DIR}/docker/setup.sh"
if [ -f "${SETUP_SCRIPT}" ]; then
    log "Running setup.sh from repo..."
    bash "${SETUP_SCRIPT}" || log "WARNING: setup.sh reported errors — continuing"
else
    log "WARNING: setup.sh not found in repo — skipping infrastructure setup"
fi

# ── 5. Hand off to supervisor ─────────────────────────────────────────────────
log "Handing off to supervisor..."
export COMFYUI_DIR="${VOLUME_PATH}/comfyui"
export KOHYA_DIR="${VOLUME_PATH}/kohya_ss"
exec /opt/harness/supervisor.sh
