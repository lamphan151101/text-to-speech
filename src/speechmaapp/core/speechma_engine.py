"""SpeechMa HTTP TTS engine.

API: POST https://speechma.com/com.api/tts-api.php
Payload: {"text": "...", "voice": "voice-314", "pitch": 0, "rate": 0}
Response: audio/mpeg binary

Captcha flow (required for session):
  GET  /com.api/captcha/captcha.php?t={ts}  → JPEG image
  POST /com.api/captcha/captcha.php         → {"code": "12345"} → {"success": true}
  After success the server sets a session cookie used by the TTS endpoint.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests

from speechmaapp.utils.logging_utils import log_error, log_info

_BASE_URL = "https://speechma.com"
_TTS_URL = f"{_BASE_URL}/com.api/tts-api.php"
_CAPTCHA_URL = f"{_BASE_URL}/com.api/captcha/captcha.php"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Origin": _BASE_URL,
    "Referer": f"{_BASE_URL}/",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Module-level session shared across all calls (thread-safe for reads)
_session = requests.Session()
_session.headers.update(_HEADERS)
_session_lock = threading.Lock()

class _RateLimiter:
    """Adaptive token-bucket rate limiter.

    • Starts full (capacity = concurrency) → first N calls fire in parallel.
    • Refills at rate_per_min/60 tokens/sec; sleep() outside lock so threads
      wait concurrently instead of serialising.
    • On 429  → rate × 0.7 (floor 20/min), bucket drained.
    • On success streak → rate × 1.15 every RECOVERY_EVERY calls, capped at
      DEFAULT_RATE so we gradually return to full speed after a backoff.
    """

    _DEFAULT_RATE: float = 50.0     # req/min; evidence: 59 calls @ ~120/min worked
    _MIN_RATE: float = 20.0         # floor after repeated 429s
    _RECOVERY_EVERY: int = 20       # successful calls before stepping rate back up

    def __init__(self, rate_per_min: float | None = None, capacity: int = 2) -> None:
        self._default = (rate_per_min or self._DEFAULT_RATE) / 60.0
        self._rate = self._default
        self._cap = float(capacity)
        self._tokens = self._cap
        self._last = time.monotonic()
        self._ok = 0               # consecutive successes since last backoff
        self._lock = threading.Lock()

    def set_capacity(self, n: int) -> None:
        """Resize burst window to match concurrency; refills the bucket."""
        with self._lock:
            self._cap = float(max(1, n))
            self._tokens = self._cap

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._cap,
                    self._tokens + (now - self._last) * self._rate,
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)  # sleep OUTSIDE lock — threads wait concurrently

    def on_success(self) -> None:
        """Gradually restore rate after a backoff (every RECOVERY_EVERY successes)."""
        with self._lock:
            self._ok += 1
            if self._ok >= self._RECOVERY_EVERY:
                self._ok = 0
                self._rate = min(self._rate * 1.15, self._default)

    def on_429(self) -> None:
        """Back off: −30 % rate, drain bucket, reset success streak."""
        with self._lock:
            self._ok = 0
            self._rate = max(self._rate * 0.7, self._MIN_RATE / 60.0)
            self._tokens = 0.0
            log_error(
                f"RateLimiter throttled to {self._rate * 60:.1f} req/min after 429"
            )


_limiter = _RateLimiter()

# Callback invoked when captcha is needed; set by the UI layer.
# Signature: (image_bytes: bytes) -> str | None  (returns code or None to cancel)
_captcha_callback: Callable[[bytes], str | None] | None = None


def set_captcha_callback(cb: Callable[[bytes], str | None]) -> None:
    global _captcha_callback
    _captcha_callback = cb


def fetch_captcha_image() -> bytes:
    ts = int(time.time() * 1000)
    resp = _session.get(f"{_CAPTCHA_URL}?t={ts}", timeout=15)
    resp.raise_for_status()
    return resp.content


def submit_captcha(code: str) -> bool:
    try:
        resp = _session.post(
            _CAPTCHA_URL,
            data=json.dumps({"code": code.strip()}),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        data = resp.json()
        return bool(data.get("success"))
    except Exception as exc:
        log_error(f"Captcha submit failed: {exc}")
        return False


def ensure_session(max_attempts: int = 3) -> bool:
    """Verify session via a captcha if needed.

    Returns True if session is (or becomes) valid.
    Called from TtsWorker before batch synthesis.
    """
    if _captcha_callback is None:
        log_error("No captcha callback registered — session may be invalid")
        return True  # optimistic: let TTS call reveal the error
    for attempt in range(max_attempts):
        try:
            image = fetch_captcha_image()
        except Exception as exc:
            log_error(f"Fetch captcha image failed attempt={attempt + 1}: {exc}")
            time.sleep(1)
            continue
        code = _captcha_callback(image)
        if code is None:
            log_info("User cancelled captcha")
            return False
        if submit_captcha(code):
            log_info("Captcha validated successfully")
            return True
        log_error(f"Captcha incorrect attempt={attempt + 1}")
    return False


@dataclass
class TtsJob:
    seg_index: int
    text: str
    voice: str
    out_path: str
    pitch: int = 0
    rate: int = 0


def _sanitize(text: str) -> str:
    return (
        text.replace("'", "")
            .replace('"', "")
            .replace("&", "and")
            .strip()
    )


def synthesize_one(
    text: str,
    voice: str,
    out_path: str,
    pitch: int = 0,
    rate: int = 0,
    retries: int = 3,
) -> None:
    sanitized = _sanitize(text)
    if len(sanitized) < 2:
        raise ValueError(f"Text too short after sanitization: {repr(text[:40])}")

    payload = json.dumps({"text": sanitized, "voice": voice, "pitch": pitch, "rate": rate})
    last_exc: BaseException | None = None

    for attempt in range(retries):
        _limiter.acquire()
        try:
            resp = _session.post(
                _TTS_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=90,
            )
            if resp.status_code in (401, 403):
                raise RuntimeError(f"Session expired (HTTP {resp.status_code}) — captcha required")
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 30))
                _limiter.on_429()
                log_error(
                    f"SpeechmaEngine 429 rate-limited voice={voice} attempt={attempt + 1}/{retries} "
                    f"— backing off {retry_after}s"
                )
                if attempt < retries - 1:
                    time.sleep(retry_after)
                    last_exc = RuntimeError(f"HTTP 429 Too Many Requests (Retry-After={retry_after}s)")
                    continue
                else:
                    raise RuntimeError(f"HTTP 429 Too Many Requests after {retries} attempts")
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "")
            if not ct.startswith("audio/"):
                raise RuntimeError(f"Unexpected Content-Type: {ct} — body: {resp.text[:200]}")
            Path(out_path).write_bytes(resp.content)
            _limiter.on_success()
            log_info(
                f"SpeechmaEngine OK url={_TTS_URL} voice={voice} "
                f"size={len(resp.content)} bytes attempt={attempt + 1}"
            )
            return
        except RuntimeError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = 2 ** attempt
                log_error(
                    f"SpeechmaEngine retryable voice={voice} attempt={attempt + 1}/{retries} "
                    f"error={type(exc).__name__}: {exc} — retry in {delay}s"
                )
                time.sleep(delay)
            else:
                log_error(
                    f"SpeechmaEngine giving up voice={voice} attempt={attempt + 1}/{retries} "
                    f"error={type(exc).__name__}: {exc}"
                )

    raise RuntimeError(f"Failed to synthesize after {retries} attempts: {last_exc}") from last_exc


def synthesize_batch(
    jobs: list[TtsJob],
    concurrency: int,
    on_done: Callable[[TtsJob, bool, BaseException | None], None],
    retries: int = 5,
) -> None:
    if not jobs:
        return
    concurrency = max(1, min(concurrency, 4))
    _limiter.set_capacity(concurrency)  # burst window = concurrency threads
    log_info(f"Batch synth start jobs={len(jobs)} concurrency={concurrency}")

    def _run_one(job: TtsJob) -> tuple[TtsJob, bool, BaseException | None]:
        try:
            synthesize_one(
                text=job.text,
                voice=job.voice,
                out_path=job.out_path,
                pitch=job.pitch,
                rate=job.rate,
                retries=retries,
            )
            return job, True, None
        except BaseException as exc:  # noqa: BLE001
            return job, False, exc

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_run_one, job): job for job in jobs}
        for future in as_completed(futures):
            job, ok, exc = future.result()
            try:
                on_done(job, ok, exc)
            except Exception as cb_exc:
                log_error(f"on_done callback failed segment={job.seg_index}: {cb_exc}")

    log_info("Batch synth complete")
