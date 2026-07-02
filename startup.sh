#!/bin/bash
set -euo pipefail

WORKSPACE=/workspace
COMFYUI=/opt/comfyui
HARNESS=/opt/harness

echo "=== AI Harness Bootstrap ==="

# ── Network volume dirs ───────────────────────────────────────────────────────
mkdir -p \
    "$WORKSPACE/comfyui/models/checkpoints" \
    "$WORKSPACE/comfyui/models/loras" \
    "$WORKSPACE/comfyui/models/controlnet" \
    "$WORKSPACE/comfyui/models/vae" \
    "$WORKSPACE/comfyui/models/upscale_models" \
    "$WORKSPACE/comfyui/output" \
    "$WORKSPACE/comfyui/workflows" \
    "$WORKSPACE/hf_cache" \
    "$WORKSPACE/harness/storage"

# ── Symlinks: ComfyUI dirs → network volume ───────────────────────────────────
rm -rf "$COMFYUI/models"
ln -sf "$WORKSPACE/comfyui/models" "$COMFYUI/models"

rm -rf "$COMFYUI/output"
ln -sf "$WORKSPACE/comfyui/output" "$COMFYUI/output"

# Workflows — synced from local via sync_to_runpod.py, persisted on network volume
mkdir -p "$COMFYUI/user/default"
rm -rf "$COMFYUI/user/default/workflows"
ln -sf "$WORKSPACE/comfyui/workflows" "$COMFYUI/user/default/workflows"

# HuggingFace cache → network volume (persists TRELLIS2 and other HF models across pod restarts)
export HF_HOME="$WORKSPACE/hf_cache"

# ── Model download helper ─────────────────────────────────────────────────────
download_models_from_file() {
    local manifest="$1"
    [ -f "$manifest" ] || return 0

    while IFS='|' read -r type filename url; do
        type=$(echo "$type" | xargs)
        [[ "$type" =~ ^#.*$ || -z "$type" ]] && continue

        filename=$(echo "$filename" | xargs)
        url=$(echo "$url" | xargs)

        case "$type" in
            checkpoint) dest="$WORKSPACE/comfyui/models/checkpoints/$filename" ;;
            lora)       dest="$WORKSPACE/comfyui/models/loras/$filename" ;;
            controlnet) dest="$WORKSPACE/comfyui/models/controlnet/$filename" ;;
            vae)        dest="$WORKSPACE/comfyui/models/vae/$filename" ;;
            upscale)    dest="$WORKSPACE/comfyui/models/upscale_models/$filename" ;;
            *) echo "  Unknown type '$type', skipping $filename"; continue ;;
        esac

        if [ ! -f "$dest" ]; then
            echo "  Downloading $filename..."
            # Append token — handle URLs with and without existing query params
            if [[ "$url" == *"?"* ]]; then
                full_url="${url}&token=${CIVITAI_API_TOKEN}"
            else
                full_url="${url}?token=${CIVITAI_API_TOKEN}"
            fi
            wget -q --show-progress -O "$dest" "$full_url" \
                || { echo "  FAILED: $filename"; rm -f "$dest"; }
        else
            echo "  OK: $filename"
        fi
    done < "$manifest"
}

# ── Model downloads ───────────────────────────────────────────────────────────
if [ -z "${CIVITAI_API_TOKEN:-}" ]; then
    echo "WARNING: CIVITAI_API_TOKEN not set — skipping model downloads"
else
    echo "Checking models (baked-in manifest)..."
    download_models_from_file "/models.txt"

    # Also read any models Sable has added at runtime (persists on network volume)
    if [ -f "$WORKSPACE/models_additions.txt" ]; then
        echo "Checking models (runtime additions)..."
        download_models_from_file "$WORKSPACE/models_additions.txt"
    fi
fi

# ── Start ComfyUI ─────────────────────────────────────────────────────────────
echo "Starting ComfyUI..."
cd "$COMFYUI"
python main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --enable-cors-header \
    --enable-manager \
    &
COMFYUI_PID=$!

echo "Waiting for ComfyUI..."
ELAPSED=0
until curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge 120 ]; then
        echo "ComfyUI did not respond after 120s — continuing anyway"
        break
    fi
done
echo "ComfyUI ready (PID $COMFYUI_PID)"

# ── Start Harness Module ──────────────────────────────────────────────────────
echo "Starting Harness Module..."
cd "$HARNESS"
export HARNESS_STORAGE_PATH="$WORKSPACE/harness/storage"
export HARNESS_MODELS_FILE="$WORKSPACE/models_additions.txt"
exec python main.py
