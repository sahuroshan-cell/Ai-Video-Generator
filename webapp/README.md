# Reel Forge — real render app

Server-side app: upload a face photo + a storyboard, get back a real
photoreal lip-synced video (Wav2Lip) composited into animated scene
templates (title / bullets / flow / stat / outro), narrated by Piper TTS
(English or Hindi). CPU-only, ~1-3 minutes per video.

This is a different thing from the `claude/reel-forge` browser Artifact
built earlier in this project's history: that one runs entirely client-side
with a procedural (non-photoreal) character and has no backend. This app is
the real-render version, and it needs a server to run on.

## Architecture

- **Compute**: this Docker image (FastAPI + Wav2Lip + Piper + ffmpeg), deployed to Render.
- **Storage + job status**: Supabase — a Postgres `jobs` table and a public `videos` Storage bucket.
- No AI writes the storyboard for you server-side (no Anthropic API key is baked into this
  deployment). The app ships with a bundled example storyboard you edit or replace — same
  `## Title Card / Bullets / Flow / Stat / Outro` text format the browser Artifact's paste box uses.

## One-time setup

### 1. Supabase

1. Create a project at supabase.com (any region/plan).
2. Open the SQL editor, paste and run `supabase/migrations/0001_jobs.sql` from this repo.
   It creates the `jobs` table and a public `videos` storage bucket.
3. Grab two values from Project Settings → API: the **Project URL** and the
   **service_role key** (not the anon key — the app uses the service role key
   server-side only, it's never exposed to the browser).

### 2. Render

1. New → Blueprint, point it at this repo. Render will read `render.yaml` at the repo root.
2. It provisions one Docker web service (`reel-forge`) on the **Standard** plan.
   Do not drop to a free/starter tier — this needs real RAM to hold PyTorch
   and the Wav2Lip checkpoints during inference; 512MB-1GB tiers will crash
   or refuse to boot the image. Standard (2GB+ RAM) is the realistic minimum.
3. In the service's Environment tab, set:
   - `SUPABASE_URL` — the Project URL from step 1.
   - `SUPABASE_SERVICE_KEY` — the service_role key from step 1.
   - `SUPABASE_BUCKET` — leave as `videos` unless you renamed the bucket.
4. Deploy. First build is slow (~3-6 GB image: PyTorch CPU wheel + Wav2Lip
   checkpoints + Piper voices are all fetched during the build).

Once deployed, Render gives you a public URL — that's the live link.

## Local test (optional, before paying for hosting)

```
docker build -f webapp/Dockerfile -t reel-forge .
docker run -p 8000:8000 \
  -e SUPABASE_URL=... -e SUPABASE_SERVICE_KEY=... \
  reel-forge
```

Without `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` set, the app still renders —
job status just lives in memory (lost on restart) and the finished video is
served straight from local disk (`GET /api/jobs/{id}/video`) instead of a
Supabase public URL. Fine for a local smoke test, not for production (no
persistence, single instance only).

## What's not included

- No authentication — anyone with the URL can submit a render. Add auth
  (e.g. Supabase Auth + a check in `main.py`) before sharing this widely.
- No queue/concurrency limits — each request spawns its own render thread.
  On a single Standard instance, two people rendering at once will both be
  slow. A real production setup would add a proper job queue.
- No rate limiting or file-size caps on the photo upload.
