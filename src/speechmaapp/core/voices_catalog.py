from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ALL_LANGUAGES = "__all__"

# Language groups shown in UI dropdown (language field from voices.json)
LANGUAGE_GROUPS: list[str] = [
    "Vietnamese",
    "English",
    "Multilingual",
    "Chinese",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Spanish",
    "Arabic",
    "Russian",
    "Other",
]

# Map from voices.json language → display group key
_LANG_MAP: dict[str, str] = {
    "Vietnamese": "Vietnamese",
    "English": "English",
    "Multilingual": "Multilingual",
    "Chinese": "Chinese",
    "Japanese": "Japanese",
    "Korean": "Korean",
    "French": "French",
    "German": "German",
    "Spanish": "Spanish",
    "Arabic": "Arabic",
    "Russian": "Russian",
}


@dataclass
class VoiceInfo:
    voice_id: str    # "voice-314"
    name: str        # "HoaiMy"
    language: str    # "Vietnamese"
    country: str     # "Vietnam"
    gender: str      # "Female"

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.country})"


def _fallback_voices() -> list[VoiceInfo]:
    return [
        VoiceInfo("voice-314", "HoaiMy", "Vietnamese", "Vietnam", "Female"),
        VoiceInfo("voice-315", "NamMinh", "Vietnamese", "Vietnam", "Male"),
        VoiceInfo("voice-109", "Aria", "English", "United States", "Female"),
        VoiceInfo("voice-119", "Jenny", "English", "United States", "Female"),
        VoiceInfo("voice-108", "Andrew", "English", "United States", "Male"),
        VoiceInfo("voice-85", "Sonia", "English", "United Kingdom", "Female"),
        VoiceInfo("voice-84", "Ryan", "English", "United Kingdom", "Male"),
        VoiceInfo("voice-107", "Andrew Multilingual", "Multilingual", "United States", "Male"),
        VoiceInfo("voice-110", "Ava Multilingual", "Multilingual", "United States", "Female"),
    ]


def _load_voices(voices_path: Path) -> list[VoiceInfo]:
    if not voices_path.exists():
        return _fallback_voices()
    try:
        raw = json.loads(voices_path.read_text(encoding="utf-8-sig"))
        voices_raw = raw.get("voices", raw) if isinstance(raw, dict) else raw
        result: list[VoiceInfo] = []
        for v in voices_raw:
            result.append(
                VoiceInfo(
                    voice_id=v.get("id", ""),
                    name=v.get("name", ""),
                    language=v.get("language", "Other"),
                    country=v.get("country", ""),
                    gender=v.get("gender", ""),
                )
            )
        return result if result else _fallback_voices()
    except Exception:
        return _fallback_voices()


def get_grouped_voices(voices_path: Path) -> dict[str, list[VoiceInfo]]:
    voices = _load_voices(voices_path)
    grouped: dict[str, list[VoiceInfo]] = {g: [] for g in LANGUAGE_GROUPS}
    for v in voices:
        group = _LANG_MAP.get(v.language, "Other")
        grouped.setdefault(group, []).append(v)
    # sort each group by country then name
    for group in grouped:
        grouped[group].sort(key=lambda x: (x.country, x.name))
    # remove empty groups, then prepend ALL_LANGUAGES entry
    result = {k: v for k, v in grouped.items() if v}
    all_voices = sorted(voices, key=lambda x: (x.language, x.country, x.name))
    return {ALL_LANGUAGES: all_voices, **result}
