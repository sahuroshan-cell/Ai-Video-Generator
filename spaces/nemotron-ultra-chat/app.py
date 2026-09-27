import os

import gradio as gr
import spaces
from huggingface_hub import InferenceClient

MODEL_ID = "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4"
PROVIDER = os.environ.get("INFERENCE_PROVIDER", "fireworks-ai")
FALLBACK_TOKEN = os.environ.get("HF_TOKEN")

EXAMPLES = [
    "What is 84 * 3 / 2?",
    "Explain quantum computing in simple terms.",
    "Write a Python function that returns the n-th prime, then analyse its complexity.",
    "Tell me an interesting fact about the universe!",
]


@spaces.GPU(duration=1)
def _noop():
    """ZeroGPU requires one decorated function; never called. All inference is remote."""


def _split_think(text: str) -> tuple[str, str]:
    """Split inline <think>...</think> reasoning from the answer, tolerating an unclosed tag."""
    if "<think>" not in text and "</think>" not in text:
        return "", text
    head, sep, tail = text.partition("</think>")
    reasoning = head.replace("<think>", "").strip()
    return (reasoning, tail.lstrip()) if sep else (reasoning, "")


def _render(reasoning: str, answer: str, thinking_done: bool) -> str:
    if not reasoning:
        return answer
    label = "Reasoning" if thinking_done else "Reasoning..."
    body = reasoning.replace("\n", "\n> ")
    return f"<details{'' if thinking_done else ' open'}><summary>{label}</summary>\n\n> {body}\n\n</details>\n\n{answer}"


def respond(
    message: str,
    history: list[dict],
    system_prompt: str = "",
    enable_thinking: bool = True,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    top_p: float = 0.95,
    oauth_token: gr.OAuthToken | None = None,
):
    """Chat with NVIDIA Nemotron 3 Ultra (550B-A55B, NVFP4) via Hugging Face Inference Providers.

    Args:
        message: The user message.
        history: Prior turns as OpenAI-style role/content dicts.
        system_prompt: Optional system instruction.
        enable_thinking: Emit a reasoning trace before the answer.
        max_tokens: Maximum tokens to generate, reasoning included.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
    """
    token = oauth_token.token if oauth_token else FALLBACK_TOKEN
    if not token:
        raise gr.Error("Sign in with Hugging Face (sidebar) to run inference on your account.")

    messages = [{"role": "system", "content": system_prompt}] if system_prompt.strip() else []
    for turn in history:
        content = turn["content"]
        if turn["role"] == "assistant" and isinstance(content, str) and "</details>" in content:
            content = content.split("</details>", 1)[1].strip()
        messages.append({"role": turn["role"], "content": content})
    messages.append({"role": "user", "content": message})

    client = InferenceClient(provider=PROVIDER, api_key=token)
    try:
        stream = client.chat_completion(
            model=MODEL_ID,
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=temperature,
            top_p=top_p,
            stream=True,
            extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}},
        )
        reasoning, raw = "", ""
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning += getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None) or ""
            raw += delta.content or ""
            inline_reasoning, answer = _split_think(raw)
            full_reasoning = (reasoning + inline_reasoning).strip()
            yield _render(full_reasoning, answer, thinking_done=bool(answer))
    except Exception as e:
        raise gr.Error(f"Inference failed ({PROVIDER}): {e}")


with gr.Blocks(fill_height=True, title="Nemotron 3 Ultra Chat") as demo:
    with gr.Sidebar():
        gr.Markdown(
            f"## Nemotron 3 Ultra\n"
            f"[{MODEL_ID}](https://huggingface.co/{MODEL_ID})\n\n"
            f"550B total / 55B active LatentMoE (Mamba-2 + MoE + Attention), 1M context. "
            f"Served via Inference Providers (`{PROVIDER}`); usage is billed to the signed-in account."
        )
        gr.LoginButton("Sign in with Hugging Face")
        system_prompt = gr.Textbox(label="System prompt", lines=3)
        enable_thinking = gr.Checkbox(value=True, label="Reasoning (enable_thinking)")
        max_tokens = gr.Slider(256, 32000, value=4096, step=256, label="Max tokens")
        temperature = gr.Slider(0.0, 2.0, value=1.0, step=0.05, label="Temperature")
        top_p = gr.Slider(0.05, 1.0, value=0.95, step=0.05, label="Top-p")

    gr.ChatInterface(
        respond,
        additional_inputs=[system_prompt, enable_thinking, max_tokens, temperature, top_p],
        examples=[[e] for e in EXAMPLES],
        cache_examples=False,
        fill_height=True,
    )

if __name__ == "__main__":
    demo.launch(mcp_server=True)
