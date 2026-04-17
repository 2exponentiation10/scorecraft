from __future__ import annotations

import os
from pathlib import Path

APP_TITLE = "Scorecraft"
APP_DESCRIPTION = (
    "YouTube 또는 오디오 파일을 입력받아 MIDI, MusicXML, 코드 진행을 생성하는 "
    "AI 악보 초안 서비스"
)
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/tmp/scorecraft-data")).resolve()
ROOT_PATH = os.getenv("ROOT_PATH", "")
JOB_DB_PATH = APP_DATA_DIR / "scorecraft.sqlite3"
UPLOAD_DIR = APP_DATA_DIR / "uploads"
JOB_DIR = APP_DATA_DIR / "jobs"
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"}
