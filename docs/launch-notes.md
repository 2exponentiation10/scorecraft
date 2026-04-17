# 2026-04-17 Scorecraft launch notes

## What shipped
- New AI score drafting service at `https://protfolio.store/scorecraft/`
- FastAPI backend with automatic docs at `https://protfolio.store/scorecraft/docs`
- Input support for YouTube links and uploaded audio files
- Background job execution for transcription
- MIDI output, MusicXML export, and chord timeline JSON
- Browser score preview via OpenSheetMusicDisplay
- GitHub Actions deployment on self-hosted runner
- Nginx reverse proxy under the existing root domain

## Processing pipeline
1. User submits a YouTube URL or an audio file.
2. Server extracts or stores the source audio.
3. ffmpeg normalizes the audio.
4. Basic Pitch creates a MIDI draft.
5. music21 converts the MIDI into MusicXML and extracts chord events.
6. Frontend shows job progress and exposes downloads.

## Notes
- Best suited for piano solo or simple melodic material.
- Generated score is a draft and still needs human cleanup for production-quality notation.
- YouTube processing should only be used for content the user has the right to process.
