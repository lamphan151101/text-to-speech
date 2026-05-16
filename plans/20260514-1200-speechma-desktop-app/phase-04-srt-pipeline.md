# Phase 04 — SRT/TXT Processing Pipeline

**Context**: [Parent Plan](plan.md) | Depends on [Phase 02](phase-02-speechma-engine.md)  
**Date**: 2026-05-14  
**Priority**: High  
**Status**: TODO | **Review**: Pending

---

## Overview

Adapt the SRT/TXT parsing + audio assembly pipeline from Sub2Speech. The pipeline is mostly unchanged; the only difference is the TTS engine call.

---

## Key Insights

- Sub2Speech's `subtitle_parser.py`, `audio_processor.py`, `models/subtitle.py`, `models/speaker.py` can be **copied almost verbatim**
- The `TtsWorker` needs adaptation: remove `asyncio.run()`, replace `synthesize_batch` with the new thread-pool version
- Remove all references to `rate`, `volume`, `pitch`, `auto_emotion` from the processing pipeline (speechma.com API doesn't support these)
- Text normalization (`text_normalizer.py`) and emotion analysis (`emotion_analyzer.py`) from Sub2Speech are NOT needed — remove them
- Speaker assignment (`speaker_assignment.py`) can be copied unchanged

### SRT Workflow (unchanged from Sub2Speech)
1. Parse `.srt` → `list[Segment]` with `index`, `start`, `end`, `text`, `speaker`
2. User assigns voice to each speaker (via UI)
3. For each segment: call `synthesize_one(text, voice_id, out_path)` → MP3 file
4. `build_timeline_audio()` assembles segments with correct timing using ffmpeg

### TXT Workflow (unchanged from Sub2Speech)
1. Parse `.txt` → split into 500-word chunks → `list[Segment]`
2. User selects one voice for all
3. `synthesize_one()` for each chunk
4. `concatenate_audio_files_to_mp3()` joins chunks sequentially

### Text Chunking for speechma.com
Each SRT segment is typically < 200 chars. No chunking needed for SRT mode.
For TXT mode, Sub2Speech pre-chunks at 500 words (~2500 chars). Need to add a post-processing split at 1000 chars if a chunk exceeds the limit.

---

## Requirements

- SRT parsing: extract index, timestamps, text, optional speaker tag
- TXT parsing: split into ~500 word chunks
- Audio assembly: timeline (SRT) and sequential (TXT) modes
- Each segment saved as `segment_XXXX.mp3` in session dir
- Failed segments tracked; retry on next export

---

## Architecture

### Files to copy from Sub2Speech (no changes needed)
```
subtitle_parser.py     → copy verbatim
audio_processor.py     → copy verbatim
models/subtitle.py     → copy verbatim
models/speaker.py      → copy verbatim (remove `auto_emotion` field)
core/speaker_assignment.py → copy verbatim
```

### Files to adapt
**`models/speaker.py`** — remove `auto_emotion` field:
```python
@dataclass
class Speaker:
    name: str
    segments: set[int] = field(default_factory=set)
    voice: str = ""           # "voice-35"
    language_group: str = ""
    # REMOVED: rate, volume, pitch, auto_emotion (not supported by speechma.com)
```

**`workers/tts_worker.py`** — main changes:
```python
# REMOVED: asyncio.run()
# REPLACED: synthesize_batch now uses ThreadPoolExecutor (sync)
# REMOVED: option_map (no rate/pitch/vol)
# REMOVED: auto_emotion logic
# REMOVED: normalize() / text_normalizer calls

class TtsWorker(QThread):
    def run(self) -> None:
        jobs = self._build_jobs()
        synthesize_batch(jobs, concurrency=2, on_done=self._on_segment_done)
        # then assemble audio...

    def _build_jobs(self) -> list[TtsJob]:
        return [
            TtsJob(
                seg_index=seg.index,
                text=seg.text,
                voice=self.segment_voice_map.get(seg.index, ""),
                out_path=str(session_dir / f"segment_{seg.index:04d}.mp3"),
            )
            for seg in targets
            if self.segment_voice_map.get(seg.index)
        ]
```

**`workers/preview_worker.py`** — simplify:
```python
class PreviewWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, config, text, voice):
        # No rate/pitch/vol params
        ...

    def run(self):
        out = str(Path(self.config.temp_dir) / f"preview_{uuid4().hex[:8]}.mp3")
        try:
            synthesize_one(self.text[:200], self.voice, out)
            self.finished.emit(out)
        except Exception as exc:
            self.error.emit(str(exc))
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\core\subtitle_parser.py`
- `D:\project\Sub2Speech\src\sub2speech\core\audio_processor.py`
- `D:\project\Sub2Speech\src\sub2speech\models\subtitle.py`
- `D:\project\Sub2Speech\src\sub2speech\models\speaker.py`
- `D:\project\Sub2Speech\src\sub2speech\workers\tts_worker.py`
- `D:\project\Sub2Speech\src\sub2speech\workers\preview_worker.py`

---

## Implementation Steps

1. Copy `subtitle_parser.py` to `src/speechmaapp/core/`
2. Copy `audio_processor.py` to `src/speechmaapp/core/`
3. Copy `speaker_assignment.py` to `src/speechmaapp/core/`
4. Copy `models/subtitle.py` unchanged
5. Copy `models/speaker.py`, remove `auto_emotion`, `rate`, `volume`, `pitch` fields
6. Adapt `workers/tts_worker.py`:
   - Remove asyncio, auto_emotion, option_map
   - Use new `synthesize_batch` from `speechma_engine`
7. Adapt `workers/preview_worker.py`:
   - Remove rate/pitch/vol params
   - Call `synthesize_one` directly
8. Test SRT pipeline end-to-end with a 3-segment test file

---

## Todo List

- [ ] Copy subtitle_parser.py (no changes)
- [ ] Copy audio_processor.py (no changes)
- [ ] Copy speaker_assignment.py (no changes)
- [ ] Copy subtitle.py model (no changes)
- [ ] Adapt speaker.py (remove rate/vol/pitch/auto_emotion)
- [ ] Write tts_worker.py (no asyncio, uses synthesize_batch)
- [ ] Write preview_worker.py (simplified, no voice params)
- [ ] Manual test: SRT file → audio output
- [ ] Manual test: TXT file → audio output

---

## Success Criteria

- 3-segment SRT file generates correctly timed MP3
- TXT file generates sequential MP3
- Failed segments tracked and retry works
- Preview worker plays a short audio clip

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| speechma.com returns non-MP3 for some voices | Low | Check Content-Type; handle gracefully |
| Large SRT (200+ segments) takes too long | Medium | Progress bar + concurrency=2; add cancel button |
| Audio assembly breaks with silence segments | Low | Copy from Sub2Speech which handles this |

---

## Next Steps

→ Phase 05: UI Components
