import os
import shutil
import tempfile
import threading
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import supabase_client as sb
from face_prep import NoFaceFound, prepare_face
from render_pipeline import RenderError, render_video
from storyboard import EXAMPLE, StoryboardError, parse as parse_storyboard

app = FastAPI(title="Reel Forge - real render")

RENDER_ROOT = os.environ.get("RENDER_ROOT", "/tmp/reelforge_jobs")
os.makedirs(RENDER_ROOT, exist_ok=True)

# In-memory fallback so the app works even with no Supabase configured
# (single-instance only; Supabase is the source of truth when set).
_local_jobs = {}


def _set_job(job_id, **fields):
    _local_jobs.setdefault(job_id, {}).update(fields)
    sb.update_job(job_id, **fields)


def _get_job(job_id):
    remote = sb.get_job(job_id)
    if remote:
        return remote
    return _local_jobs.get(job_id)


def _run_job(job_id, face_src, language, scenes):
    jobdir = f"{RENDER_ROOT}/{job_id}"
    os.makedirs(jobdir, exist_ok=True)
    try:
        face_path = f"{jobdir}/face.png"
        try:
            prepare_face(face_src, face_path)
        except NoFaceFound as e:
            _set_job(job_id, status="error", error=str(e))
            return

        out_path = f"{jobdir}/final.mp4"

        def on_progress(i, n, scene):
            _set_job(job_id, status="running", progress=f"{i + 1}/{n}: {scene['heading']}")

        render_video(face_path, language, scenes, out_path, on_progress=on_progress)

        result_url = sb.upload_video(out_path, f"{job_id}.mp4")
        _set_job(job_id, status="done", progress="done",
                 result_url=result_url, local_path=out_path if not result_url else None)
    except RenderError as e:
        _set_job(job_id, status="error", error=str(e))
    except Exception as e:  # noqa: BLE001 - report unexpected failures to the client too
        _set_job(job_id, status="error", error=f"unexpected: {e}")


@app.get("/api/example-storyboard")
def example_storyboard():
    return {"text": EXAMPLE}


@app.post("/api/generate")
async def generate(
    photo: UploadFile = File(...),
    language: str = Form("en"),
    storyboard_text: str = Form(...),
):
    if language not in ("en", "hi"):
        raise HTTPException(400, "language must be 'en' or 'hi'")
    try:
        scenes = parse_storyboard(storyboard_text)
    except StoryboardError as e:
        raise HTTPException(400, str(e))

    job_id = str(uuid.uuid4())
    jobdir = f"{RENDER_ROOT}/{job_id}"
    os.makedirs(jobdir, exist_ok=True)
    face_src = f"{jobdir}/upload{os.path.splitext(photo.filename or '')[1] or '.jpg'}"
    with open(face_src, "wb") as f:
        shutil.copyfileobj(photo.file, f)

    sb.create_job(job_id, topic=scenes[0]["heading"], language=language)
    _set_job(job_id, status="queued", progress="queued")

    threading.Thread(target=_run_job, args=(job_id, face_src, language, scenes), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, "unknown job id")
    return JSONResponse({
        "status": job.get("status"),
        "progress": job.get("progress"),
        "result_url": job.get("result_url"),
        "error": job.get("error"),
        "has_local_file": bool(job.get("local_path")),
    })


@app.get("/api/jobs/{job_id}/video")
def job_video(job_id: str):
    job = _get_job(job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "video not ready")
    if job.get("result_url"):
        raise HTTPException(409, "video is in Supabase storage; use result_url directly")
    if not job.get("local_path") or not os.path.exists(job["local_path"]):
        raise HTTPException(404, "video file missing")
    return FileResponse(job["local_path"], media_type="video/mp4", filename=f"{job_id}.mp4")


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend"), html=True), name="frontend")
