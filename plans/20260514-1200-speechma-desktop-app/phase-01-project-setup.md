# Phase 01 — Project Setup & Structure

**Context**: [Parent Plan](plan.md)  
**Date**: 2026-05-14  
**Priority**: High — must complete before all other phases  
**Status**: TODO | **Review**: Pending

---

## Overview

Create the project skeleton in `d:\project\speeachMaProject\`, mirroring Sub2Speech's proven layout but adapted for speechma.com.

---

## Key Insights

- Sub2Speech uses `src/sub2speech/` package layout; replicate with `src/speechmaapp/`
- Sub2Speech already has working SRT parser, audio processor, models, UI patterns — **copy and adapt**, don't rewrite
- The only fundamentally new code is the HTTP engine replacing edge-tts
- `ffmpeg-python` + `imageio-ffmpeg` for audio; Sub2Speech already handles this well
- Remove `edge-tts` and `async` TTS patterns; replace with sync `requests` in QThread

---

## Requirements

- Python 3.10+
- Windows 10/11 (primary target; same as Sub2Speech)
- Network access to speechma.com
- All dependencies installable via pip

---

## Architecture

```
speeachMaProject/
├── src/
│   └── speechmaapp/
│       ├── __init__.py          # version = "1.0"
│       ├── app.py               # entry point (mirror Sub2Speech app.py)
│       ├── config.py            # AppConfig + Settings dataclass
│       ├── core/
│       │   ├── __init__.py
│       │   ├── speechma_engine.py   # NEW: HTTP TTS engine
│       │   ├── audio_processor.py   # COPIED from Sub2Speech
│       │   ├── subtitle_parser.py   # COPIED from Sub2Speech
│       │   └── voices_catalog.py    # ADAPTED: speechma voices
│       ├── models/
│       │   ├── __init__.py
│       │   ├── speaker.py       # COPIED from Sub2Speech
│       │   └── subtitle.py      # COPIED from Sub2Speech
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py   # ADAPTED from Sub2Speech
│       │   ├── output_panel.py  # COPIED from Sub2Speech
│       │   ├── speaker_manager.py # ADAPTED: no rate/pitch/vol params
│       │   ├── subtitle_table.py  # COPIED from Sub2Speech
│       │   ├── theme.py         # COPIED from Sub2Speech
│       │   └── animated_progress.py # COPIED from Sub2Speech
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── i18n.py          # ADAPTED: VI/EN translations
│       │   └── logging_utils.py # COPIED from Sub2Speech
│       └── workers/
│           ├── __init__.py
│           ├── tts_worker.py    # ADAPTED: uses speechma_engine
│           └── preview_worker.py # ADAPTED: uses speechma_engine
├── config/
│   └── voices.json              # Bundled speechma voice catalog
├── src/
│   └── ico.png                  # App icon (copy from Sub2Speech)
├── requirements.txt
├── setup.bat
└── run.bat
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\app.py` — entry point pattern
- `D:\project\Sub2Speech\src\sub2speech\config.py` — AppConfig pattern
- `D:\project\Sub2Speech\requirements.txt` — dep pattern

---

## Implementation Steps

### 1. Create directory structure
```
mkdir -p src/speechmaapp/{core,models,ui,utils,workers}
mkdir -p config logs Audio temp
```

### 2. Create `requirements.txt`
```
PySide6>=6.7
requests>=2.32
ffmpeg-python>=0.2
imageio-ffmpeg>=0.5
pyinstaller>=6.6
```
Remove `edge-tts` (no longer needed). Remove `asyncio` deps.

### 3. Create `setup.bat`
```bat
@echo off
pip install -r requirements.txt
echo Setup done.
pause
```

### 4. Create `run.bat`
```bat
@echo off
cd /d "%~dp0"
python -m speechmaapp.app
pause
```

### 5. Create `src/speechmaapp/__init__.py`
```python
__version__ = "1.0"
```

### 6. Create `config.py` — adapt from Sub2Speech
```python
@dataclass
class Settings:
    output_dir: str
    save_original_audio: bool
    last_language_group: str
    language: str
    # Remove tts_concurrency — speechma has rate limits; default 2
    tts_concurrency: int
```

Key change in `AppConfig`: `voices_cache_path` points to bundled `config/voices.json`, not fetched from edge-tts.

---

## Todo List

- [ ] Create all directories
- [ ] Write requirements.txt (no edge-tts, add requests)
- [ ] Write setup.bat and run.bat
- [ ] Write `__init__.py` with version
- [ ] Write config.py (adapt from Sub2Speech)
- [ ] Copy icon from Sub2Speech
- [ ] Copy models (speaker.py, subtitle.py) unchanged
- [ ] Copy utils (logging_utils.py) unchanged
- [ ] Copy audio_processor.py unchanged
- [ ] Copy subtitle_parser.py unchanged
- [ ] Copy UI components: output_panel.py, subtitle_table.py, theme.py, animated_progress.py

---

## Success Criteria

- `run.bat` launches app without ImportError
- Config loads/saves settings.json correctly
- All copied files pass import check

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Sub2Speech files have edge-tts imports in copied modules | Medium | Grep for `edge_tts` and remove/replace |
| Directory name collision (config/ exists) | Low | Check before creating |

---

## Security Considerations

- No credentials stored in files
- Config dir user-writable only

---

## Next Steps

→ Phase 02: Build speechma_engine.py
