# AI Image & Video Generation Toolkit
### BIS Harness Module — Visual Generation Reference

This document describes the tools, models, workflows, and concepts available to the visual generation module of the BIS AI harness. It is intended as a briefing document for an AI assistant (Claude Code or similar) tasked with building, maintaining, or extending this module.

---

## Architecture Overview

The visual generation stack is built around **ComfyUI** as the inference backend, exposed via its REST/WebSocket API. The harness dispatches generation jobs to ComfyUI, which executes workflows defined as JSON node graphs. Training jobs are handled by **Kohya_ss** or **OneTrainer** separately.

All models, LoRAs, and supporting files live on a **persistent RunPod network volume**, mounted at each session. The GPU pod is spun up on demand and shut down after jobs complete.

---

## File System Layout

```
/models
  /checkpoints        # Base diffusion models
  /loras              # Trained LoRA adapters
  /controlnet         # ControlNet condition models
  /vae                # Standalone VAE decoders
  /clip               # CLIP and T5 text encoders
/training
  /datasets           # Raw image datasets for LoRA training
  /output             # Trained LoRA output files
/comfyui              # ComfyUI installation
/kohya_ss             # Kohya_ss training tool
/onetrainer           # OneTrainer (Flux-preferred trainer)
```

---

## Base Models

These are the foundation models generation runs on. LoRAs must be trained against the same base they will be used with.

| Model | Use Case | Source |
|---|---|---|
| **Flux.1 Dev** | Highest quality image generation, best prompt adherence | Hugging Face (black-forest-labs) |
| **Flux.1 Schnell** | Faster Flux variant, slightly lower quality | Hugging Face (black-forest-labs) |
| **SDXL Base 1.0** | Broad ecosystem, large LoRA library, reliable | Hugging Face (stabilityai) |
| **SD 1.5** | Maximum compatibility, fastest training, older quality ceiling | Hugging Face / CivitAI |
| **Wan 2.1 14B** | Best open-source video generation model | Hugging Face |
| **Wan 2.1 1.3B** | Lighter Wan variant for faster video on tighter VRAM | Hugging Face |

### Supporting Files for Flux

Flux requires these files separately from the checkpoint:

- `clip_l.safetensors` — CLIP text encoder
- `t5xxl_fp16.safetensors` (or `t5xxl_fp8` for VRAM-constrained runs)
- `ae.safetensors` — Flux VAE

---

## Inference Tools

### ComfyUI
**Repo:** github.com/comfyanonymous/ComfyUI

The primary inference backend. Node-based workflow editor with a REST API and WebSocket interface. The harness communicates with ComfyUI by:
1. POSTing a workflow JSON to `/prompt`
2. Listening on the WebSocket for completion events
3. Fetching the output image from `/view`

Install **ComfyUI Manager** immediately after ComfyUI. It handles custom node installation without manual file management.

### Essential ComfyUI Custom Nodes

| Node Package | Purpose |
|---|---|
| **ComfyUI-Advanced-ControlNet** | Improved ControlNet handling |
| **ComfyUI_IPAdapter_plus** | Image reference / IP-Adapter |
| **ComfyUI-AnimateDiff-Evolved** | Frame-consistent animation / video bridge |
| **rgthree-comfy** | Quality of life node improvements |
| **ComfyUI-WanVideoWrapper** | Wan 2.1 video generation support |

All installable via ComfyUI Manager.

---

## Training Tools

### Kohya_ss
**Repo:** github.com/bmaltais/kohya_ss

Standard LoRA training tool. Web UI wrapper over the underlying training scripts. Handles SD 1.5, SDXL, and Flux LoRA training. Use this for SD 1.5 and SDXL LoRAs.

### OneTrainer
**Repo:** github.com/Nerogar/OneTrainer

Cleaner modern interface, stronger Flux.1 support. Preferred trainer for Flux LoRAs.

### Captioning Tools

Training images require caption files (`.txt` sidecar per image) describing image content. This teaches the model to associate the trigger word with the subject rather than everything else in the frame.

- **Florence-2** — lightweight, fast, good quality captions. Preferred.
- **BLIP2** — alternative, slightly heavier
- Both are available via Hugging Face and can be run as a preprocessing step before training

---

## LoRA Training Reference

LoRAs are small fine-tuned adapters (50–150MB) that bias a base model toward a specific character, style, or concept without retraining the full model.

### Dataset Requirements

| Base Model | Recommended Image Count |
|---|---|
| SD 1.5 | 15–30 images |
| SDXL | 30–50 images |
| Flux | 20–40 images |

**Image guidelines:**
- Variety of angles, expressions, lighting, contexts
- Clean consistent depictions of the subject
- Single consistent art style per dataset produces cleaner results
- Resolution: 512×512 for SD 1.5, 1024×1024 for SDXL/Flux
- Each image needs a corresponding `.txt` caption file

### Key Training Parameters

- **Learning rate:** 1e-4 for SD 1.5, 5e-5 for SDXL, 1e-4 for Flux (starting points; tune from here)
- **Steps:** 1000–2000 for character LoRAs; save checkpoints every 250 steps and evaluate
- **Network rank (dim):** 32–64 for most use cases; higher = more capacity but larger file and more risk of overfitting
- **Trigger word:** a unique string associated with the character (e.g. `mycharname_v1`) included in all training captions

### Content Policy

The local training stack (Kohya_ss, OneTrainer, ComfyUI) has no content detection or filtering. Training image content is unrestricted when running locally or on RunPod pods. Cloud-based training services (Replicate, Astria) have ToS restrictions and should not be used for NSFW training data.

---

## ControlNet

ControlNet is a parallel network that enforces structural constraints (pose, depth, edges) on generation while allowing the base model to handle appearance. This is the primary mechanism for using Blender-derived pose references.

### How It Works

1. A **control image** (depth map, pose skeleton, edge map) is fed alongside the text prompt
2. ControlNet injects structural signals into the U-Net's attention layers
3. The model denoises toward the prompt while being constrained to the structure
4. A **weight** parameter (typically 0.7–1.2) controls enforcement strength

### ControlNet Types

| Type | Input | Best For |
|---|---|---|
| **Depth** | Grayscale depth/z-pass render | Overall 3D spatial relationships |
| **Normal Map** | Normal pass render | Surface form, more precise than depth |
| **OpenPose** | Pose skeleton image | Humanoid figure poses |
| **Canny** | Edge/line render | Hard structural outlines |
| **Lineart** | Clean line render | Following specific contours |

### Recommended Models

- **SDXL ControlNet:** depth, canny, openpose variants (available on Hugging Face / CivitAI)
- **Flux ControlNet:** XLabs-AI models on Hugging Face (ecosystem still maturing)

### Blender Workflow for ControlNet

The intended workflow for pose-guided generation:

1. Import or build a mannequin in Blender (Manny/Quinn from UE5 exported as FBX works well; Rigify metarig is an in-Blender alternative)
2. Scale/adjust proportions to match target character (head-body ratio, limb length, shoulder width are the impactful variables)
3. Pose the armature in Pose Mode
4. Enable Z pass in View Layer → Passes → Data
5. Render depth pass (EEVEE is sufficient; Cycles not needed for this purpose)
6. Export as 16-bit grayscale PNG
7. Feed into ComfyUI as ControlNet depth input alongside text prompt and LoRA

**Mannequin appearance does not matter.** ControlNet reads geometry and spatial relationships only. A grey default mesh with correct proportions in the right pose is all that is needed.

---

## IP-Adapter

IP-Adapter encodes reference image visual features directly into the attention layers alongside the text prompt, enabling style and appearance transfer without structural constraint.

- Accepts 1–2 reference images cleanly; more images dilute influence and introduce conflict
- Can be stacked with ControlNet (ControlNet handles structure, IP-Adapter handles appearance)
- **ComfyUI_IPAdapter_plus** is the node package to use

---

## VAE

The VAE (Variational Autoencoder) handles encoding/decoding between pixel space and the latent space where diffusion operates. Base models include a VAE but standalone VAEs can improve output quality:

- `sdxl-vae-fp16-fix` — fixes color saturation issues in SDXL
- `ae.safetensors` — Flux's dedicated VAE

---

## Prompt Engineering Reference

### Prompt Structure

**Subject → Style → Composition → Lighting → Technical**

Example: *"A weathered mercenary standing at a rain-slicked city overlook, digital painting, cinematic wide shot, dramatic rim lighting with neon bleed, highly detailed, concept art"*

### Term Reference

| Parameter | Terms |
|---|---|
| **Lighting** | golden hour, blue hour, chiaroscuro, rim lighting, volumetric light, bioluminescent, neon-lit, studio softbox, harsh midday sun, candlelight, overcast diffuse, god rays, backlighting, silhouette lighting |
| **Medium / Style** | oil painting, watercolor, ink illustration, digital painting, concept art, photorealistic, 3D render, cel-shaded, woodblock print, charcoal sketch, matte painting, linocut, gouache, pixel art |
| **Render Engine** | Octane render, Unreal Engine 5, Blender Cycles, V-Ray, Arnold, Redshift, ray-traced, subsurface scattering |
| **Composition** | wide shot, extreme close-up, dutch angle, bird's eye view, worm's eye view, rule of thirds, symmetrical, shallow depth of field, bokeh, tilt-shift, fisheye lens |
| **Mood** | liminal, melancholic, ethereal, oppressive, serene, foreboding, whimsical, stark, grandiose, intimate |
| **Artist / Aesthetic** | Simon Stålenhag, Syd Mead, Moebius, Craig Mullins, H.R. Giger, Alphonse Mucha, Studio Ghibli, ukiyo-e, brutalist, solarpunk, grimdark |
| **Technical Quality** | highly detailed, intricate, sharp focus, 8K, masterpiece, cinematic, RAW photo, film grain |
| **Color Palette** | muted earth tones, high contrast, monochromatic, desaturated, vibrant, neon, sepia, cool blues and grays |

### CFG Scale

Controls prompt adherence vs. creative freedom. Too low ignores the prompt; too high produces oversaturated artifacted results.
- **Typical range:** 7–12 (model-dependent)
- Flux uses a different guidance mechanism (distilled guidance) and has different optimal ranges

### Negative Prompts (SD/SDXL)

Common useful negatives: `blurry, low quality, deformed, extra limbs, bad anatomy, watermark, text, logo, oversaturated, jpeg artifacts`

---

## Generation Workflow

### Iteration Strategy

1. **Draft pass** — low steps (15–20), low resolution, 4–8 variants to find a direction
2. **Seed lock** — when a promising result appears, lock the seed to iterate on prompt without losing composition
3. **Refinement** — increase steps, adjust prompt, fix problem areas
4. **Upscale** — final resolution pass after composition is locked
5. **Inpainting** — fix specific regions (hands, faces) without regenerating the whole image

### ControlNet + LoRA Together

The correct mental model:
- **ControlNet** owns structure and pose (fed from Blender depth render)
- **LoRA** owns character identity and appearance
- **Base model** fills in detail, texture, and style
- **Text prompt** steers everything

These can all run simultaneously in a single ComfyUI workflow.

---

## Video Generation

Video is currently secondary to the still image pipeline but the infrastructure supports it via Wan 2.1.

### Key Differences from Image Generation

- **Temporal attention layers** maintain consistency across frames
- **AnimateDiff** adds motion consistency to image models
- First-frame + last-frame control is available in some tools (generates motion between endpoints)
- Character consistency across multiple distinct clips remains the hard unsolved problem in open-source video

### Video Workflow Notes

- Generate short clips (3–5 seconds); quality degrades over longer durations
- Use camera language in prompts: "slow dolly in," "static shot," "handheld," "aerial pan"
- Describe motion explicitly, not just scene content
- Clip-by-clip generation + editing is the current practical approach, not continuous timeline animation

### Character Consistency in Video

Options in order of robustness:
1. **LoRA active during generation** — most reliable, bakes identity into every frame
2. **IP-Adapter reference injection** — feeds portrait as locked appearance reference
3. **Seed + prompt locking** — cheap, partially works for same-setup shots
4. **First/last frame control** — Wan 2.1 supports this; guides motion between endpoints

---

## RunPod Integration Notes

### Recommended Pod Configuration

- **GPU:** RTX 4090 (24GB VRAM) for images and standard video
- **GPU:** A100 for large video jobs or batched training runs
- **Pricing:** ~$0.74/hr spot (4090); secure instances cost more but are uninterruptible
- **Storage:** Network volume for persistent model storage (~$0.07/GB/month); mount at each session

### Workflow

1. Keep all models and tool installations on the network volume
2. Spin up GPU pod, mount volume
3. Start ComfyUI server
4. Harness connects via ComfyUI API
5. Dispatch jobs, retrieve outputs
6. Shut down pod when done; volume persists

### RunPod API

RunPod exposes a REST API for programmatic pod management. The harness can use this to:
- Spin up a pod on demand when a generation job is queued
- Shut down the pod after job completion or timeout
- Route jobs to RunPod vs. local GPU based on job type or VRAM requirements

### Local GPU (RTX 3060 6GB)

Usable for SD 1.5 image generation during development and testing:
- SD 1.5 at 512×512: ~10–20 seconds per image
- SDXL: requires CPU offloading; slow but functional
- Flux: not recommended at this VRAM level
- Video: not viable locally

Enable xformers and `--lowvram` flags in ComfyUI for 6GB operation. System RAM (32GB recommended) acts as the offload buffer.

---

## External Resources

| Resource | URL | Purpose |
|---|---|---|
| CivitAI | civitai.com | Models, LoRAs, embeddings, community workflows |
| Hugging Face | huggingface.co | Base model downloads, research models |
| ComfyUI Repo | github.com/comfyanonymous/ComfyUI | Core inference tool |
| Kohya_ss Repo | github.com/bmaltais/kohya_ss | LoRA training |
| OneTrainer Repo | github.com/Nerogar/OneTrainer | LoRA training (Flux-preferred) |
| XLabs-AI | huggingface.co/XLabs-AI | Flux ControlNet models |
| r/StableDiffusion | reddit.com/r/StableDiffusion | Community, workflow discussion |

---

*Document generated for BIS harness visual generation module. Update as tooling evolves — this space moves fast.*
