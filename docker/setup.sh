#!/usr/bin/env bash
# Infrastructure setup — runs on every boot and every update.
# Lives in the git repo so it updates without a Docker rebuild.
# Called by: entrypoint.sh (first boot), update.sh (on Update Pod)
set -uo pipefail

VOLUME_PATH="${VOLUME_PATH:-/workspace}"
INSTALL_DIR="${INSTALL_DIR:-${VOLUME_PATH}/ai_harness}"
COMFYUI_DIR="${VOLUME_PATH}/comfyui"
KOHYA_DIR="${VOLUME_PATH}/kohya_ss"
log() { echo "[setup] $*"; }

# ── ComfyUI ───────────────────────────────────────────────────────────────────
if [ -f "${COMFYUI_DIR}/.comfyui_installed" ]; then
    log "ComfyUI already installed"
else
    log "Installing ComfyUI..."
    rm -rf "${COMFYUI_DIR}"
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "${COMFYUI_DIR}" \
        || { log "ERROR: ComfyUI clone failed"; }
    if [ -d "${COMFYUI_DIR}" ]; then
        mkdir -p \
            "${COMFYUI_DIR}/models/checkpoints" \
            "${COMFYUI_DIR}/models/loras" \
            "${COMFYUI_DIR}/models/controlnet" \
            "${COMFYUI_DIR}/models/vae" \
            "${COMFYUI_DIR}/models/upscale_models" \
            "${COMFYUI_DIR}/output" \
            "${COMFYUI_DIR}/input"
        echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${COMFYUI_DIR}/.comfyui_installed"
        log "ComfyUI cloned"
    fi
fi

log "Verifying ComfyUI Python dependencies..."
pip install -r "${COMFYUI_DIR}/requirements.txt" --quiet \
    || log "WARNING: some ComfyUI requirements failed"
pip install sqlalchemy alembic tqdm blake3 safetensors einops scipy \
    transformers torchsde av aiohttp pydantic accelerate omegaconf kornia spandrel --quiet \
    || log "WARNING: some extra ComfyUI deps failed"
for req in "${COMFYUI_DIR}"/custom_nodes/*/requirements.txt; do
    [ -f "$req" ] && pip install -r "$req" --quiet || true
done
log "ComfyUI dependencies ready"

# ── kohya_ss ──────────────────────────────────────────────────────────────────
if [ -f "${KOHYA_DIR}/.kohya_installed" ]; then
    log "kohya_ss already installed"
elif [ -d "${KOHYA_DIR}" ] && [ "$(ls -A "${KOHYA_DIR}")" ]; then
    log "Found unregistered kohya_ss directory — stamping existing install"
    echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${KOHYA_DIR}/.kohya_installed"
else
    log "Installing kohya_ss..."
    rm -rf "${KOHYA_DIR}"
    git clone --depth 1 https://github.com/bmaltais/kohya_ss "${KOHYA_DIR}" \
        || log "WARNING: kohya_ss clone failed — skipping"
    [ -d "${KOHYA_DIR}" ] \
        && echo "$(date -u +"%Y%m%dT%H%M%SZ")" > "${KOHYA_DIR}/.kohya_installed"
    log "kohya_ss cloned"
fi

log "Verifying kohya_ss Python dependencies..."
pip install -r "${KOHYA_DIR}/requirements.txt" --quiet \
    || log "WARNING: some kohya deps failed"
pip install gradio toml easygui --quiet \
    || log "WARNING: some kohya extra deps failed"

# Patch out easygui's tkinter dependency — headless server has no display
COMMON_GUI="${KOHYA_DIR}/kohya_gui/common_gui.py"
if [ -f "${COMMON_GUI}" ] && grep -q "from easygui import" "${COMMON_GUI}"; then
    python3 -c "p='${COMMON_GUI}'; c=open(p).read(); c=c.replace('from easygui import msgbox, ynbox', 'def msgbox(*a,**kw): print(a)\ndef ynbox(*a,**kw): return True'); open(p,'w').write(c)"
    log "Patched kohya_ss easygui import"
fi
log "kohya_ss dependencies ready"

log "Setup complete"
