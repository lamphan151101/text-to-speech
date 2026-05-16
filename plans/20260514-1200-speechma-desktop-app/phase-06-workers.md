# Phase 06 — Background Workers

**Context**: [Parent Plan](plan.md) | Depends on [Phase 02](phase-02-speechma-engine.md), [Phase 04](phase-04-srt-pipeline.md)  
**Date**: 2026-05-14  
**Priority**: High  
**Status**: TODO | **Review**: Pending

---

## Overview

Implement the QThread-based background workers that handle TTS generation and audio preview without blocking the UI. This phase formalizes the worker design sketched in Phase 04.

---

## Key Insights

- Sub2Speech uses asyncio in TtsWorker; this app uses ThreadPoolExecutor (sync requests)
- `synthesize_batch` in `speechma_engine.py` is synchronous — called directly from `TtsWorker.run()`
- Progress signals emitted after each segment completes
- Session management: the `requests.Session` lives at module level in `speechma_engine.py` — thread-safe for reads, but each thread makes its own request

---

## Requirements

### `TtsWorker`
- Signals: `progress(int)`, `finished(str)`, `incomplete(object)`, `error(str)`
- Accepts: `segments`, `segment_voice_map`, `output_path`, `save_original`, `retry_only_indices`
- No `option_map` (no rate/pitch/vol)
- Calls `synthesize_batch` from `speechma_engine`
- On complete: calls audio assembly (timeline or sequential)
- Session dir: `temp/export_sessions/{source_name}_{md5}/`

### `PreviewWorker`
- Signals: `finished(str)`, `error(str)`
- Accepts: `config`, `text: str`, `voice: str`
- Calls `synthesize_one(text[:200], voice, preview_path)`
- Saves to `temp/preview_XXXXXXXX.mp3`

---

## Architecture

### `TtsWorker.run()` flow
```
1. Collect target segments (all or retry_only)
2. Build TtsJob list from segments + voice_map
3. Call synthesize_batch(jobs, concurrency=2, on_done=_on_segment_done)
   - _on_segment_done increments progress, tracks failures
4. If failures: emit incomplete(failed_list); return
5. If success: assemble audio
   - SRT: build_timeline_audio()
   - TXT: concatenate_audio_files_to_mp3()
   - Single: export_single_mp3()
6. Emit finished(output_path)
7. Cleanup session dir
```

### Thread safety note
`on_done` callback from `synthesize_batch` runs in worker threads (not main thread). Use a list + lock to collect results:
```python
import threading
_lock = threading.Lock()

def _on_segment_done(job, ok, exc):
    with _lock:
        if ok:
            ok_count += 1
        else:
            failed_segments.append(job.seg_index)
        processed += 1
    self.progress.emit(int(processed / total * 80))
```

### `TtsWorker` full signature
```python
class TtsWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)
    incomplete = Signal(object)
    error = Signal(str)

    def __init__(
        self, config, source_name, source_file_name, source_md5,
        segments, segment_voice_map, output_path,
        save_original=False, retry_only_indices=None, is_text_input=False
    ):
```

### `PreviewWorker` full signature
```python
class PreviewWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, config, text: str, voice: str):
        # voice is "voice-35" format

    def run(self):
        preview_path = str(Path(self.config.temp_dir) / f"preview_{uuid4().hex[:8]}.mp3")
        try:
            synthesize_one(self.text, self.voice, preview_path)
            self.finished.emit(preview_path)
        except Exception as exc:
            self.error.emit(str(exc))
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\workers\tts_worker.py` — original (heavily adapted)
- `D:\project\Sub2Speech\src\sub2speech\workers\preview_worker.py` — original (simplified)
- `src/speechmaapp/core/speechma_engine.py` — [Phase 02]

---

## Implementation Steps

1. Write `workers/tts_worker.py`
   - QThread subclass with 5 signals
   - `run()` method: build jobs → batch synthesis → audio assembly
   - Thread-safe `_on_segment_done` callback
   - Session registry (JSON) for retry state (copy pattern from Sub2Speech)
2. Write `workers/preview_worker.py`
   - QThread subclass with 2 signals
   - `run()`: call synthesize_one, emit path
3. Test both workers with mock signals

---

## Todo List

- [ ] Write tts_worker.py (remove asyncio/option_map, add threading.Lock for callbacks)
- [ ] Write preview_worker.py (simplified, voice only)
- [ ] Manual test: TtsWorker processes 3 segments, emits progress
- [ ] Manual test: PreviewWorker plays audio in UI

---

## Success Criteria

- `progress` signal fires after each segment
- `finished` signal fires with correct output path
- `incomplete` signal lists failed segment indices correctly
- `preview_worker` plays audio within 5 seconds

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Thread contention in `_on_segment_done` | Low | threading.Lock protects shared state |
| Temp preview files not cleaned up | Low | MainWindow._cleanup_active_preview_file (copy from Sub2Speech) |
| Worker continues after window close | Low | Connect QThread.quit to app quit signal |

---

## Next Steps

→ Phase 07: Polish & Packaging
