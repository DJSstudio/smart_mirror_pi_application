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

    def test_anonymous_token_denied(self, server: ShareServer) -> None:
        # Policy: anonymous (skip-login) sessions are NOT shareable to phones,
        # so an anonymous session token authorizes no device.
        token = server.create_session_token(required_device_id="")
        assert server._check_session_token(token, device_id="any-device") is False

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

    def test_anonymous_export_token_denied(self, server: ShareServer) -> None:
        # Policy: anonymous-session export tokens authorize no device.
        token = server.create_token("vid-1", required_device_id="")
        ok, video_id = server.verify_export_token(token, device_id="any-device")
        assert ok is False

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


# ---------------------------------------------------------------------------
# ShareServer — HTTP download authorization
# Regression guard for the open-endpoint fix: /, /api/videos must be gone and
# /download/<id> must require a valid session token bound to the device.
# ---------------------------------------------------------------------------

class _FakeVideo:
    def __init__(self, vid: str, path: str) -> None:
        self.id = vid
        self.title = "Look 1"
        self.file_path = path
        self.duration_seconds = 5.0

    def created_label(self) -> str:
        return "Today"


class TestDownloadAuthorization:
    @pytest.fixture()
    def live_server(self, tmp_path):
        video_file = tmp_path / "clip.mp4"
        video_file.write_bytes(b"DATA" * 256)
        srv = ShareServer(host="127.0.0.1", port=0)
        srv.start()
        srv.update_gallery("S", [_FakeVideo("vid-1", str(video_file))])
        yield srv, str(video_file)
        srv.stop()

    @staticmethod
    def _get(srv: ShareServer, path: str, cookie: str | None = None):
        """GET a path; pass *cookie* to set the mirror_did device cookie.

        Device identity is now cookie-only (no ?device_id= URL fallback), so
        the owner path supplies its id via this cookie, exactly like a phone."""
        import urllib.error
        import urllib.request
        headers = {"Cookie": f"mirror_did={cookie}"} if cookie is not None else {}
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.port}{path}", headers=headers
        )
        try:
            r = urllib.request.urlopen(req, timeout=5)
            return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_open_gallery_routes_removed(self, live_server) -> None:
        srv, _ = live_server
        assert self._get(srv, "/")[0] == 404
        assert self._get(srv, "/api/videos")[0] == 404

    def test_token_pages_reject_malformed_token(self, live_server) -> None:
        # Reflected-XSS guard: a token outside the token_urlsafe alphabet must
        # be rejected (404) BEFORE it is reflected into any HTML/JS template.
        import urllib.parse
        srv, _ = live_server
        bad = urllib.parse.quote("x';alert(document.cookie)//", safe="")
        assert self._get(srv, f"/session/{bad}")[0] == 404
        assert self._get(srv, f"/export/{bad}")[0] == 404
        assert self._get(srv, f"/qr/activate?token={bad}")[0] == 404

    def test_token_page_json_encodes_token(self, live_server) -> None:
        # A well-formed token renders the page with the token JSON-encoded into
        # a double-quoted JS literal — never the old single-quoted form that the
        # _esc()-based code allowed to break out of.
        srv, _ = live_server
        code, body = self._get(srv, "/qr/activate?token=AbC123_-xyz")
        assert code == 200
        assert b'var token="AbC123_-xyz";' in body
        assert b"var token='" not in body

    def test_download_without_token_forbidden(self, live_server) -> None:
        srv, _ = live_server
        assert self._get(srv, "/download/vid-1")[0] == 403

    def test_download_wrong_device_forbidden(self, live_server) -> None:
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="owner")
        code = self._get(srv, f"/download/vid-1?token={tok}", cookie="attacker")[0]
        assert code == 403

    def test_download_device_id_query_param_is_ignored(self, live_server) -> None:
        # H1 fix: identity is the HttpOnly cookie ONLY.  A LAN attacker who
        # photographed the session-QR token but lacks the owner's cookie must
        # NOT be able to assert the owner's id via ?device_id= and exfiltrate.
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="owner")
        # No cookie sent — the (legacy) query param must be inert.
        assert self._get(srv, f"/download/vid-1?token={tok}&device_id=owner")[0] == 403

    def test_download_valid_owner_streams_file(self, live_server) -> None:
        import os
        srv, path = live_server
        tok = srv.create_session_token(required_device_id="owner")
        code, body = self._get(srv, f"/download/vid-1?token={tok}", cookie="owner")
        assert code == 200
        assert len(body) == os.path.getsize(path)

    def test_anonymous_session_denied(self, live_server) -> None:
        # Policy: an anonymous (skip-login) session is not shareable — its
        # token must not authorize a download from any device, even one
        # presenting a real device cookie.
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="")
        code = self._get(srv, f"/download/vid-1?token={tok}", cookie="whatever")[0]
        assert code == 403

    def test_download_token_only_no_identity_forbidden(self, live_server) -> None:
        # Valid session token but no cookie and no device_id param → device
        # check fails (device-gated session).
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="owner")
        assert self._get(srv, f"/download/vid-1?token={tok}")[0] == 403

    def test_download_with_device_cookie(self, live_server) -> None:
        # The HttpOnly cookie carries the device identity (H1) — no device_id
        # in the URL needed.
        import urllib.request
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="owner")
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.port}/download/vid-1?token={tok}",
            headers={"Cookie": "mirror_did=owner"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 200

    def test_qr_confirm_sets_httponly_device_cookie(self, live_server) -> None:
        # First QR confirm with no cookie mints + sets a server-side device id.
        import urllib.request
        srv, _ = live_server
        raw, _ = srv.create_login_token()
        with urllib.request.urlopen(
            f"http://127.0.0.1:{srv.port}/api/qr/confirm?token={raw}", timeout=5
        ) as r:
            set_cookie = r.headers.get("Set-Cookie", "")
        assert "mirror_did=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_clear_session_data_revokes_access(self, live_server) -> None:
        # H3: logout clears the snapshot + invalidates the session token.
        srv, _ = live_server
        tok = srv.create_session_token(required_device_id="owner")
        assert self._get(srv, f"/download/vid-1?token={tok}", cookie="owner")[0] == 200
        srv.clear_session_data()
        assert self._get(srv, f"/download/vid-1?token={tok}", cookie="owner")[0] == 403
