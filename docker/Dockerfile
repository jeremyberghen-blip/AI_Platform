# AI Harness — RunPod template image
# Thin image: runtime deps only. The actual app lives on the network volume.
# RunPod PyTorch base — Python 3.11, CUDA 12.4, PyTorch 2.4 pre-installed
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git ca-certificates \
    lsof procps zstd \
    && rm -rf /var/lib/apt/lists/*

# ── Ollama ───────────────────────────────────────────────────────────────────
RUN curl -fsSL https://ollama.com/install.sh | sh

# ── Bootstrap scripts (baked into image, app code lives on volume) ───────────
COPY entrypoint.sh install.sh update.sh supervisor.sh /opt/harness/
RUN chmod +x /opt/harness/*.sh

# ── Ports ────────────────────────────────────────────────────────────────────
# 8080  = harness module API
# 8188  = ComfyUI
# 8552  = kohya_ss
# 11434 = Ollama
EXPOSE 8080 8188 8552 11434

ENTRYPOINT ["/opt/harness/entrypoint.sh"]
