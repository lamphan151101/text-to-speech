import hashlib
import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from speechmaapp.config import AppConfig
from speechmaapp.core.audio_processor import (
    build_timeline_audio,
    build_timeline_audio_fast,
    concatenate_audio_files_to_mp3,
    export_single_mp3,
)
from speechmaapp.core.speechma_engine import TtsJob, configure_proxy_failover, synthesize_batch
from speechmaapp.models.subtitle import Segment
from speechmaapp.utils.logging_utils import log_error, log_info


class TtsWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)
    incomplete = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        source_name: str,
        source_file_name: str,
        source_md5: str,
        segments: list[Segment],
        segment_voice_map: dict[int, str],
        segment_pitch_map: dict[int, int],
        segment_rate_map: dict[int, int],
        output_path: str,
        save_original: bool,
        retry_only_indices: list[int] | None = None,
        is_text_input: bool = False,
    ) -> None:
        super().__init__()
        self.config = config
        self.source_name = source_name
        self.source_file_name = source_file_name
        self.source_md5 = source_md5
        self.segments = segments
        self.segment_voice_map = segment_voice_map
        self.segment_pitch_map = segment_pitch_map
        self.segment_rate_map = segment_rate_map
        self.output_path = output_path
        self.save_original = save_original
        self.retry_only_indices = retry_only_indices or []
        self.is_text_input = is_text_input

    def run(self) -> None:
        try:
            export_started = time.perf_counter()
            log_info(
                f"Export start source={self.source_name} md5={self.source_md5} "
                f"segments={len(self.segments)} output={self.output_path}"
            )
            sessions_root = Path(self.config.temp_dir) / "export_sessions"
            session_key = f"{self.source_name}_{self.source_md5}"
            session_dir = sessions_root / session_key
            session_dir.mkdir(parents=True, exist_ok=True)
            self._update_registry(sessions_root, session_key, "running", session_dir)

            cache_dir = Path(self.config.temp_dir) / "tts_cache"
            self._restore_segment_cache(session_dir, cache_dir)
            targets = self._collect_targets(session_dir)
            cached_count = len(self.segments) - len(targets)
            total = max(len(self.segments), 1)
            # Pre-credit already-synthesized segments so progress bar is accurate
            processed_count = cached_count
            if cached_count:
                log_info(f"Cache-aware: skipping {cached_count} already-synthesized segments")
                self.progress.emit(int((processed_count / total) * 80))
            failed_segments: list[int] = []
            _lock = threading.Lock()

            original_dir = Path(self.config.audio_root) / self.source_name
            if self.save_original:
                original_dir.mkdir(parents=True, exist_ok=True)

            jobs: list[TtsJob] = []
            for seg in targets:
                voice = self.segment_voice_map.get(seg.index, "")
                if not voice:
                    with _lock:
                        failed_segments.append(seg.index)
                        processed_count += 1
                    self.progress.emit(int((processed_count / total) * 80))
                    log_error(f"Skip segment={seg.index} reason=no_voice")
                    continue
                jobs.append(
                    TtsJob(
                        seg_index=seg.index,
                        text=seg.text,
                        voice=voice,
                        out_path=str(session_dir / f"segment_{seg.index:04d}.mp3"),
                        pitch=self.segment_pitch_map.get(seg.index, 0),
                        rate=self.segment_rate_map.get(seg.index, 0),
                    )
                )

            def _on_done(job: TtsJob, ok: bool, exc: BaseException | None) -> None:
                nonlocal processed_count
                with _lock:
                    if ok:
                        self._save_segment_cache(job, cache_dir)
                        if self.save_original:
                            shutil.copy2(job.out_path, str(original_dir / Path(job.out_path).name))
                    else:
                        failed_segments.append(job.seg_index)
                        log_error(f"Segment synth failed segment={job.seg_index}: {exc}")
                    processed_count += 1
                self.progress.emit(int((processed_count / total) * 80))

            if jobs:
                settings = self.config.load_settings()
                configure_proxy_failover(settings)
                concurrency = 1
                log_info(f"Start synth batch jobs={len(jobs)} concurrency={concurrency}")
                synth_started = time.perf_counter()
                synthesize_batch(jobs=jobs, concurrency=concurrency, on_done=_on_done)
                log_info(f"Synth batch elapsed={time.perf_counter() - synth_started:.2f}s")
            else:
                log_info("No synth jobs queued")

            if failed_segments:
                failed_sorted = sorted(set(failed_segments))
                log_error(f"Synthesis incomplete failed_segments={failed_sorted}")
                self._update_registry(sessions_root, session_key, "incomplete", session_dir, failed_sorted)
                self.incomplete.emit(failed_sorted)
                return

            raw_paths = self._collect_all_segment_paths(session_dir)
            render_started = time.perf_counter()
            self.progress.emit(85)
            if len(self.segments) == 1:
                log_info("Single segment export mode")
                export_single_mp3(raw_paths[0], self.output_path)
            elif self.is_text_input:
                log_info("TXT sequential export mode")
                concatenate_audio_files_to_mp3(raw_paths, self.output_path)
            else:
                log_info("Timeline export mode")
                try:
                    build_timeline_audio_fast(self.segments, raw_paths, self.output_path)
                except Exception as exc:
                    log_error(f"Fast timeline export failed, falling back to legacy path: {exc}")
                    build_timeline_audio(self.segments, raw_paths, self.output_path, session_dir)
            log_info(f"Audio render elapsed={time.perf_counter() - render_started:.2f}s")

            self.progress.emit(100)
            log_info(f"Export completed output={self.output_path} elapsed={time.perf_counter() - export_started:.2f}s")
            self._update_registry(sessions_root, session_key, "completed", session_dir, [])
            shutil.rmtree(session_dir, ignore_errors=True)
            self.finished.emit(self.output_path)

        except Exception as exc:
            log_error(f"Export failed: {exc}")
            self.error.emit(str(exc))

    def _collect_targets(self, session_dir: Path | None = None) -> list[Segment]:
        if self.retry_only_indices:
            retry_set = set(self.retry_only_indices)
            return [seg for seg in self.segments if seg.index in retry_set]
        if session_dir is not None:
            # Skip segments whose MP3 is already synthesized and non-empty
            return [
                seg for seg in self.segments
                if not (p := session_dir / f"segment_{seg.index:04d}.mp3").is_file()
                or p.stat().st_size < 512
            ]
        return list(self.segments)

    def _collect_all_segment_paths(self, session_dir: Path) -> list[str]:
        paths: list[str] = []
        missing: list[int] = []
        for seg in self.segments:
            file_path = session_dir / f"segment_{seg.index:04d}.mp3"
            if not file_path.exists():
                missing.append(seg.index)
            paths.append(str(file_path))
        if missing:
            raise RuntimeError(
                f"Thiếu file segment trung gian: {', '.join(str(i) for i in missing)}. "
                "Hãy bấm Xuất MP3 để tạo lại các segment lỗi."
            )
        return paths

    def _restore_segment_cache(self, session_dir: Path, cache_dir: Path) -> None:
        restored = 0
        cache_dir.mkdir(parents=True, exist_ok=True)
        for seg in self.segments:
            out_path = session_dir / f"segment_{seg.index:04d}.mp3"
            if out_path.is_file() and out_path.stat().st_size >= 512:
                continue
            cache_path = self._cache_path_for_segment(seg, cache_dir)
            if cache_path is None or not cache_path.is_file() or cache_path.stat().st_size < 512:
                continue
            shutil.copy2(cache_path, out_path)
            restored += 1
        if restored:
            log_info(f"Restored cached TTS segments count={restored}")

    def _save_segment_cache(self, job: TtsJob, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path_for_values(
            text=job.text,
            voice=job.voice,
            pitch=job.pitch,
            rate=job.rate,
            cache_dir=cache_dir,
        )
        try:
            shutil.copy2(job.out_path, cache_path)
        except Exception as exc:
            log_error(f"Save segment cache failed segment={job.seg_index}: {exc}")

    def _cache_path_for_segment(self, seg: Segment, cache_dir: Path) -> Path | None:
        voice = self.segment_voice_map.get(seg.index, "")
        if not voice:
            return None
        return self._cache_path_for_values(
            text=seg.text,
            voice=voice,
            pitch=self.segment_pitch_map.get(seg.index, 0),
            rate=self.segment_rate_map.get(seg.index, 0),
            cache_dir=cache_dir,
        )

    def _cache_path_for_values(
        self,
        text: str,
        voice: str,
        pitch: int,
        rate: int,
        cache_dir: Path,
    ) -> Path:
        payload = json.dumps(
            {"text": text, "voice": voice, "pitch": pitch, "rate": rate},
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return cache_dir / f"{digest}.mp3"

    def _update_registry(
        self,
        sessions_root: Path,
        session_key: str,
        status: str,
        session_dir: Path,
        failed_segments: list[int] | None = None,
    ) -> None:
        registry_path = sessions_root / "sessions_index.json"
        sessions_root.mkdir(parents=True, exist_ok=True)
        try:
            raw = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        except Exception:
            raw = {}
        raw[session_key] = {
            "source_file_name": self.source_file_name,
            "source_name": self.source_name,
            "source_md5": self.source_md5,
            "session_dir": str(session_dir),
            "status": status,
            "failed_segments": failed_segments or [],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        registry_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
