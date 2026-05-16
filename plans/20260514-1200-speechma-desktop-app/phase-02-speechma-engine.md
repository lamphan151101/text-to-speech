# Phase 02 — SpeechMa API Engine

**Context**: [Parent Plan](plan.md) | Depends on [Phase 01](phase-01-project-setup.md)  
**Date**: 2026-05-14  
**Priority**: Critical — core feature  
**Status**: TODO | **Review**: Pending

---

## Overview

Build `speechma_engine.py` — the HTTP-based TTS engine replacing `edge_tts_engine.py`. This is the most novel component of the project.

---

## Key Insights

**Confirmed API from reverse engineering (fairy-root/Speechma-API)**:
- **Endpoint**: `POST https://speechma.com/com.api/tts-api.php`
- **Headers**: Must include Origin, Referer, User-Agent mimicking browser
- **Payload**: `{"text": "<content>", "voice": "voice-35"}`
- **Response**: `Content-Type: audio/mpeg` → raw MP3 bytes
- **No auth required** (as of May 2026)
- **Text limit**: 2000 chars; use **1000 chars** per chunk for safety

**Key differences from edge-tts**:
- Sync HTTP (not async WebSocket) → use `requests` in QThread
- **`pitch` and `rate` ARE supported** (default 0, confirmed from source JS)
- **CAPTCHA required**: validate via `/com.api/captcha/captcha.php` → sets session cookie → TTS API uses `credentials: same-origin` (i.e., session cookie)
- Characters must be sanitized (remove `'`, `"`, `&` → replace with space/`and`)
- Retry logic needed (3 attempts per segment)

### CAPTCHA Flow (critical discovery)
The TTS API requires a valid session from captcha:
1. `GET /com.api/captcha/captcha.php?t={timestamp}` → JPEG image (5-digit code)
2. Show image to user in a Qt dialog → user types the code
3. `POST /com.api/captcha/captcha.php` with `{"code": "12345"}` → `{"success": true}` → sets session cookie
4. All TTS calls use `requests.Session()` (cookie persists automatically)
5. Session valid until server expires it; re-prompt captcha on 401/403

---

## Requirements

- Handle text > 1000 chars by splitting at sentence boundaries
- Retry failed requests up to 3 times with exponential backoff
- Return raw MP3 bytes for saving to file
- Thread-safe (called from QThread, not main thread)
- Sanitize text before sending

---

## Architecture

### `TtsJob` dataclass
```python
@dataclass
class TtsJob:
    seg_index: int
    text: str
    voice: str          # "voice-35"
    out_path: str       # where to save the MP3
```

Note: No `rate`, `volume`, `pitch` fields (not supported by speechma.com API). Remove `auto_emotion` feature entirely for this app.

### `TtsJob` dataclass (updated — pitch/rate included)
```python
@dataclass
class TtsJob:
    seg_index: int
    text: str
    voice: str          # "voice-314"
    out_path: str
    pitch: int = 0      # -100 to +100 (speechma range TBD)
    rate: int = 0       # -100 to +100 (speechma range TBD)
```

### Core function signatures
```python
def ensure_session_valid(config) -> bool:
    """Check session; if expired, show captcha dialog to user."""

def synthesize_one(text: str, voice: str, out_path: str,
                   pitch: int = 0, rate: int = 0, retries: int = 3) -> None:
    """Call speechma API, save MP3 to out_path. Raises RuntimeError on failure."""

def synthesize_batch(jobs: list[TtsJob], concurrency: int,
                     on_done: Callable[[TtsJob, bool, Exception|None], None]) -> None:
    """Process multiple jobs with limited concurrency using ThreadPoolExecutor."""
```

### HTTP Session (module-level singleton)
```python
_session = requests.Session()
_session.headers.update({
    'Host': 'speechma.com',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
    'Accept': '*/*',
    'Origin': 'https://speechma.com',
    'Referer': 'https://speechma.com/',
    'Accept-Encoding': 'gzip, deflate, br',
})
```

### Text sanitization
```python
def _sanitize(text: str) -> str:
    """Remove chars that cause API errors."""
    return text.replace("'", "").replace('"', '').replace("&", "and")
```

### Text chunking
For SRT mode, each subtitle segment is typically short (<500 chars), so chunking is rarely needed. For TXT mode, segments are pre-chunked at 500 words in `subtitle_parser.py`. Still, add safety check:
```python
def _chunk_text(text: str, limit: int = 1000) -> list[str]:
    """Split at sentence boundaries if text exceeds limit."""
```

### `synthesize_one` logic
```python
def synthesize_one(text: str, voice: str, out_path: str, retries: int = 3) -> None:
    sanitized = _sanitize(text)
    if not sanitized or len(sanitized) < 2:
        raise ValueError(f"Text too short after sanitization: {repr(text[:40])}")
    
    payload = {"text": sanitized, "voice": voice}
    last_exc = None
    
    for attempt in range(retries):
        try:
            resp = _session.post(
                "https://speechma.com/com.api/tts-api.php",
                data=json.dumps(payload),
                timeout=60,
            )
            resp.raise_for_status()
            if resp.headers.get("Content-Type", "").startswith("audio/"):
                Path(out_path).write_bytes(resp.content)
                return
            raise RuntimeError(f"Unexpected Content-Type: {resp.headers.get('Content-Type')}")
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
    
    raise RuntimeError(f"Failed after {retries} attempts: {last_exc}") from last_exc
```

### `synthesize_batch` — replaces asyncio with ThreadPoolExecutor
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def synthesize_batch(jobs: list[TtsJob], concurrency: int,
                     on_done: Callable) -> None:
    concurrency = max(1, min(concurrency, 4))  # speechma limit: keep low
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_job = {
            executor.submit(_run_one, job): job
            for job in jobs
        }
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                future.result()
                on_done(job, True, None)
            except Exception as exc:
                on_done(job, False, exc)
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\core\edge_tts_engine.py` — original engine (replace)
- `D:\project\Sub2Speech\src\sub2speech\workers\tts_worker.py` — caller pattern

---

## Implementation Steps

1. Create `src/speechmaapp/core/speechma_engine.py`
2. Define `_session` module-level requests.Session with headers
3. Implement `_sanitize(text)` helper
4. Implement `_chunk_text(text, limit=1000)` helper
5. Implement `synthesize_one(text, voice, out_path, retries=3)`
6. Implement `synthesize_batch(jobs, concurrency, on_done)` using ThreadPoolExecutor
7. Add logging for each attempt/retry/failure

---

## Todo List

- [ ] Create speechma_engine.py
- [ ] Module-level `_session` with proper headers
- [ ] `TtsJob` dataclass (no rate/pitch/vol fields)
- [ ] `_sanitize()` text cleaner
- [ ] `_chunk_text()` for >1000 char text
- [ ] `synthesize_one()` with 3-retry logic
- [ ] `synthesize_batch()` with ThreadPoolExecutor
- [ ] Unit-test manually: call API with sample text, verify MP3 saved

---

## Success Criteria

- `synthesize_one("Hello world", "voice-35", "test.mp3")` saves a valid MP3
- Retry fires on network failure
- Text with special chars sanitized correctly
- Batch processes 5 jobs concurrently (concurrency=2) without errors

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| API endpoint changes | Medium | Log + alert user; plan for config-overridable URL |
| Rate limiting (HTTP 429) | Medium | Backoff + cap concurrency at 2 |
| CAPTCHA suddenly required | Low | Fall back to manual browser flow; log clearly |
| Large text segment fails | Low | `_chunk_text` splits and concatenates audio |

---

## Security Considerations

- Do not store API keys (none needed currently)
- Do not log full text content (privacy)
- Headers mimic browser to avoid bot detection (ethical grey area — acceptable for personal desktop use)

---

## Next Steps

→ Phase 03: Voice Catalog
