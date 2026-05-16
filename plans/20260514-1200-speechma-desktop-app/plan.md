# SpeechMa Desktop App — Implementation Plan

**Date**: 2026-05-14  
**Status**: Ready for Implementation  
**Goal**: Build a PySide6 desktop app (modeled on Sub2Speech) that generates voice via speechma.com API from text input and SRT files.

---

## Key Technical Facts

- **API**: `POST https://speechma.com/com.api/tts-api.php`
- **Payload**: `{"text": "...", "voice": "voice-XX"}` → returns `audio/mpeg`
- **No auth required** (currently, subject to change)
- **Text limit**: 2000 chars/request (use 1000 for safety)
- **Voice IDs**: Format `voice-XX` (numbers 1–580+)
- **Stack**: Python + PySide6 + requests + ffmpeg-python + imageio-ffmpeg

---

## Implementation Phases

| # | Phase | Status | File |
|---|-------|--------|------|
| 01 | Project Setup & Structure | TODO | [phase-01-project-setup.md](phase-01-project-setup.md) |
| 02 | SpeechMa API Engine | TODO | [phase-02-speechma-engine.md](phase-02-speechma-engine.md) |
| 03 | Voice Catalog | TODO | [phase-03-voice-catalog.md](phase-03-voice-catalog.md) |
| 04 | SRT/TXT Processing Pipeline | TODO | [phase-04-srt-pipeline.md](phase-04-srt-pipeline.md) |
| 05 | UI Components | TODO | [phase-05-ui-components.md](phase-05-ui-components.md) |
| 06 | Background Workers | TODO | [phase-06-workers.md](phase-06-workers.md) |
| 07 | Polish & Packaging | TODO | [phase-07-polish-packaging.md](phase-07-polish-packaging.md) |

---

## Research Reports

- [API Research](research/researcher-01-speechma-api.md)
- [Architecture Research](research/researcher-02-architecture.md)

---

## Reference Project

`D:\project\Sub2Speech` — existing PySide6 desktop TTS app using edge-tts. This project adapts its architecture, replacing the TTS engine with speechma.com HTTP calls.
