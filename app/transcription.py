from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from music21 import chord as m21chord
from music21 import converter, harmony, meter, note, stream, tempo

from .config import SUPPORTED_AUDIO_EXTENSIONS


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
    return clean[:80] or f"source-{uuid.uuid4().hex[:8]}"


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, check=True, text=True, capture_output=True)


def download_youtube_audio(url: str, work_dir: Path) -> tuple[Path, str]:
    output_template = str(work_dir / "source.%(ext)s")
    run_command([
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "-o",
        output_template,
        url,
    ], cwd=work_dir)
    candidates = sorted(work_dir.glob("source.*"))
    if not candidates:
        raise RuntimeError("유튜브 오디오 추출에 실패했습니다.")
    audio_path = candidates[0]
    title = audio_path.stem.replace("source", "YouTube audio")
    return audio_path, title


def normalize_audio(input_path: Path, work_dir: Path) -> tuple[Path, float | None]:
    normalized = work_dir / "normalized.wav"
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "22050",
        str(normalized),
    ]
    run_command(args, cwd=work_dir)

    duration = None
    try:
        probe = run_command([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(normalized),
        ])
        duration = float(probe.stdout.strip())
    except Exception:
        duration = None
    return normalized, duration


def run_basic_pitch(audio_path: Path, work_dir: Path) -> Path:
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict_and_save

    output_dir = work_dir / "basic_pitch"
    output_dir.mkdir(parents=True, exist_ok=True)
    predict_and_save(
        [str(audio_path)],
        str(output_dir),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
    )

    midi_files = sorted(output_dir.glob("*.mid")) + sorted(output_dir.glob("*.midi"))
    if not midi_files:
        raise RuntimeError("MIDI 생성에 실패했습니다.")
    midi_path = output_dir / "transcription.mid"
    shutil.copy2(midi_files[0], midi_path)
    return midi_path


def chord_quality(intervals: set[int]) -> str:
    if {0, 4, 7}.issubset(intervals):
        return "maj7" if 11 in intervals else ("7" if 10 in intervals else "")
    if {0, 3, 7}.issubset(intervals):
        return "m7" if 10 in intervals else "m"
    if {0, 3, 6}.issubset(intervals):
        return "dim7" if 9 in intervals else "dim"
    if {0, 4, 8}.issubset(intervals):
        return "aug"
    if {0, 5, 7}.issubset(intervals):
        return "sus4"
    if {0, 2, 7}.issubset(intervals):
        return "sus2"
    return ""


def chord_symbol_from_chord(ch: m21chord.Chord) -> str:
    try:
        root = ch.root()
    except Exception:
        root = ch.bass()
    if root is None:
        return "N.C."
    pcs = sorted({(p.pitchClass - root.pitchClass) % 12 for p in ch.pitches})
    quality = chord_quality(set(pcs))
    name = root.name.replace("-", "b")
    return f"{name}{quality}"


def analyze_score(midi_path: Path, work_dir: Path) -> tuple[Path, Path, dict[str, Any]]:
    score = converter.parse(str(midi_path))
    if not score.recurse().getElementsByClass(meter.TimeSignature):
        score.insert(0, meter.TimeSignature("4/4"))
    if not score.recurse().getElementsByClass(tempo.MetronomeMark):
        score.insert(0, tempo.MetronomeMark(number=96))

    chordified = score.chordify()
    chord_events: list[dict[str, Any]] = []
    for m in chordified.parts[0].getElementsByClass(stream.Measure):
        measure_label = m.measureNumber or len(chord_events) + 1
        inserted = False
        for element in m.notes:
            if isinstance(element, m21chord.Chord) and element.pitches:
                symbol = chord_symbol_from_chord(element)
                chord_events.append({
                    "measure": measure_label,
                    "offset": round(float(element.offset), 3),
                    "symbol": symbol,
                    "pitches": [p.nameWithOctave for p in element.pitches[:6]],
                })
                if not inserted:
                    try:
                        score.insert(m.offset, harmony.ChordSymbol(symbol))
                    except Exception:
                        pass
                    inserted = True
                break

    notes = list(score.recurse().notes)
    summary = {
        "noteCount": len([n for n in notes if isinstance(n, (note.Note, m21chord.Chord))]),
        "estimatedMeasures": len(list(score.parts[0].getElementsByClass(stream.Measure))) if score.parts else 0,
        "partCount": len(score.parts) if score.parts else 1,
        "chordCount": len(chord_events),
    }

    chords_path = work_dir / "chords.json"
    chords_path.write_text(json.dumps(chord_events, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = work_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    musicxml_path = work_dir / "score.musicxml"
    score.write("musicxml", fp=str(musicxml_path))
    return musicxml_path, chords_path, summary


def validate_upload_filename(filename: str) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext or 'unknown'}")
