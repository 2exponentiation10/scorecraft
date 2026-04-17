# Scorecraft

Scorecraft is a portfolio MVP that turns a YouTube link or audio file into a draft score bundle:

- MIDI transcription
- MusicXML export
- Chord timeline JSON
- In-browser score preview

## Stack
- FastAPI
- basic-pitch
- music21
- yt-dlp
- ffmpeg
- Docker / GitHub Actions

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Docker run
```bash
docker compose up --build
```

Open:
- http://127.0.0.1:7086/
- http://127.0.0.1:7086/docs

## Limitations
- Best quality for piano solo or simple melodic material.
- Polyphonic live recordings still require manual cleanup.
- Use only content you have the right to process.
