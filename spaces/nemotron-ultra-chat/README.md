---
title: Nemotron 3 Ultra Chat
emoji: 🟩
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
short_description: Chat with NVIDIA Nemotron 3 Ultra 550B-A55B NVFP4
hf_oauth: true
hf_oauth_scopes:
  - inference-api
models:
  - nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4
---

# Nemotron 3 Ultra Chat

Client-side chat demo for [nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4).

The model (550B total / 55B active, min 4x B200 or 8x H100) is served through
Hugging Face Inference Providers (`fireworks-ai`). This is a **Static Space**:
there is no backend. Your browser signs in with Hugging Face
(`@huggingface/hub`'s OAuth helper), and all chat requests go straight from
your browser to `router.huggingface.co`, billed to your own account.

- Sign in with Hugging Face to start chatting.
- Reasoning toggle maps to `chat_template_kwargs.enable_thinking`; the trace
  renders in a collapsible block, parsed from either `reasoning_content`
  deltas or an inline `<think>...</think>` block.
- Sampling defaults follow the model card: `temperature=1.0`, `top_p=0.95`.
- No server, no secrets, nothing stored beyond `sessionStorage` for the OAuth
  token HF's own SDK manages.
