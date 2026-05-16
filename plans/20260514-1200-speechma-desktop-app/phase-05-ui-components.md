# Phase 05 — UI Components

**Context**: [Parent Plan](plan.md) | Depends on [Phase 03](phase-03-voice-catalog.md), [Phase 04](phase-04-srt-pipeline.md)  
**Date**: 2026-05-14  
**Priority**: High  
**Status**: TODO | **Review**: Pending

---

## Overview

Build the desktop GUI, adapting Sub2Speech's proven UI layout. The main difference is simplification: no rate/volume/pitch sliders (speechma.com API doesn't expose these), and voice data comes from our speechma voice catalog instead of edge-tts.

---

## Key Insights

- Sub2Speech's UI is clean and well-structured — copy 80% of it
- Key simplification: `SpeakerManager` drops rate/volume/pitch inputs (3 input fields removed)
- Voice catalog replaces edge-tts grouped voices — API format is compatible
- `SubtitleTable`, `OutputPanel`, `AnimatedProgressBar`, `theme.py` copy verbatim
- `MainWindow` adapts to use `speechma_engine` instead of `edge_tts_engine`
- Remove `auto_emotion` checkbox from speaker manager
- Window title: "SpeechMa" instead of "Sub2Speech"

---

## Requirements

- Top bar: Open file button, status label, language toggle (VI/EN), help button
- Left panel: Subtitle/content table with preview button
- Right panel: Voice selector (language group → voice combo), speaker management (SRT mode), speaker list table
- Bottom: Output directory, export button, media player, progress bar

---

## Architecture

### Layout (same as Sub2Speech)
```
┌─────────────────────────────────────────────────┐
│ [Mở file...] [status]          [VI/EN] [Trợ giúp]│
├────────────────────────┬────────────────────────┤
│ Nội dung               │ Chọn giọng đọc          │
│ [Nghe thử dòng đã chọn]│ ┌─Thiết lập giọng──────┐│
│ ┌─────────────────────┐│ │ Ngôn ngữ: [────────] ││
│ │ #│Thời gian│ Nội dung│ │ Giọng:    [────────] ││
│ │  │         │ Speaker ││ │ [Preview] [Thêm]     ││
│ │  │         │         ││ └───────────────────────┘│
│ └─────────────────────┘│ ┌─Danh sách người nói───┐│
│                        │ │ [Xóa]                  ││
│                        │ │ Name│Range│Lang│Voice  ││
│                        │ └────────────────────────┘│
├────────────────────────┴────────────────────────┤
│ Thư mục: [__________] [Chọn...] □Lưu gốc [Xuất] │
│ [Phát] [Dừng] [────────────────────] 00:00/00:00 │
│ [████████████░░░░░░] (progress bar)               │
└─────────────────────────────────────────────────┘
```

### Files to copy verbatim
- `ui/subtitle_table.py` — no changes
- `ui/output_panel.py` — no changes
- `ui/animated_progress.py` — no changes
- `ui/theme.py` — no changes (keep same dark theme)
- `utils/subprocess_utils.py` — no changes

### `ui/speaker_manager.py` — adapted
```python
# REMOVED: rate_input, volume_input, pitch_input
# REMOVED: auto_emotion_checkbox
# REMOVED: voice_options_widget
# SIMPLIFIED top_form:
self.top_form.addRow(self.name_label, self.name_input)
self.top_form.addRow(self.range_label, self.range_input)
self.top_form.addRow(self.language_label, self.language_combo)
self.top_form.addRow(self.voice_label, self.voice_combo)
# (no more options row)
```

### `ui/main_window.py` — adapted
```python
# CHANGED: window title → "SpeechMa"
# CHANGED: get_grouped_voices() uses speechma VoiceInfo (voice_id not short_name)
# CHANGED: build_segment_voice_map returns {"voice_id": "voice-35"}
# REMOVED: option_map, emotion_info_label
# REMOVED: _build_segment_voice_options_map
# CHANGED: TtsWorker call — no option_map arg
# CHANGED: PreviewWorker call — no rate/vol/pitch args
```

Voice map adaptation:
```python
# Sub2Speech:
voice_combo.addItem(f"{voice.display_name} ({voice.gender})", voice.short_name)
# SpeechMa:
voice_combo.addItem(f"{voice.name} ({voice.gender})", voice.voice_id)
```

### `utils/i18n.py` — adapted
Update all translation strings. Keep VI/EN bilingual support.
Key new strings:
```python
# VI
"top.open_file": "Mở file...",
"status.no_file": "Chưa mở file",
"section.voice": "Chọn giọng",
"section.voice_setup": "Thiết lập giọng",
"section.speaker_list": "Danh sách người nói",
"speaker.preview_sample_text": "Xin chào, đây là giọng đọc thử nghiệm.",
# Note: remove rate/vol/pitch translation keys
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\ui\main_window.py` — template
- `D:\project\Sub2Speech\src\sub2speech\ui\speaker_manager.py` — template
- `D:\project\Sub2Speech\src\sub2speech\utils\i18n.py` — template

---

## Implementation Steps

1. Copy `subtitle_table.py`, `output_panel.py`, `animated_progress.py`, `theme.py` verbatim
2. Copy `utils/subprocess_utils.py` verbatim
3. Write `utils/i18n.py` — adapt translations, remove rate/pitch/vol keys
4. Write `ui/speaker_manager.py` — remove rate/vol/pitch/auto_emotion widgets
5. Write `ui/main_window.py` — adapt voice loading, remove option_map, update worker calls
6. Write `app.py` — mirror Sub2Speech entry point
7. Run app, verify UI renders correctly
8. Test open SRT, assign voices, preview, export

---

## Todo List

- [ ] Copy subtitle_table.py (no changes)
- [ ] Copy output_panel.py (no changes)
- [ ] Copy animated_progress.py (no changes)
- [ ] Copy theme.py (no changes)
- [ ] Copy subprocess_utils.py (no changes)
- [ ] Write i18n.py (remove rate/pitch/vol keys, keep rest)
- [ ] Write speaker_manager.py (simplified — no rate/vol/pitch)
- [ ] Write main_window.py (adapted — no option_map, speechma voices)
- [ ] Write app.py (mirror Sub2Speech)
- [ ] Run app and verify UI renders
- [ ] End-to-end test with SRT file

---

## Success Criteria

- App launches without errors
- Voice list populated in dropdown
- SRT file opens and segments shown in table
- Preview button plays audio
- Export button generates MP3

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PySide6 version mismatch on user machine | Low | Pin PySide6>=6.7 in requirements.txt |
| UI hangs during export (blocking main thread) | None | Workers already in QThread |
| Voice list empty (voices.json missing) | Low | Fallback voices hardcoded in catalog |

---

## Next Steps

→ Phase 06: Background Workers (already largely designed in Phase 04)
