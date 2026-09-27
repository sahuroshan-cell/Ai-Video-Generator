---
title: LTX-2 Video Demo
emoji: 🎬
colorFrom: indigo
colorTo: green
sdk: static
app_file: index.html
short_description: LTX-2 text/image-to-video demo (embeds Lightricks' Space)
models:
  - Lightricks/LTX-2
  - Lightricks/LTX-2.5
---

# LTX-2 Video Demo

This Space does not run LTX-2 itself. [Lightricks/LTX-2](https://github.com/Lightricks/LTX-2)
is a 22B-parameter audio-video diffusion model whose recommended weights
(LTX-2.5) run to ~66 GiB and need a real GPU (per the model card: 4x B200 /
8x H100 class hardware for the frontier text model family this repo ships,
or at minimum a dedicated 24GB+ CUDA GPU for the distilled pipeline) — well
beyond a free-tier Space's ZeroGPU allowance or this account's current
Space-hosting quota (see note below).

Rather than fake a demo or proxy calls through someone else's compute quota,
this Space embeds Lightricks' own official, already-running Space,
[`Lightricks/LTX-2-3`](https://huggingface.co/spaces/Lightricks/LTX-2-3)
(472 likes at time of writing), so it's the real thing on the model
author's own GPU:

- Full LTX-2.3 Distilled pipeline: text/image-to-video with synchronized audio.
- Runs entirely on Lightricks' hosted hardware; generations are billed to
  their Space's quota, not this one.

## Why not host it here

- This account can't create a Gradio/ZeroGPU Space yet (needs a PRO plan, a
  30-day-old verified account, or a community grant — see
  [Spaces ZeroGPU docs](https://huggingface.co/docs/hub/spaces-zerogpu)).
- Even with ZeroGPU, LTX-2.5's own weights alone (42 GB transformer + 26 GB
  text encoder, bf16) exceed ZeroGPU's 96 GB VRAM ceiling once you add VAEs
  and activations — this needs dedicated GPU hosting, not a shared allocator.
- LTX-2.5 has no [Inference Providers](https://huggingface.co/docs/inference-providers)
  mapping, so there's no hosted API to build a lightweight client-side proxy
  against (unlike, say, a chat LLM). The base `Lightricks/LTX-2` model *is*
  on Inference Providers (`fal-ai`, `wavespeed`) — a thin proxy Space against
  that model specifically is possible as a follow-up if wanted.
