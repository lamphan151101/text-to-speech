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
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import requests
from requests.adapters import HTTPAdapter

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

# Module-level session shared across all calls.
# _session_lock guards resets; individual requests read _session without locking
# (Python GIL makes attribute reads atomic in CPython).
_session = requests.Session()
_session.headers.update(_HEADERS)
_session.mount("https://", HTTPAdapter(pool_connections=16, pool_maxsize=16))
_session_lock = threading.Lock()
_last_session_reset_at: float = 0.0  # monotonic timestamp of last reset


def _try_session_reset() -> None:
    """Create a fresh HTTP session to recover from session-level rate limiting.

    Replaces the global session (new object = no cookies) so the next TTS
    request arrives without a tracked session ID, effectively resetting the
    server-side rate-limit counter for this client.  If the server then returns
    401/403 (captcha needed), synthesize_one() will surface that as a normal
    error and the user can click the Captcha button to re-authenticate.

    Debounced to once per 10 s so concurrent threads don't each create a new
    session in the same 429 wave.
    """
    global _session, _last_session_reset_at
    with _session_lock:
        now = time.monotonic()
        if now - _last_session_reset_at < 10.0:
            log_info("Session reset skipped — already reset within 10 s")
            return
        _last_session_reset_at = now
        new_session = requests.Session()
        new_session.headers.update(_HEADERS)
        new_session.mount("https://", HTTPAdapter(pool_connections=16, pool_maxsize=16))
        _session = new_session
    log_info("Session reset: new HTTP session created (cookies cleared) for rate-limit recovery")


class _RateLimiter:
    """Adaptive token-bucket rate limiter.

    • Starts full (capacity = concurrency) → first N calls fire in parallel.
    • Refills at rate_per_min/60 tokens/sec; sleep() outside lock so threads
      wait concurrently instead of serialising.
    • On 429  → rate × 0.7 (floor 20/min), bucket drained.
    • On success streak → rate × 1.15 every RECOVERY_EVERY calls, capped at
      DEFAULT_RATE so we gradually return to full speed after a backoff.
    """

    _DEFAULT_RATE: float = 24.0
    _MAX_RATE: float = 36.0
    _MIN_RATE: float = 6.0
    _RECOVERY_EVERY: int = 30

    def __init__(self, rate_per_min: float | None = None, capacity: int = 2) -> None:
        self._default = (rate_per_min or self._DEFAULT_RATE) / 60.0
        self._rate = self._default
        self._max_rate = self._MAX_RATE / 60.0
        self._cap = float(capacity)
        self._tokens = 1.0
        self._last = time.monotonic()
        self._ok = 0               # consecutive successes since last backoff
        self._cooldown_until = 0.0
        self._last_throttle_log = 0.0
        self._lock = threading.Lock()

    def set_capacity(self, n: int) -> None:
        """Resize burst window without creating a request spike."""
        with self._lock:
            self._cap = float(max(1, n))
            self._tokens = min(max(self._tokens, 1.0), self._cap)

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


class _StableRateLimiter:
    """Shared token-bucket limiter with per-batch concurrency scaling.

    set_capacity(n) must be called once per batch before any acquire() calls.
    It scales the total rate to n × _DEFAULT_RATE so each thread gets its own
    budget, and resets cooldown/streak so every export starts clean.
    """

    _DEFAULT_RATE: float = 10.0   # req/min per thread
    _MAX_RATE: float = 40.0       # hard ceiling regardless of n
    _MIN_RATE: float = 4.0        # floor per thread; scales with n
    _RECOVERY_EVERY: int = 15     # restore rate after N successes
    _MAX_COOLDOWN_SECONDS: float = 90.0    # cap per 429 wave

    _429_DEBOUNCE_SECS: float = 2.0  # concurrent threads within this window = one event

    def __init__(self, rate_per_min: float | None = None, capacity: int = 1) -> None:
        self._default = (rate_per_min or self._DEFAULT_RATE) / 60.0
        self._max_rate = self._MAX_RATE / 60.0
        self._rate = self._default
        self._rate_ceiling = self._default     # scales with n in set_capacity
        self._min_rate_floor = self._MIN_RATE / 60.0  # scales with n in set_capacity
        self._cap = float(capacity)
        self._tokens = 1.0
        self._last = time.monotonic()
        self._ok = 0
        self._fail_streak = 0
        self._cooldown_until = 0.0
        self._last_throttle_log = 0.0
        self._last_429_time = 0.0  # debounce: prevent per-thread streak inflation
        self._lock = threading.Lock()

    def set_capacity(self, n: int) -> None:
        """Scale rate and burst window for n parallel threads; resets state for a fresh batch."""
        with self._lock:
            n = max(1, n)
            self._cap = float(n)
            self._tokens = min(max(self._tokens, 1.0), self._cap)
            # Each thread gets _DEFAULT_RATE budget; total pool = n × default, capped at MAX
            self._rate_ceiling = min(self._default * n, self._max_rate)
            self._rate = self._rate_ceiling
            # Scale floor: n threads → n × MIN_RATE total
            self._min_rate_floor = self._MIN_RATE * n / 60.0
            # Fresh start for each export batch
            self._fail_streak = 0
            self._cooldown_until = 0.0
            self._last_429_time = 0.0
            self._ok = 0

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                if now < self._cooldown_until:
                    wait = self._cooldown_until - now
                else:
                    self._tokens = min(
                        self._cap,
                        self._tokens + (now - self._last) * self._rate,
                    )
                    self._last = now
                    if self._tokens >= 1.0:
                        self._tokens -= 1.0
                        return
                    wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)

    def on_success(self) -> None:
        with self._lock:
            self._ok += 1
            self._fail_streak = 0   # reset: next 429 starts a fresh streak
            if self._ok >= self._RECOVERY_EVERY:
                self._ok = 0
                self._rate = min(self._rate * 1.20, self._rate_ceiling)

    def clear_cooldown(self) -> None:
        """Lift cooldown and restore full rate (call after a session reset).
        New session = fresh server-side counter, so we start at ceiling speed again.
        """
        with self._lock:
            self._cooldown_until = 0.0
            self._rate = self._rate_ceiling   # new session → full budget restored
            self._tokens = max(self._tokens, 1.0)
            self._fail_streak = 0
            self._ok = 0

    def on_429(self, retry_after: int) -> float:
        with self._lock:
            now = time.monotonic()
            self._ok = 0
            # Debounce: concurrent threads hitting 429 simultaneously = one event.
            # Without this, n threads each decrement rate and increment streak n times
            # per wave, causing the rate to collapse n× faster than intended.
            if now - self._last_429_time >= self._429_DEBOUNCE_SECS:
                self._fail_streak += 1
                self._rate = max(self._rate * 0.75, self._min_rate_floor)
                self._last_throttle_log = 0.0  # force a log line on each new wave
            self._last_429_time = now
            self._tokens = 0.0
            self._last = now
            # Fixed cooldown = Retry-After + jitter, no exponential multiplier
            cooldown = min(
                max(float(retry_after), 30.0) + random.uniform(2.0, 8.0),
                self._MAX_COOLDOWN_SECONDS,
            )
            self._cooldown_until = max(self._cooldown_until, now + cooldown)
            wait = self._cooldown_until - now
            if now - self._last_throttle_log >= 10.0:
                self._last_throttle_log = now
                log_info(
                    f"RateLimiter cooldown {wait:.1f}s; "
                    f"new rate={self._rate * 60:.1f} req/min after 429 "
                    f"streak={self._fail_streak}"
                )
            return wait


_limiter = _StableRateLimiter()

_TTS_READ_TIMEOUT = 90  # seconds — TTS synthesis can be slow for long text


def _tts_request(payload: str) -> "requests.Response":
    """Make a single POST to the TTS endpoint via direct connection."""
    try:
        return _session.post(
            _TTS_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=_TTS_READ_TIMEOUT,
        )
    except (requests.Timeout, requests.ConnectionError) as exc:
        log_error(f"TTS network error {type(exc).__name__}: {exc}")
        raise


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


def _parse_retry_after(value: str | None) -> int:
    try:
        return max(int(value or "30"), 1)
    except ValueError:
        return 30


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
    rate_limit_hits = 0
    session_reset_attempted = False  # try at most once per synthesize_one call

    for attempt in range(retries):
        _limiter.acquire()
        try:
            resp = _tts_request(payload)
            if resp.status_code in (401, 403):
                raise RuntimeError(f"Session expired (HTTP {resp.status_code}) — captcha required")
            if resp.status_code == 429:
                rate_limit_hits += 1
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                wait = _limiter.on_429(retry_after)
                # Recovery order:
                # 1. session_reset — new cookie → fresh server-side counter, no wait
                # 2. sleep         — wait out Retry-After window
                if not session_reset_attempted:
                    session_reset_attempted = True
                    _try_session_reset()
                    action = "session_reset"
                else:
                    action = "sleep"

                log_info(
                    f"SpeechmaEngine 429 rate-limited voice={voice} attempt={attempt + 1}/{retries} "
                    f"action={action}"
                    + ("" if action != "sleep" else f" — backing off {wait:.0f}s (Retry-After={retry_after}s)")
                )
                if rate_limit_hits >= 8:
                    raise RuntimeError(
                        "SpeechMa is still rate-limiting this session after multiple cooldowns. "
                        "Wait 10-15 minutes, then retry failed segments; completed segments are cached."
                    )
                if attempt < retries - 1:
                    if action == "session_reset":
                        _limiter.clear_cooldown()  # new session → fresh budget
                    else:
                        time.sleep(wait)
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
    retries: int = 8,
) -> None:
    if not jobs:
        return
    _limiter.set_capacity(concurrency)  # scales rate and burst window
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
