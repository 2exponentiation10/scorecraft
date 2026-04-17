from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_DESCRIPTION, APP_TITLE, ROOT_PATH, UPLOAD_DIR
from .storage import JobStore
from .transcription import (
    analyze_score,
    download_youtube_audio,
    normalize_audio,
    run_basic_pitch,
    sanitize_filename,
    validate_upload_filename,
)

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, root_path=ROOT_PATH)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = JobStore()
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def serialize_job(job: dict) -> dict:
    base_url = ROOT_PATH.rstrip("/")
    return {
        "id": job["id"],
        "createdAt": job["created_at"],
        "updatedAt": job["updated_at"],
        "status": job["status"],
        "title": job.get("title") or (job.get("source_value") or "Untitled score"),
        "sourceType": job["source_type"],
        "sourceValue": job.get("source_value"),
        "error": job.get("error"),
        "progress": job.get("progress") or 0,
        "progressLabel": job.get("progress_label") or "대기 중",
        "durationSeconds": job.get("duration_seconds"),
        "summary": job.get("summary") or {},
        "chords": job.get("chords") or [],
        "downloads": {
            "musicxml": f"{base_url}/api/jobs/{job['id']}/musicxml" if job.get("musicxml_path") else None,
            "midi": f"{base_url}/api/jobs/{job['id']}/midi" if job.get("midi_path") else None,
            "chords": f"{base_url}/api/jobs/{job['id']}/chords" if job.get("chords_path") else None,
        },
    }


def process_job(job_id: str) -> None:
    job = store.get_job(job_id)
    work_dir = Path(job["work_dir"])
    try:
        store.update_job(job_id, status="running", progress=0.1, progress_label="입력 소스 준비 중")
        if job["source_type"] == "youtube":
            source_audio, inferred_title = download_youtube_audio(job["source_value"], work_dir)
            store.update_job(job_id, title=inferred_title)
        else:
            source_audio = work_dir / "uploaded" / Path(job["source_value"]).name
            if not source_audio.exists():
                raise RuntimeError("업로드된 파일을 찾을 수 없습니다.")

        store.update_job(job_id, progress=0.35, progress_label="오디오 정규화 중")
        normalized_audio, duration = normalize_audio(source_audio, work_dir)
        store.update_job(
            job_id,
            normalized_audio_path=str(normalized_audio),
            duration_seconds=duration,
            progress=0.55,
            progress_label="음표 추출 중",
        )

        midi_path = run_basic_pitch(normalized_audio, work_dir)
        store.update_job(job_id, midi_path=str(midi_path), progress=0.8, progress_label="코드 및 악보 구성 중")

        musicxml_path, chords_path, summary = analyze_score(midi_path, work_dir)
        summary_path = work_dir / "summary.json"
        store.update_job(
            job_id,
            status="succeeded",
            progress=1.0,
            progress_label="완료",
            musicxml_path=str(musicxml_path),
            chords_path=str(chords_path),
            summary_path=str(summary_path),
        )
    except Exception as exc:  # pragma: no cover
        store.update_job(job_id, status="failed", error=str(exc), progress_label="실패")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": APP_TITLE}


@app.get("/api/jobs")
async def list_jobs() -> dict:
    return {"jobs": [serialize_job(job) for job in store.list_jobs()]}


@app.post("/api/jobs")
async def create_job(
    youtube_url: Annotated[str | None, Form()] = None,
    audio_file: Annotated[UploadFile | None, File()] = None,
) -> JSONResponse:
    youtube_url = (youtube_url or "").strip()
    if not youtube_url and not audio_file:
        raise HTTPException(status_code=400, detail="유튜브 링크 또는 오디오 파일 중 하나는 필요합니다.")

    job_id = uuid.uuid4().hex[:12]
    work_dir = Path(store.create_job(job_id, "youtube" if youtube_url else "upload", youtube_url or (audio_file.filename if audio_file else None))["work_dir"])

    if audio_file is not None:
        validate_upload_filename(audio_file.filename or "")
        upload_dir = work_dir / "uploaded"
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / sanitize_filename(audio_file.filename or "audio")
        with destination.open("wb") as target:
            shutil.copyfileobj(audio_file.file, target)
        store.update_job(job_id, source_value=str(destination))

    thread = threading.Thread(target=process_job, args=(job_id,), daemon=True)
    thread.start()
    return JSONResponse(serialize_job(store.get_job(job_id)), status_code=202)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    try:
        return serialize_job(store.get_job(job_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")


@app.get("/api/jobs/{job_id}/musicxml")
async def get_musicxml(job_id: str) -> FileResponse:
    job = store.get_job(job_id)
    if not job.get("musicxml_path"):
        raise HTTPException(status_code=404, detail="MusicXML이 아직 생성되지 않았습니다.")
    return FileResponse(job["musicxml_path"], media_type="application/vnd.recordare.musicxml+xml", filename=f"{job_id}.musicxml")


@app.get("/api/jobs/{job_id}/midi")
async def get_midi(job_id: str) -> FileResponse:
    job = store.get_job(job_id)
    if not job.get("midi_path"):
        raise HTTPException(status_code=404, detail="MIDI가 아직 생성되지 않았습니다.")
    return FileResponse(job["midi_path"], media_type="audio/midi", filename=f"{job_id}.mid")


@app.get("/api/jobs/{job_id}/chords")
async def get_chords(job_id: str) -> JSONResponse:
    job = store.get_job(job_id)
    return JSONResponse(job.get("chords") or [])
