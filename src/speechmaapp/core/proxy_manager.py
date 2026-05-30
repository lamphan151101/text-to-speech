"""Proxy failover manager.

Selects and rotates through a list of proxy profiles when TTS requests
encounter network-level failures (Timeout, ConnectionError, 502/503/504)
or HTTP 429 rate-limit responses.

State machine:
  direct (default) → proxy[0] → proxy[1] → ... → direct (when all in cooldown)

Network failures use the full cooldown (proxy_cooldown_seconds).
Rate-limit (429) responses use a short cooldown (Retry-After + 10s) so
the proxy is available again quickly once the server cools down.
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


_DIRECT = "direct"


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
        self._cooldown_until: dict[str, float] = {}     # network-error cooldowns
        self._rl_cooldown_until: dict[str, float] = {}  # rate-limit (429) cooldowns
        # -1 = direct connection (default start state)
        self._current_idx: int = -1

        if not enabled:
            log_info("ProxyManager disabled")
            return
        if not self._profiles:
            log_info("ProxyManager enabled but no valid proxy profiles configured")
            return
        log_info(
            f"ProxyManager loaded profiles count={len(self._profiles)} "
            "— starting with direct connection (proxies are failover)"
        )

    # ------------------------------------------------------------------ public

    def current_name(self) -> str:
        with self._lock:
            if not self._enabled or not self._profiles:
                return _DIRECT
            if self._current_idx == -1:
                return _DIRECT
            p = self._profiles[self._current_idx]
            if self._cooldown_until.get(p.name, 0.0) <= time.monotonic():
                return p.name
            return _DIRECT

    def current_proxies(self) -> dict[str, str] | None:
        """Return proxies dict for requests, or None to use direct connection."""
        with self._lock:
            if not self._enabled or not self._profiles:
                return None
            if self._current_idx == -1:
                return None
            p = self._profiles[self._current_idx]
            if self._cooldown_until.get(p.name, 0.0) > time.monotonic():
                # Current proxy in cooldown — use direct as fallback
                return None
            out: dict[str, str] = {}
            if p.http:
                out["http"] = p.http
            if p.https:
                out["https"] = p.https
            return out or None

    def report_success(self, elapsed_seconds: float) -> None:
        """Called after a successful request; triggers rotation on slow response."""
        with self._lock:
            if not self._enabled or not self._profiles:
                return
            if self._current_idx == -1:
                return  # direct connection succeeded — nothing to rotate
            p = self._profiles[self._current_idx]
            if elapsed_seconds > self._slow_threshold:
                log_error(
                    f"ProxyManager slow response proxy={p.name} "
                    f"elapsed={elapsed_seconds:.1f}s threshold={self._slow_threshold}s"
                )
                self._put_on_cooldown(p.name, "slow_response")

    def report_failure(self, reason: str, proxy_was_active: bool = True) -> None:
        """Called after a network-level failure; rotates to next proxy (or direct).

        proxy_was_active must be False when the request went via direct connection
        because the current proxy was in cooldown.  In that case the proxy is NOT
        blamed and its cooldown is NOT extended — we just wait for it to recover.
        """
        with self._lock:
            if not self._enabled or not self._profiles:
                return
            if self._current_idx == -1 or not proxy_was_active:
                # Either naturally on direct, or proxy was in cooldown and we fell
                # back to direct — do not blame or rotate the proxy.
                log_error(f"ProxyManager direct connection failure reason={reason}")
                if self._current_idx == -1:
                    self._rotate(from_name=_DIRECT, reason=reason)
            else:
                p = self._profiles[self._current_idx]
                log_error(f"ProxyManager failure proxy={p.name} reason={reason}")
                self._put_on_cooldown(p.name, reason)

    def report_rate_limited(self, retry_after_seconds: int = 30) -> bool:
        """Rotate IP on HTTP 429 using a short rate-limit cooldown (Retry-After + 10 s).

        Unlike report_failure(), this uses a SEPARATE _rl_cooldown_until dict so
        proxies in a long network-error cooldown can still be tried for 429 bypass —
        a different IP that was previously slow may not be rate-limited.

        Returns True if the active connection actually changed (new IP available).
        """
        with self._lock:
            if not self._enabled or not self._profiles:
                return False
            now = time.monotonic()
            short_cooldown = max(float(retry_after_seconds), 30.0) + 10.0

            # Record current name before rotation
            old_name = (
                _DIRECT if self._current_idx == -1
                else self._profiles[self._current_idx].name
            )

            # Put current connection on rate-limit cooldown
            if self._current_idx != -1:
                p = self._profiles[self._current_idx]
                self._rl_cooldown_until[p.name] = now + short_cooldown
                log_info(
                    f"ProxyManager 429 proxy={p.name} "
                    f"rl_cooldown={short_cooldown:.0f}s → rotating"
                )
            else:
                log_info("ProxyManager 429 on direct → trying proxy failover")

            # Rotate using RATE-LIMIT cooldown only (ignore network-error cooldowns).
            # This lets a proxy that was slow/failing still be tried for a different IP.
            start_idx = 0 if self._current_idx == -1 else (self._current_idx + 1) % len(self._profiles)
            for i in range(len(self._profiles)):
                idx = (start_idx + i) % len(self._profiles)
                candidate = self._profiles[idx]
                if self._rl_cooldown_until.get(candidate.name, 0.0) <= now:
                    self._current_idx = idx
                    # Clear the network-error cooldown so current_proxies() actually
                    # routes through this proxy (not direct fallback).
                    self._cooldown_until.pop(candidate.name, None)
                    safe = _redact(candidate.http or candidate.https)
                    log_info(
                        f"ProxyManager IP switched for 429: {old_name} → {candidate.name} "
                        f"addr={safe}"
                    )
                    return True

            # All proxies are in rate-limit cooldown too — fall back to direct
            self._current_idx = -1
            log_info(
                f"ProxyManager no IP switch available for 429 "
                f"(all proxies rate-limited, staying on direct)"
            )
            return old_name != _DIRECT  # True only if we moved FROM a proxy to direct

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
        """Find the next available proxy; fall back to direct if all are in cooldown."""
        now = time.monotonic()
        # When rotating from direct (-1), start at proxy[0]; otherwise advance from current.
        start_idx = 0 if self._current_idx == -1 else (self._current_idx + 1) % len(self._profiles)
        for i in range(len(self._profiles)):
            idx = (start_idx + i) % len(self._profiles)
            candidate = self._profiles[idx]
            if self._cooldown_until.get(candidate.name, 0.0) <= now:
                self._current_idx = idx
                safe = _redact(candidate.http or candidate.https)
                log_info(
                    f"ProxyManager switched {from_name} -> {candidate.name} "
                    f"addr={safe} reason={reason}"
                )
                return
        # All proxies in cooldown → fall back to direct connection
        self._current_idx = -1
        log_error(
            "ProxyManager all proxies unavailable, falling back to direct connection"
        )
