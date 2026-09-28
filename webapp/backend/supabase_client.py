"""Thin wrapper around Supabase: a `jobs` table for status and a Storage
bucket for finished videos. Both are optional -- if the env vars aren't
set, the app still runs renders, it just can't persist status across
restarts or serve the result from storage (main.py falls back to serving
the file straight off local disk in that case).
"""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "videos")

_client = None


def enabled():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


def client():
    global _client
    if _client is None and enabled():
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def create_job(job_id, topic, language):
    c = client()
    if not c:
        return
    c.table("jobs").insert({
        "id": job_id, "status": "queued", "progress": "queued",
        "topic": topic, "language": language,
    }).execute()


def update_job(job_id, **fields):
    c = client()
    if not c:
        return
    c.table("jobs").update(fields).eq("id", job_id).execute()


def get_job(job_id):
    c = client()
    if not c:
        return None
    r = c.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return r.data[0] if r.data else None


def upload_video(local_path, storage_name):
    c = client()
    if not c:
        return None
    with open(local_path, "rb") as f:
        c.storage.from_(SUPABASE_BUCKET).upload(
            storage_name, f, {"content-type": "video/mp4", "upsert": "true"}
        )
    return c.storage.from_(SUPABASE_BUCKET).get_public_url(storage_name)
