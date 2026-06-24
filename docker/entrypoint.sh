#!/usr/bin/env bash
set -euo pipefail

# ── Config from environment (set these in the RunPod template) ────────────────
VOLUME_PATH="${VOLUME_PATH:-/workspace}"
INSTALL_DIR="${INSTALL_DIR:-${VOLUME_PATH}/ai_harness}"
REPO_URL="${REPO_URL:-https://github.com/jeremyberghen-blip/AI_Platform.git}"
BRANCH="${BRANCH:-main}"
HARNESS_API_KEY="${HARNESS_API_KEY:?HARNESS_API_KEY env var is required}"
HARNESS_PORT="${HARNESS_PORT:-8080}"
HARNESS_BACKEND_TYPE="${HARNESS_BACKEND_TYPE:-ollama}"
# Which model to pull on first boot (space-separated for multiple)
OLLAMA_MODELS="${OLLAMA_MODELS:-llama3.2:3b}"
OLLAMA_HOST="http://localhost:11434"

log() { echo "[entrypoint] $*"; }

# ── 1. Start Ollama in the background ────────────────────────────────────────
log "Starting Ollama..."
OLLAMA_MODELS_PATH="${VOLUME_PATH}/ollama_models"
mkdir -p "${OLLAMA_MODELS_PATH}"
export OLLAMA_MODELS="${OLLAMA_MODELS_PATH}"
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
for i in $(seq 1 30); do
    if curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
        log "Ollama ready"
        break
    fi
    sleep 1
done

# ── 2. Install or verify the harness module ───────────────────────────────────
if [ -f "${INSTALL_DIR}/.installed" ]; then
    log "Found existing installation at ${INSTALL_DIR}"
    INSTALLED_VERSION=$(cat "${INSTALL_DIR}/.installed" 2>/dev/null || echo "unknown")
    log "Installed version: ${INSTALLED_VERSION}"
else
    log "No installation found — running install..."
    /opt/harness/install.sh "${INSTALL_DIR}" "${REPO_URL}" "${BRANCH}"
fi

# ── 3. Pull requested models (skip if already present) ───────────────────────
for MODEL in ${OLLAMA_MODELS}; do
    if ollama list 2>/dev/null | grep -q "^${MODEL}"; then
        log "Model already present: ${MODEL}"
    else
        log "Pulling model: ${MODEL} (this may take a while on first boot)"
        ollama pull "${MODEL}" || log "WARNING: failed to pull ${MODEL}"
    fi
done

# ── 4. Write runtime .env for the harness module ─────────────────────────────
ENV_FILE="${INSTALL_DIR}/harness_module/.env"
cat > "${ENV_FILE}" <<EOF
HARNESS_API_KEY=${HARNESS_API_KEY}
HARNESS_BACKEND_TYPE=${HARNESS_BACKEND_TYPE}
HARNESS_OLLAMA_BASE_URL=${OLLAMA_HOST}
HARNESS_PORT=${HARNESS_PORT}
HARNESS_STORAGE_PATH=${VOLUME_PATH}/harness_storage
EOF
log "Runtime .env written"

# ── 5. Start harness module ───────────────────────────────────────────────────
VENV="${INSTALL_DIR}/venv"
log "Starting harness module on port ${HARNESS_PORT}..."
cd "${INSTALL_DIR}/harness_module"
"${VENV}/bin/uvicorn" main:app \
    --host 0.0.0.0 \
    --port "${HARNESS_PORT}" \
    --log-level info &
MODULE_PID=$!

log "All services running. Ollama PID=${OLLAMA_PID}, Module PID=${MODULE_PID}"

# Keep container alive and propagate signals
trap 'log "Shutting down..."; kill ${MODULE_PID} ${OLLAMA_PID} 2>/dev/null; exit 0' SIGTERM SIGINT
wait ${MODULE_PID}
