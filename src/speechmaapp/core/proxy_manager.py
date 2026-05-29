"""Proxy failover manager.

Selects and rotates through a list of proxy profiles when TTS requests
encounter network-level failures (Timeout, ConnectionError, 502/503/504).

Intentionally NOT used for 429 rate-limiting — that is handled by the
adaptive rate limiter in speechma_engine.py.
"""

from __future__ import annotations

import re
import threading
import time

from speechmaapp.config import ProxyProfile
from speechmaapp.utils.logging_utils import log_error, log_info


def _redact(url: str) -> str:
    """Replace user:pass@ credentials in a proxy URL with ***:***@"""
    return re.sub(r"://[^:@/]+:[^@/]+@", "://***:***@", url)


class ProxyManager:
    def __init__(
        self,
        profiles: list[ProxyProfile],
        enabled: bool,
        slow_response_seconds: int = 20,
        cooldown_seconds: int = 300,
    ) -> None:
        self._enabled = enabled
        self._slow_threshold = max(5, min(slow_response_seconds, 120))
        self._cooldown = max(30, min(cooldown_seconds, 3600))
        self._lock = threading.Lock()
        self._profiles = [p for p in profiles if p.http or p.https]
        self._cooldown_until: dict[str, float] = {}
        self._current_idx: int = 0

        if not enabled:
            log_info("ProxyManager disabled")
            return
        if not self._profiles:
            log_info("ProxyManager enabled but no valid proxy profiles configured")
            return
        log_info(f"ProxyManager loaded profiles count={len(self._profiles)}")
        self._log_current()

    # ------------------------------------------------------------------ public

    def current_name(self) -> str:
        with self._lock:
            if not self._enabled or not self._profiles:
                return "direct"
            p = self._profiles[self._current_idx]
            if self._cooldown_until.get(p.name, 0.0) <= time.monotonic():
                return p.name
            return "direct"

    def current_proxies(self) -> dict[str, str] | None:
        """Return proxies dict for requests, or None to use direct connection."""
        with self._lock:
            if not self._enabled or not self._profiles:
                return None
            p = self._profiles[self._current_idx]
            if self._cooldown_until.get(p.name, 0.0) > time.monotonic():
                return None  # all proxies in cooldown → direct fallback
            out: dict[str, str] = {}
            if p.http:
                out["http"] = p.http
            if p.https:
                out["https"] = p.https
            return out or None

    def report_success(self, elapsed_seconds: float) -> None:
        """Called after a successful request; triggers proxy rotation on slow response."""
        with self._lock:
            if not self._enabled or not self._profiles:
                return
            p = self._profiles[self._current_idx]
            if elapsed_seconds > self._slow_threshold:
                log_error(
                    f"ProxyManager slow response proxy={p.name} "
                    f"elapsed={elapsed_seconds:.1f}s threshold={self._slow_threshold}s"
                )
                self._put_on_cooldown(p.name, "slow_response")

    def report_failure(self, reason: str) -> None:
        """Called after a network-level failure; puts current proxy on cooldown."""
        with self._lock:
            if not self._enabled or not self._profiles:
                return
            p = self._profiles[self._current_idx]
            log_error(f"ProxyManager failure proxy={p.name} reason={reason}")
            self._put_on_cooldown(p.name, reason)

    def should_switch_for_status(self, status_code: int) -> bool:
        return status_code in (502, 503, 504)

    # ----------------------------------------------------------------- private

    def _put_on_cooldown(self, name: str, reason: str) -> None:
        self._cooldown_until[name] = time.monotonic() + self._cooldown
        log_info(
            f"ProxyManager cooldown proxy={name} seconds={self._cooldown} reason={reason}"
        )
        self._rotate(from_name=name, reason=reason)

    def _rotate(self, from_name: str, reason: str) -> None:
        now = time.monotonic()
        for _ in range(len(self._profiles)):
            self._current_idx = (self._current_idx + 1) % len(self._profiles)
            candidate = self._profiles[self._current_idx]
            if self._cooldown_until.get(candidate.name, 0.0) <= now:
                log_info(
                    f"ProxyManager switched proxy {from_name} -> {candidate.name} reason={reason}"
                )
                return
        log_error(
            "ProxyManager all proxies unavailable, falling back to direct connection"
        )

    def _log_current(self) -> None:
        if not self._profiles:
            return
        p = self._profiles[self._current_idx]
        safe = _redact(p.http or p.https)
        log_info(f"ProxyManager using proxy={p.name} addr={safe}")
