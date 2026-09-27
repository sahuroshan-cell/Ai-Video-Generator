---
title: Nemotron 3 Ultra Chat
emoji: 🟩
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 6.28.0
app_file: app.py
python_version: "3.12"
short_description: Chat with NVIDIA Nemotron 3 Ultra 550B-A55B NVFP4
hf_oauth: true
hf_oauth_scopes:
  - inference-api
models:
  - nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4
---

# Nemotron 3 Ultra Chat

Streaming chat demo for [nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4).

The model (550B total / 55B active, min 4x B200 or 8x H100) is served through
Hugging Face Inference Providers (`fireworks-ai`), not hosted in this Space.

- Sign in with Hugging Face: inference is billed to your account.
- Not signed in: falls back to the Space's `HF_TOKEN` secret, if the owner set one.
- Reasoning toggle maps to `chat_template_kwargs.enable_thinking`; the trace is shown in a collapsible block.
- Sampling defaults follow the model card: `temperature=1.0`, `top_p=0.95`.
