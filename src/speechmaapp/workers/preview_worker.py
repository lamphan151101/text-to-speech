import uuid
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from speechmaapp.config import AppConfig
from speechmaapp.core.speechma_engine import synthesize_one
from speechmaapp.utils.logging_utils import log_error, log_info


class PreviewWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, config: AppConfig, text: str, voice: str, pitch: int = 0, rate: int = 0) -> None:
        super().__init__()
        self.config = config
        self.text = text[:300]
        self.voice = voice
        self.pitch = pitch
        self.rate = rate

    def run(self) -> None:
        out = str(Path(self.config.temp_dir) / f"preview_{uuid.uuid4().hex[:8]}.mp3")
        try:
            log_info(f"Preview start voice={self.voice}")
            synthesize_one(self.text, self.voice, out, pitch=self.pitch, rate=self.rate, retries=2)
            self.finished.emit(out)
        except Exception as exc:
            log_error(f"Preview failed: {exc}")
            self.error.emit(str(exc))
