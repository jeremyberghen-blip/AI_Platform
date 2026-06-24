# AI Harness — RunPod template image
# Thin image: runtime deps only. The actual app lives on the network volume.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    curl wget git ca-certificates \
    lsof procps \
    && rm -rf /var/lib/apt/lists/*

# python3 → python3.11
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
 && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# ── Ollama ───────────────────────────────────────────────────────────────────
RUN curl -fsSL https://ollama.com/install.sh | sh

# ── Bootstrap scripts (baked into image, app code lives on volume) ───────────
COPY entrypoint.sh install.sh update.sh /opt/harness/
RUN chmod +x /opt/harness/*.sh

# ── Ports ────────────────────────────────────────────────────────────────────
# 8080 = harness module API
# 11434 = Ollama
EXPOSE 8080 11434

ENTRYPOINT ["/opt/harness/entrypoint.sh"]
