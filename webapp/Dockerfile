# Reel Forge - real render backend.
# Bundles Wav2Lip (photoreal lip-sync) + Piper (TTS) + ffmpeg. CPU-only.
# Needs real resources: ~4GB image, several GB RAM at inference time.
# Build context must be the repository root (docker build -f webapp/Dockerfile .).

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core git git-lfs curl ca-certificates \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# --- Wav2Lip: code + checkpoints, mirrored on Hugging Face (avoids the
# original repo's flaky Google Drive weight links) ---
WORKDIR /opt/wav2lip
RUN git clone --depth 1 https://huggingface.co/camenduru/Wav2Lip.git repo
# The repo's audio.py targets a pre-0.9 librosa API; patch for the version
# pinned in requirements.txt (positional args -> keyword-only).
RUN sed -i \
    "s/librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,/librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,/" \
    repo/audio.py

# --- Piper voices (English + Hindi) ---
RUN mkdir -p /opt/wav2lip/voices && cd /opt/wav2lip/voices && \
    for f in \
      "en/en_US/amy/medium/en_US-amy-medium.onnx" \
      "en/en_US/amy/medium/en_US-amy-medium.onnx.json" \
      "hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx" \
      "hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json"; do \
      curl -sS -L -o "$(basename "$f")" "https://huggingface.co/rhasspy/piper-voices/resolve/main/$f"; \
    done

# --- Python deps ---
COPY webapp/requirements.txt /opt/wav2lip/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /opt/wav2lip/requirements.txt

# --- App code ---
# main.py serves the frontend from ../frontend relative to itself, so keep
# the same sibling-directory layout the source tree uses.
COPY webapp/backend /app
COPY webapp/frontend /frontend
WORKDIR /app

ENV WAV2LIP_DIR=/opt/wav2lip/repo
ENV VOICES_DIR=/opt/wav2lip/voices
ENV RENDER_ROOT=/tmp/reelforge_jobs

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
