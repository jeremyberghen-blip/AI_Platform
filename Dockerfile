FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# ── Python 3.12 (wheels/Linux/Torch270 are cp312-only) ────────────────────────
# RunPod base already includes deadsnakes PPA — just install directly.
# python3.12-distutils does not exist (distutils removed in 3.12; setuptools replaces it).
RUN apt-get update && \
    apt-get install -y \
        python3.12 python3.12-venv python3.12-dev \
        curl gnupg2 libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Make 3.12 the default python / python3 / pip
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2 && \
    update-alternatives --install /usr/bin/python  python  /usr/bin/python3.12 2 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 && \
    pip install --upgrade pip

# ── PyTorch 2.7.0 + CUDA 12.8 (PyTorch bundles its own CUDA 12.8 runtime) ────
RUN pip install --no-cache-dir \
    torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu128

# ── ComfyUI ────────────────────────────────────────────────────────────────────
WORKDIR /opt/comfyui
RUN git clone https://github.com/comfyanonymous/ComfyUI.git . && \
    pip install --no-cache-dir -r requirements.txt

# ── Custom Nodes ───────────────────────────────────────────────────────────────

# ComfyUI Manager
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git custom_nodes/ComfyUI-Manager && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-Manager/requirements.txt

# cg-use-everywhere
RUN git clone https://github.com/chrisgoringe/cg-use-everywhere.git custom_nodes/cg-use-everywhere

# visualbruno ComfyUI-Trellis2 — Linux/Torch270 cp312 wheels + requirements
# NOTE: nvdiffrec_render has no Linux/Torch270 build. The Rasterize PBR node will
#       be unavailable; use Shape to Textured Mesh -> Save Mesh for GLB export.
RUN git clone https://github.com/visualbruno/ComfyUI-Trellis2.git custom_nodes/ComfyUI-Trellis2-visualbruno

RUN pip install --no-cache-dir --no-deps \
    custom_nodes/ComfyUI-Trellis2-visualbruno/wheels/Linux/Torch270/cumesh-1.0-cp312-cp312-linux_x86_64.whl \
    custom_nodes/ComfyUI-Trellis2-visualbruno/wheels/Linux/Torch270/nvdiffrast-0.4.0-cp312-cp312-linux_x86_64.whl \
    custom_nodes/ComfyUI-Trellis2-visualbruno/wheels/Linux/Torch270/flex_gemm-0.0.1-cp312-cp312-linux_x86_64.whl \
    custom_nodes/ComfyUI-Trellis2-visualbruno/wheels/Linux/Torch270/o_voxel-0.0.1-cp312-cp312-linux_x86_64.whl \
    custom_nodes/ComfyUI-Trellis2-visualbruno/wheels/Linux/Torch270/custom_rasterizer-0.1-cp312-cp312-linux_x86_64.whl

# blinker 1.4 is distutils-installed in the base image; pip can't uninstall it cleanly.
# Force-overwrite it before running requirements.txt so flask/dash/open3d resolve cleanly.
RUN pip install --no-cache-dir --ignore-installed blinker
RUN pip install --no-cache-dir -r custom_nodes/ComfyUI-Trellis2-visualbruno/requirements.txt

# PozzettiAndrea ComfyUI-TRELLIS2
RUN git clone https://github.com/PozzettiAndrea/ComfyUI-TRELLIS2.git custom_nodes/ComfyUI-TRELLIS2 && \
    pip install --no-cache-dir -r custom_nodes/ComfyUI-TRELLIS2/requirements.txt && \
    python custom_nodes/ComfyUI-TRELLIS2/install.py || true

# ComfyUI GeometryPack (provides Save Mesh node for GLB export)
RUN git clone https://github.com/PozzettiAndrea/ComfyUI-GeometryPack.git custom_nodes/ComfyUI-GeometryPack

# TRELLIS2 HiCache — speed accelerator for visualbruno's TRELLIS2
RUN git clone https://github.com/Archerkattri/ComfyUI-TRELLIS2-HiCache.git custom_nodes/comfyui-trellis2-hicache && \
    pip install --no-cache-dir hicache-pp

# ComfyUI Impact Pack
RUN git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git custom_nodes/comfyui-impact-pack && \
    pip install --no-cache-dir -r custom_nodes/comfyui-impact-pack/requirements.txt

# comfy-image-saver
RUN git clone https://github.com/giriss/comfy-image-saver.git custom_nodes/comfy-image-saver && \
    pip install --no-cache-dir -r custom_nodes/comfy-image-saver/requirements.txt 2>/dev/null || true

# ComfyUI Custom Scripts (pythongosssss)
RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git custom_nodes/comfyui-custom-scripts

# rgthree-comfy
RUN git clone https://github.com/rgthree/rgthree-comfy.git custom_nodes/rgthree-comfy

# mikey_nodes
RUN git clone https://github.com/bash-j/mikey_nodes.git custom_nodes/mikey_nodes && \
    pip install --no-cache-dir -r custom_nodes/mikey_nodes/requirements.txt 2>/dev/null || true

# Ultimate SD Upscale
RUN git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git custom_nodes/comfyui_ultimatesdupscale

# ── ComfyUI Manager config ─────────────────────────────────────────────────────
RUN mkdir -p user/__manager
COPY docker/manager_config.ini user/__manager/config.ini

# ── Harness Module ─────────────────────────────────────────────────────────────
WORKDIR /opt/harness
COPY harness_module/ .
RUN pip install --no-cache-dir -r requirements.txt

# ── Bootstrap ──────────────────────────────────────────────────────────────────
COPY startup.sh /startup.sh
COPY models.txt /models.txt
RUN chmod +x /startup.sh

EXPOSE 8080 8188

CMD ["/startup.sh"]
