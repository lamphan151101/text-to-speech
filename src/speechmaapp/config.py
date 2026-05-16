import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    output_dir: str
    save_original_audio: bool
    last_language_group: str
    language: str
    tts_concurrency: int


class AppConfig:
    def __init__(self, app_root: Path) -> None:
        self.app_root = app_root
        self.config_dir = app_root / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.config_dir / "settings.json"
        self.audio_root = app_root / "Audio"
        self.audio_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = app_root / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        # voices.json bundled alongside config/
        self.voices_path = self.config_dir / "voices.json"
        # copy bundled voices.json if not already present
        self._ensure_voices()

    def _ensure_voices(self) -> None:
        if self.voices_path.exists():
            return
        # look for bundled voices.json next to exe / in source tree
        candidates = [
            self.app_root / "config" / "voices.json",
            Path(__file__).resolve().parents[3] / "config" / "voices.json",
        ]
        for c in candidates:
            if c.exists() and c != self.voices_path:
                import shutil
                shutil.copy2(str(c), str(self.voices_path))
                return

    def load_settings(self) -> Settings:
        default = Settings(
            output_dir=str(self.audio_root.resolve()),
            save_original_audio=False,
            last_language_group="Vietnamese",
            language="vi",
            tts_concurrency=2,
        )
        if not self.settings_path.exists():
            return default
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return Settings(
                output_dir=raw.get("output_dir", default.output_dir),
                save_original_audio=bool(raw.get("save_original_audio", default.save_original_audio)),
                last_language_group=raw.get("last_language_group", default.last_language_group),
                language=raw.get("language", default.language),
                tts_concurrency=self._clamp(raw.get("tts_concurrency", default.tts_concurrency)),
            )
        except (OSError, json.JSONDecodeError):
            return default

    def save_settings(self, settings: Settings) -> None:
        payload = {
            "output_dir": settings.output_dir,
            "save_original_audio": settings.save_original_audio,
            "last_language_group": settings.last_language_group,
            "language": settings.language,
            "tts_concurrency": self._clamp(settings.tts_concurrency),
        }
        self.settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _clamp(value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 2
        return max(1, min(parsed, 4))
