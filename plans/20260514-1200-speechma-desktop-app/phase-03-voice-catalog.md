# Phase 03 — Voice Catalog

**Context**: [Parent Plan](plan.md) | Depends on [Phase 02](phase-02-speechma-engine.md)  
**Date**: 2026-05-14  
**Priority**: High  
**Status**: TODO | **Review**: Pending

---

## Overview

Build a voice catalog for speechma.com voices. Unlike edge-tts (which provides a list API), speechma.com has no public voice list endpoint. We must bundle a known voice list and provide a mechanism to refresh it.

---

## Key Insights

- speechma.com has **583 voices** hardcoded in `script.js?v=...` (confirmed)
- Voice IDs format: `voice-1` to `voice-349+`
- **Vietnamese voices confirmed**: `voice-314` (HoaiMy, Female), `voice-315` (NamMinh, Male)
- **COMPLETED**: `config/voices.json` already extracted (583 voices, saved 2026-05-14)
- Voice list source: `https://speechma.com/script.js?v=1777481668` — `this.voices = [...]` array
- **API also supports `pitch` and `rate` params** (discovered from `makeApiRequest` function)

### PHASE 3 STATUS: COMPLETE ✅
Voice list already saved to `d:\project\speeachMaProject\config\voices.json`

---

## Requirements

- Voices grouped by language (same as Sub2Speech UX pattern)
- Each voice has: `voice_id` (e.g., `voice-35`), `name`, `language`, `gender`
- Bundled `voices.json` in `config/` directory
- Cache refreshable (TTL: 7 days)

---

## Architecture

### `voices.json` structure
```json
{
  "voices": [
    {
      "id": "voice-35",
      "name": "Sonia",
      "language": "English",
      "locale": "en-GB",
      "gender": "Female"
    },
    {
      "id": "voice-1",
      "name": "Aria",
      "language": "English",
      "locale": "en-US",
      "gender": "Female"
    }
  ],
  "timestamp": 1747234800
}
```

### `voices_catalog.py` module
```python
@dataclass
class VoiceInfo:
    voice_id: str       # "voice-35"
    name: str           # "Sonia"
    language: str       # "English (UK)"
    locale: str         # "en-GB"
    gender: str         # "Female"

LANGUAGE_GROUPS = [
    "Tiếng Việt", "English (US)", "English (UK)",
    "Tiếng Nhật", "Tiếng Trung", "Tiếng Hàn",
    "Tiếng Pháp", "Tiếng Tây Ban Nha", "Tiếng Đức",
    "Khác"  # catch-all
]

def get_grouped_voices(voices_path: Path) -> dict[str, list[VoiceInfo]]:
    """Load voices.json and group by language."""
    voices = _load_voices(voices_path)
    return _group_voices(voices)

def _load_voices(voices_path: Path) -> list[VoiceInfo]:
    """Load from bundled file; fallback to hardcoded minimal list."""
    if voices_path.exists():
        raw = json.loads(voices_path.read_text(encoding="utf-8"))
        return [VoiceInfo(**v) for v in raw.get("voices", [])]
    return _fallback_voices()

def _fallback_voices() -> list[VoiceInfo]:
    """Minimal hardcoded voice list for offline launch."""
    return [
        VoiceInfo("voice-35", "Sonia", "English (UK)", "en-GB", "Female"),
        VoiceInfo("voice-30", "Maisie", "English (UK)", "en-GB", "Female"),
        VoiceInfo("voice-25", "Bella", "English (UK)", "en-GB", "Female"),
        # Add Vietnamese voices once IDs are discovered
    ]
```

### Voice ID Discovery Script (standalone)
Create `tools/discover_voices.py` — a one-time script to probe voice IDs:
```python
# Run once to build voices.json
# Tests voice-1 to voice-600, saves valid IDs
# Usage: python tools/discover_voices.py
for i in range(1, 601):
    voice_id = f"voice-{i}"
    try:
        synthesize_one("Test", voice_id, f"test_{i}.mp3")
        valid_voices.append(voice_id)
    except:
        pass
```

### AppConfig change
In `config.py`, `voices_cache_path` should point to bundled `config/voices.json`:
```python
self.voices_path = self.config_dir / "voices.json"
# On first run, copy from bundled_voices to config_dir if not exists
```

---

## Related Code Files

- `D:\project\Sub2Speech\src\sub2speech\core\voices_catalog.py` — original (adapted)
- `D:\project\Sub2Speech\src\sub2speech\config.py` — voices_cache_path pattern

---

## Implementation Steps

1. **Discover voices**: Before coding, use Chrome DevTools on speechma.com to find:
   - The endpoint that loads the voice dropdown
   - The format of voice IDs
   - Names, languages, genders for each voice
2. Create `config/voices.json` with discovered voices
3. Create `src/speechmaapp/core/voices_catalog.py`
   - `VoiceInfo` dataclass
   - `get_grouped_voices(path)` function
   - `_fallback_voices()` with hardcoded minimal list
4. Create `tools/discover_voices.py` for future voice refreshing
5. Wire into `AppConfig`

---

## Todo List

- [ ] Open speechma.com in DevTools, find voice list endpoint/data
- [ ] Export complete voice list as JSON
- [ ] Manually curate `config/voices.json` with 50+ key voices at minimum
- [ ] Create `voices_catalog.py` with `VoiceInfo` and `get_grouped_voices()`
- [ ] Add fallback minimal voice list (7 known English UK voices)
- [ ] Create `tools/discover_voices.py` for ID scanning
- [ ] Test: `get_grouped_voices()` returns non-empty dict

---

## Success Criteria

- Voice dropdown in UI shows at least 20 voices grouped by language
- Vietnamese voices available (critical for target users)
- Fallback voices load if `voices.json` missing/corrupt

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| No Vietnamese voices exist on speechma.com | Low | Check site; fallback to edge-tts for VI if needed |
| Voice IDs change after site update | Medium | Log the error, prompt user to refresh voice list |
| Discovery script banned by rate limits | Medium | Add 1s delay between probes |

---

## Security Considerations

- Discovery script should run slowly (1s delay) to avoid DoS-like behavior
- Bundle voices.json so offline use is possible (no network needed for UI)

---

## Next Steps

→ Phase 04: SRT/TXT Processing Pipeline
