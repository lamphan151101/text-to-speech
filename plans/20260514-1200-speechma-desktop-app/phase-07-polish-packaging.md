# Phase 07 — Polish & Packaging

**Context**: [Parent Plan](plan.md) | Depends on all prior phases  
**Date**: 2026-05-14  
**Priority**: Medium  
**Status**: TODO | **Review**: Pending

---

## Overview

Final polish: README, logging, error messages, and PyInstaller packaging into a standalone Windows `.exe`.

---

## Key Insights

- Sub2Speech uses `imageio-ffmpeg` to bundle FFmpeg — same approach here (no system FFmpeg required)
- PyInstaller requires `--hidden-import` for `requests` ecosystem
- Bundle `config/voices.json` as data file in the executable
- Windows taskbar icon requires SetCurrentProcessExplicitAppUserModelID (copy from Sub2Speech)

---

## Requirements

- Single `.exe` runnable without Python installed
- Bundled FFmpeg (via imageio-ffmpeg)
- Bundled `voices.json`
- Log rotation (7-day, daily rotation)

---

## Architecture

### PyInstaller spec file (`SpeechMa.spec`)
```python
a = Analysis(
    ['src/speechmaapp/app.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config/voices.json', 'config'),
        ('src/ico.png', '.'),
    ],
    hiddenimports=[
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'imageio_ffmpeg',
    ],
    ...
)
```

### Build script (`build.bat`)
```bat
@echo off
pip install pyinstaller
pyinstaller SpeechMa.spec --noconfirm
echo Build done: dist\SpeechMa\SpeechMa.exe
pause
```

### Logging
Copy `logging_utils.py` from Sub2Speech unchanged:
- Rotating log handler (1 file/day, keep 7)
- Log to `logs/speechma_YYYYMMDD.log`
- Log levels: INFO for normal operations, ERROR for failures
- Never log full text content (privacy)

### Error messages (user-facing)
| Error | Message to user |
|-------|----------------|
| Network error | "Lỗi kết nối mạng. Kiểm tra internet và thử lại." |
| API error (non-audio response) | "Dịch vụ speechma.com trả lời không hợp lệ. Thử lại sau." |
| All retries failed | "Không thể tạo giọng cho đoạn {X}. Nhấn Xuất MP3 để thử lại." |
| Empty text | "Nội dung quá ngắn để tổng hợp giọng." |

### README.md
Bilingual (VI/EN), cover:
- Features list
- Quick start (setup.bat + run.bat)
- SRT workflow (assign voice per speaker)
- TXT workflow (single voice)
- Troubleshooting (network errors, voice not found)
- Note: app connects to speechma.com; internet required

---

## Related Code Files

- `D:\project\Sub2Speech\README.md` — template
- `D:\project\Sub2Speech\src\sub2speech\utils\logging_utils.py` — copy
- `D:\project\Sub2Speech\run.bat`, `setup.bat` — template

---

## Implementation Steps

1. Copy `logging_utils.py` verbatim
2. Write `SpeechMa.spec` PyInstaller spec
3. Write `build.bat`
4. Test `pyinstaller SpeechMa.spec` on dev machine
5. Run `.exe` — verify it launches without Python
6. Test export with 3-segment SRT on built exe
7. Write `README.md` (bilingual)

---

## Todo List

- [ ] Copy logging_utils.py
- [ ] Write SpeechMa.spec
- [ ] Write build.bat
- [ ] Test build on dev machine
- [ ] Test .exe without Python in PATH
- [ ] Write README.md

---

## Success Criteria

- `dist/SpeechMa/SpeechMa.exe` launches on fresh Windows machine
- No "Python not found" or DLL errors
- Export produces valid MP3 from within .exe
- Logs written to `logs/` beside exe

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Missing DLL in .exe | Medium | Test on clean VM; add `--hidden-import` as needed |
| voices.json not found in .exe | Medium | Test DATA path with `sys._MEIPASS` in app_root resolution |
| FFmpeg not bundled | Low | imageio-ffmpeg bundles it automatically |
| App blocked by Windows Defender | Low | Sign exe or add exception note to README |

---

## Security Considerations

- `.exe` makes HTTP requests to speechma.com — document this clearly in README
- No credentials stored or transmitted beyond text + voice_id to speechma.com
- Log files contain segment indices and file paths — avoid logging full text content

---

## Unresolved Questions

1. Will speechma.com add CAPTCHA to the API endpoint in the future? (monitor + document workaround)
2. Does speechma.com have a Terms of Service that restricts automated/desktop usage?
3. Are there Vietnamese voices on speechma.com? (need to verify during Phase 03 voice discovery)
4. Does the API accept speed/pitch parameters that the GitHub wrapper didn't expose? (verify via DevTools)

---

## Next Steps

Project is complete. Future enhancements:
- Add speed/pitch sliders if API supports them (verify via DevTools)
- Add batch SRT directory processing
- Add progress ETA display
