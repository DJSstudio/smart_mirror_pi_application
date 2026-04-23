"""Unit tests for ShareServer token logic and rate limiting.

Tests exercise the in-process server object directly — no HTTP sockets needed.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.services.share_server import ShareServer, _RateBucket, _RL_BURST


# ---------------------------------------------------------------------------
# _RateBucket
# ---------------------------------------------------------------------------

class TestRateBucket:
    def test_allows_burst_requests(self) -> None:
        bucket = _RateBucket(tokens=float(_RL_BURST))
        for _ in range(_RL_BURST):
            assert bucket.allow() is True

    def test_blocks_after_burst_exhausted(self) -> None:
        bucket = _RateBucket(tokens=float(_RL_BURST))
        for _ in range(_RL_BURST):
            bucket.allow()
        assert bucket.allow() is False

    def test_refills_over_time(self) -> None:
        bucket = _RateBucket(tokens=0.0)
        # Simulate 2 seconds of elapsed time
        bucket.last_refill = time.monotonic() - 2.0
        assert bucket.allow() is True  # 2 tokens refilled, 1 consumed → still positive


# ---------------------------------------------------------------------------
# ShareServer — session tokens
# ---------------------------------------------------------------------------

class TestSessionTokens:
    @pytest.fixture()
    def server(self) -> ShareServer:
        return ShareServer()

    def test_create_and_validate_anonymous_token(self, server: ShareServer) -> None:
        token = server.create_session_token(required_device_id="")
        assert server._check_session_token(token, device_id="any-device") is True

    def test_create_and_validate_device_gated_token(self, server: ShareServer) -> None:
        token = server.create_session_token(required_device_id="dev-abc")
        assert server._check_session_token(token, device_id="dev-abc") is True

    def test_device_gated_token_rejects_wrong_device(self, server: ShareServer) -> None:
        token = server.create_session_token(required_device_id="dev-abc")
        assert server._check_session_token(token, device_id="dev-xyz") is False

    def test_unknown_token_rejected(self, server: ShareServer) -> None:
        assert server._check_session_token("not-a-real-token", device_id="any") is False

    def test_expired_token_rejected(self, server: ShareServer) -> None:
        token = server.create_session_token(required_device_id="")
        # Back-date the expiry
        with server._lock:
            _, device_id = server._session_tokens[token]
            server._session_tokens[token] = (time.time() - 1, device_id)

        assert server._check_session_token(token, device_id="any") is False

    def test_expired_token_pruned_after_check(self, server: ShareServer) -> None:
        token = server.create_session_token(required_device_id="")
        with server._lock:
            server._session_tokens[token] = (time.time() - 1, "")

        server._check_session_token(token, device_id="any")

        with server._lock:
            assert token not in server._session_tokens

    def test_token_is_url_safe_string(self, server: ShareServer) -> None:
        token = server.create_session_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # Must not contain characters unsafe in URLs
        for ch in [" ", "+", "=", "/"]:
            assert ch not in token


# ---------------------------------------------------------------------------
# ShareServer — export tokens
# ---------------------------------------------------------------------------

class TestExportTokens:
    @pytest.fixture()
    def server(self) -> ShareServer:
        return ShareServer()

    def test_create_token_returns_string(self, server: ShareServer) -> None:
        token = server.create_token("vid-1", required_device_id="")
        assert isinstance(token, str) and len(token) > 0

    def test_token_remaining_positive_after_creation(self, server: ShareServer) -> None:
        token = server.create_token("vid-1", required_device_id="")
        remaining = server.token_remaining(token)
        assert remaining > 0

    def test_unknown_token_remaining_returns_zero(self, server: ShareServer) -> None:
        assert server.token_remaining("ghost") == 0

    def test_verify_export_token_any_device(self, server: ShareServer) -> None:
        token = server.create_token("vid-1", required_device_id="")
        ok, video_id = server.verify_export_token(token, device_id="any-device")
        assert ok is True
        assert video_id == "vid-1"

    def test_verify_export_token_wrong_device_rejected(self, server: ShareServer) -> None:
        token = server.create_token("vid-1", required_device_id="dev-owner")
        ok, video_id = server.verify_export_token(token, device_id="dev-other")
        assert ok is False
        assert video_id is None


# ---------------------------------------------------------------------------
# ShareServer — rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @pytest.fixture()
    def server(self) -> ShareServer:
        return ShareServer()

    def test_allows_initial_requests(self, server: ShareServer) -> None:
        for _ in range(5):
            assert server._check_rate_limit("192.168.1.1") is True

    def test_rate_limits_after_burst(self, server: ShareServer) -> None:
        ip = "10.0.0.1"
        for _ in range(_RL_BURST):
            server._check_rate_limit(ip)
        assert server._check_rate_limit(ip) is False

    def test_different_ips_have_independent_buckets(self, server: ShareServer) -> None:
        for _ in range(_RL_BURST):
            server._check_rate_limit("10.0.0.1")
        # A fresh IP should still be allowed
        assert server._check_rate_limit("10.0.0.2") is True


# ---------------------------------------------------------------------------
# ShareServer — login tokens
# ---------------------------------------------------------------------------

class TestLoginTokens:
    @pytest.fixture()
    def server(self) -> ShareServer:
        return ShareServer()

    def test_create_login_token_returns_raw_and_hash(self, server: ShareServer) -> None:
        raw, token_hash = server.create_login_token()
        assert isinstance(raw, str) and len(raw) > 0
        assert isinstance(token_hash, str) and len(token_hash) == 64  # SHA-256 hex

    def test_login_token_initial_status_is_pending(self, server: ShareServer) -> None:
        raw, token_hash = server.create_login_token()
        status, device_id, action = server.check_login_status(token_hash)
        assert status == "pending"
        assert device_id is None
        assert action is None

    def test_invalidated_token_returns_expired(self, server: ShareServer) -> None:
        _, token_hash = server.create_login_token()
        server.invalidate_login_token(token_hash)
        status, _, _ = server.check_login_status(token_hash)
        assert status == "expired"
