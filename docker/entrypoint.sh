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

# Capture model list before OLLAMA_MODELS is repurposed as the storage path
OLLAMA_MODEL_LIST="${OLLAMA_MODELS:-llama3.2:3b}"

# SD models to download on first boot (space-separated filenames without extension)
SD_MODELS="${SD_MODELS:-v1-5-pruned-emaonly}"

COMFYUI_DIR="${VOLUME_PATH}/comfyui"
KOHYA_DIR="${VOLUME_PATH}/kohya_ss"
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
    log "Found existing harness installation at ${INSTALL_DIR}"
else
    log "No harness installation found — running install..."
    /opt/harness/install.sh "${INSTALL_DIR}" "${REPO_URL}" "${BRANCH}"
fi

# ── 3. Install or verify ComfyUI ─────────────────────────────────────────────
export PIP_CACHE_DIR="${VOLUME_PATH}/.pip_cache"
mkdir -p "${PIP_CACHE_DIR}"

if [ -f "${COMFYUI_DIR}/.comfyui_installed" ]; then
    log "Found existing ComfyUI installation at ${COMFYUI_DIR}"
else
    log "Installing ComfyUI — this will take a few minutes on first boot..."
    rm -rf "${COMFYUI_DIR}"
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "${COMFYUI_DIR}" \
        || { log "ERROR: ComfyUI clone failed"; exit 1; }
    mkdir -p "${COMFYUI_DIR}/models/checkpoints" \
              "${COMFYUI_DIR}/models/loras" \
              "${COMFYUI_DIR}/models/controlnet" \
              "${COMFYUI_DIR}/models/vae" \
              "${COMFYUI_DIR}/models/upscale_models" \
              "${COMFYUI_DIR}/output" \
              "${COMFYUI_DIR}/input"
    echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${COMFYUI_DIR}/.comfyui_installed"
    log "ComfyUI cloned"
fi

# Always verify pip deps — packages live on the container (ephemeral), not the
# volume, so they must be reinstalled on every new pod. Pip cache is on the
# volume so this is fast after the first install.
log "Verifying ComfyUI Python dependencies..."
pip install -r "${COMFYUI_DIR}/requirements.txt" --quiet \
    || log "WARNING: some ComfyUI requirements.txt deps failed"
pip install sqlalchemy alembic tqdm blake3 safetensors einops scipy \
    transformers torchsde av aiohttp pydantic accelerate omegaconf kornia spandrel --quiet \
    || log "WARNING: some extra ComfyUI deps failed"

# Install custom node dependencies
for req in "${COMFYUI_DIR}"/custom_nodes/*/requirements.txt; do
    [ -f "$req" ] && pip install -r "$req" --quiet || true
done
log "ComfyUI dependencies ready"

# ── 4. Install or verify kohya_ss ────────────────────────────────────────────
if [ -f "${KOHYA_DIR}/.kohya_installed" ]; then
    log "Found existing kohya_ss installation at ${KOHYA_DIR}"
elif [ -d "${KOHYA_DIR}" ] && [ "$(ls -A "${KOHYA_DIR}")" ]; then
    log "Found unregistered kohya_ss directory — stamping existing install"
    echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${KOHYA_DIR}/.kohya_installed"
else
    log "Installing kohya_ss — this will take a few minutes on first boot..."
    rm -rf "${KOHYA_DIR}"
    git clone --depth 1 https://github.com/bmaltais/kohya_ss "${KOHYA_DIR}" \
        || log "WARNING: kohya_ss clone failed — skipping"
    [ -d "${KOHYA_DIR}" ] && echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${KOHYA_DIR}/.kohya_installed"
    log "kohya_ss cloned"
fi

log "Verifying kohya_ss Python dependencies..."
pip install -r "${KOHYA_DIR}/requirements.txt" --quiet \
    || log "WARNING: some kohya_ss deps failed — kohya may not start"
pip install gradio toml easygui --quiet \
    || log "WARNING: some kohya extra deps failed"

# Patch out easygui's tkinter dependency — we run headless, dialogs are unused
COMMON_GUI="${KOHYA_DIR}/kohya_gui/common_gui.py"
if [ -f "${COMMON_GUI}" ] && grep -q "from easygui import" "${COMMON_GUI}"; then
    python3 -c "p='${COMMON_GUI}'; c=open(p).read(); c=c.replace('from easygui import msgbox, ynbox', 'def msgbox(*a,**kw): print(a)\ndef ynbox(*a,**kw): return True'); open(p,'w').write(c)"
    log "Patched kohya_ss easygui import"
fi
log "kohya_ss dependencies ready"

# ── 5. Pull Ollama models (skip if already present) ───────────────────────────
for MODEL in ${OLLAMA_MODEL_LIST}; do
    if ollama list 2>/dev/null | grep -q "^${MODEL}"; then
        log "Ollama model already present: ${MODEL}"
    else
        log "Pulling Ollama model: ${MODEL} (this may take a while on first boot)"
        ollama pull "${MODEL}" || log "WARNING: failed to pull ${MODEL}"
    fi
done

# ── 5. Download SD checkpoints (skip if already present) ─────────────────────
declare -A SD_MODEL_URLS=(
    ["v1-5-pruned-emaonly"]="https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
)

for MODEL_NAME in ${SD_MODELS}; do
    MODEL_FILE="${COMFYUI_DIR}/models/checkpoints/${MODEL_NAME}.safetensors"
    if [ -f "${MODEL_FILE}" ]; then
        log "SD model already present: ${MODEL_NAME}"
    elif [ -n "${SD_MODEL_URLS[${MODEL_NAME}]+_}" ]; then
        log "Downloading SD model: ${MODEL_NAME}..."
        wget -q --show-progress -O "${MODEL_FILE}" "${SD_MODEL_URLS[${MODEL_NAME}]}" \
            || log "WARNING: failed to download ${MODEL_NAME}"
    else
        log "WARNING: unknown SD model '${MODEL_NAME}' — skipping"
    fi
done

# ── 6. Write runtime .env for the harness module ─────────────────────────────
ENV_FILE="${INSTALL_DIR}/harness_module/.env"
cat > "${ENV_FILE}" <<EOF
HARNESS_API_KEY=${HARNESS_API_KEY}
HARNESS_BACKEND_TYPE=${HARNESS_BACKEND_TYPE}
HARNESS_OLLAMA_BASE_URL=${OLLAMA_HOST}
HARNESS_PORT=${HARNESS_PORT}
HARNESS_STORAGE_PATH=${VOLUME_PATH}/harness_storage
HARNESS_VOLUME_PATH=${VOLUME_PATH}
EOF
log "Runtime .env written"

# ── 7. Hand off to supervisor (manages harness + ComfyUI in a restart loop) ──
log "Handing off to supervisor..."
export VOLUME_PATH INSTALL_DIR COMFYUI_DIR KOHYA_DIR HARNESS_PORT BRANCH
exec /opt/harness/supervisor.sh
