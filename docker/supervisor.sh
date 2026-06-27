#!/usr/bin/env bash
# Manages harness module and ComfyUI as a supervised process group.
# Runs in a loop so flag files can trigger update or restart without pod restart.
set -uo pipefail

VOLUME_PATH="${VOLUME_PATH:-/workspace}"
INSTALL_DIR="${INSTALL_DIR:-${VOLUME_PATH}/ai_harness}"
COMFYUI_DIR="${VOLUME_PATH}/comfyui"
KOHYA_DIR="${KOHYA_DIR:-${VOLUME_PATH}/kohya_ss}"
HARNESS_PORT="${HARNESS_PORT:-8080}"
BRANCH="${BRANCH:-main}"

FLAG_UPDATE="${VOLUME_PATH}/.do_update"
FLAG_RESTART="${VOLUME_PATH}/.do_restart"

MODULE_PID=""
COMFYUI_PID=""
KOHYA_PID=""

log() { echo "[supervisor] $*"; }

start_comfyui() {
    if [ ! -f "${COMFYUI_DIR}/.comfyui_installed" ]; then
        log "ComfyUI not installed — skipping"
        return
    fi
    log "Starting ComfyUI on port 8188..."
    cd "${COMFYUI_DIR}"
    python3 main.py --listen 0.0.0.0 --port 8188 --enable-cors-header "*" &
    COMFYUI_PID=$!
    log "ComfyUI PID=${COMFYUI_PID}"
}

start_kohya() {
    if [ ! -f "${KOHYA_DIR}/.kohya_installed" ]; then
        log "kohya_ss not installed — skipping"
        return
    fi
    log "Starting kohya_ss on port 8552..."
    cd "${KOHYA_DIR}"
    python3 gui.py --server_name 0.0.0.0 --server_port 8552 --headless &
    KOHYA_PID=$!
    log "kohya_ss PID=${KOHYA_PID}"
}

start_harness() {
    log "Starting harness module on port ${HARNESS_PORT}..."
    cd "${INSTALL_DIR}/harness_module"
    "${INSTALL_DIR}/venv/bin/uvicorn" main:app \
        --host 0.0.0.0 \
        --port "${HARNESS_PORT}" \
        --log-level info &
    MODULE_PID=$!
    log "Harness PID=${MODULE_PID}"
}

stop_all() {
    log "Stopping services..."
    [ -n "${MODULE_PID}" ]  && kill "${MODULE_PID}"  2>/dev/null || true
    [ -n "${COMFYUI_PID}" ] && kill "${COMFYUI_PID}" 2>/dev/null || true
    [ -n "${KOHYA_PID}" ]   && kill "${KOHYA_PID}"   2>/dev/null || true
    sleep 2
    MODULE_PID=""
    COMFYUI_PID=""
    KOHYA_PID=""
}

trap 'log "Supervisor received shutdown signal"; stop_all; exit 0' SIGTERM SIGINT

while true; do
    start_comfyui
    start_kohya
    start_harness

    log "Services running. Waiting for harness to exit..."
    wait "${MODULE_PID}" 2>/dev/null || true
    log "Harness module exited"

    # Stop ComfyUI and kohya alongside the harness
    [ -n "${COMFYUI_PID}" ] && kill "${COMFYUI_PID}" 2>/dev/null || true
    [ -n "${KOHYA_PID}" ]   && kill "${KOHYA_PID}"   2>/dev/null || true
    sleep 1
    COMFYUI_PID=""
    KOHYA_PID=""

    if [ -f "${FLAG_UPDATE}" ]; then
        log "Update flag detected — pulling latest code..."
        rm -f "${FLAG_UPDATE}"
        /opt/harness/update.sh "${INSTALL_DIR}" "${BRANCH}" \
            && log "Update complete" \
            || log "WARNING: update failed — restarting on current version"

    elif [ -f "${FLAG_RESTART}" ]; then
        log "Restart flag detected — restarting services..."
        rm -f "${FLAG_RESTART}"

    else
        log "Unexpected exit — restarting in 5s..."
        sleep 5
    fi
done
