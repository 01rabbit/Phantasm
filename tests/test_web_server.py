import asyncio
import inspect
import os
import sys
import time
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import web_server
from phasmid.restricted_actions import (
    RestrictedActionRejected,
    evaluate_restricted_action,
)


class WebServerBoundaryTests(unittest.TestCase):
    def tearDown(self):
        web_server._rate_limit.clear()
        web_server._restricted_sessions.clear()
        web_server._access_attempts._state.clear()
        web_server._ui_sessions.clear()
        web_server._unlock_attempts._state.clear()

    def test_require_web_token_rejects_invalid_token(self):
        with self.assertRaises(HTTPException) as ctx:
            web_server.require_web_token("wrong")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_web_token_accepts_current_token(self):
        self.assertIsNone(web_server.require_web_token(web_server.WEB_TOKEN))

    def test_disabled_capability_rejects_with_neutral_error(self):
        with mock.patch.object(web_server, "capability_enabled", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                web_server.require_capability(web_server.Capability.TOKEN_ROTATION)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "operation unavailable")

    def test_fastapi_debug_is_disabled_by_default(self):
        self.assertFalse(web_server.app.debug)

    def test_security_headers_are_applied_to_responses(self):
        response = web_server._apply_security_headers(JSONResponse({"ok": True}))
        self.assertEqual(
            response.headers["cache-control"],
            "no-store, no-cache, must-revalidate, max-age=0",
        )
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn(
            "frame-ancestors 'none'", response.headers["content-security-policy"]
        )
        self.assertIn("camera=(self)", response.headers["permissions-policy"])

    def test_rate_limit_blocks_after_configured_limit(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(path="/retrieve"),
        )
        for _ in range(web_server.RATE_LIMIT_MAX):
            web_server.enforce_rate_limit(request)

        with self.assertRaises(HTTPException) as ctx:
            web_server.enforce_rate_limit(request)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_upload_size_limit_rejects_large_payload(self):
        async def run():
            with mock.patch.object(web_server, "MAX_UPLOAD_BYTES", 8):
                content = b"x" * 9
                upload = UploadFile(filename="oversized.bin", file=_BytesFile(content))
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.read_limited_upload(upload)
            self.assertEqual(ctx.exception.status_code, 413)

        asyncio.run(run())

    def test_store_rejects_short_access_password(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/store"),
            )
            upload = UploadFile(filename="payload.txt", file=_BytesFile(b"data"))
            response = await web_server.store(
                request,
                file=upload,
                password="short",
                restricted_recovery_password="another-short",
            )
            self.assertIn("at least", response["error"])

        asyncio.run(run())

    def test_status_uses_neutral_terms(self):
        with mock.patch.object(
            web_server.access_cue_service,
            "status",
            return_value={
                "object_detected": True,
                "matched_mode": "dummy",
                "match_states": {"dummy": True, "secret": False},
                "registered_modes": {"dummy": True, "secret": False},
            },
        ):
            status = web_server.neutral_status()

        self.assertEqual(status["object_state"], "matched")
        self.assertTrue(
            {"camera_ready", "object_state", "device_state", "local_mode"}.issubset(
                set(status.keys())
            )
        )

    def test_status_uses_active_camera_backend_from_gate_status(self):
        with mock.patch.object(
            web_server.access_cue_service,
            "status",
            return_value={
                "camera_ready": True,
                "object_detected": False,
                "matched_mode": "none",
                "match_states": {"dummy": False, "secret": False},
                "registered_modes": {"dummy": False, "secret": False},
                "camera_backend": "picamera2",
                "last_camera_error": None,
                "camera_backend_warnings": ["OpenCV VideoCapture(0) open failed"],
                "stream_resolution": {"width": 320, "height": 240},
                "fps_target": 4,
            },
        ):
            status = web_server.neutral_status()

        self.assertTrue(status["camera_ready"])
        self.assertEqual(status["camera_backend"], "picamera2")
        self.assertIsNone(status["last_camera_error"])

    def test_status_normalizes_backend_when_ready_but_backend_unknown(self):
        with mock.patch.object(
            web_server.access_cue_service,
            "status",
            return_value={
                "camera_ready": True,
                "object_detected": False,
                "matched_mode": "none",
                "match_states": {"dummy": False, "secret": False},
                "registered_modes": {"dummy": False, "secret": False},
                "camera_backend": "none",
                "last_camera_error": None,
                "camera_backend_warnings": [],
                "stream_resolution": {"width": 320, "height": 240},
                "fps_target": 4,
            },
        ):
            status = web_server.neutral_status()

        self.assertTrue(status["camera_ready"])
        self.assertEqual(status["camera_backend"], "stream")

    def test_require_ui_unlock_rejects_request_without_page_session(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={},
        )
        with self.assertRaises(HTTPException) as ctx:
            web_server.require_ui_unlock(request)
        self.assertEqual(ctx.exception.status_code, 423)

    def test_require_ui_unlock_allows_request_with_page_session(self):
        token = web_server._create_ui_session("127.0.0.1")
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={web_server.UI_SESSION_COOKIE: token},
        )
        self.assertIsNone(web_server.require_ui_unlock(request))

    def test_status_returns_neutral_status_without_face_gate(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
            )
            with mock.patch.object(
                web_server,
                "neutral_status",
                return_value={
                    "camera_ready": True,
                    "object_state": "matched",
                    "device_state": "ready",
                    "local_mode": True,
                },
            ):
                response = await web_server.status(request)
            self.assertEqual(response["device_state"], "ready")
            self.assertTrue(response["camera_ready"])
            self.assertEqual(response["object_state"], "matched")
            self.assertTrue(
                {
                    "camera_ready",
                    "object_state",
                    "device_state",
                    "local_mode",
                }.issubset(set(response.keys()))
            )

        asyncio.run(run())

    def test_retrieve_attempt_limiter_blocks_repeated_failures(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/retrieve"),
            )
            limiter = web_server.AttemptLimiter(
                max_failures=1,
                lockout_seconds=30,
                clock=lambda: 1000,
            )
            with (
                mock.patch.object(web_server, "_access_attempts", limiter),
                mock.patch.object(
                    web_server.access_cue_service,
                    "auth_sequence",
                    return_value=[web_server.access_cue_service.match_none()],
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "current_match_mode",
                    return_value=web_server.access_cue_service.match_none(),
                ),
            ):
                first = await web_server.retrieve(request, password="wrong-passphrase")
                second = await web_server.retrieve(request, password="wrong-passphrase")
            self.assertEqual(first["error"], web_server.text.NO_VALID_ENTRY_FOUND)
            self.assertEqual(
                second["error"],
                web_server.text.ACCESS_TEMPORARILY_UNAVAILABLE,
            )

        asyncio.run(run())

    def test_retrieve_does_not_return_ambiguous_error_in_coercion_safe(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/retrieve"),
            )
            with (
                mock.patch.object(
                    web_server.access_cue_service,
                    "current_match_mode",
                    return_value=web_server.access_cue_service.match_ambiguous(),
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "auth_sequence",
                    return_value=["reference_dummy_matched"],
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "modes",
                    return_value=("dummy",),
                ),
                mock.patch.object(
                    web_server.vault,
                    "retrieve_with_policy",
                    return_value=(None, None, "open"),
                ),
            ):
                response = await web_server.retrieve(request, password="pw")
            self.assertEqual(response["error"], web_server.text.NO_VALID_ENTRY_FOUND)
            self.assertNotEqual(
                response.get("error"), web_server.text.AMBIGUOUS_OBJECT_MATCH
            )

        asyncio.run(run())

    def test_video_feed_requires_unlocked_ui(self):
        route = next(
            route
            for route in web_server.app.routes
            if getattr(route, "path", None) == "/video_feed"
        )
        dependency_names = {item.call.__name__ for item in route.dependant.dependencies}
        self.assertIn("require_ui_unlock", dependency_names)

    def test_shutdown_cleanup_closes_camera_resources(self):
        async def run():
            with mock.patch.object(web_server.access_cue_service, "close") as close:
                await web_server.shutdown_cleanup()
                close.assert_called_once()

        asyncio.run(run())

    def test_video_feed_stream_cleanup_runs_on_disconnect(self):
        async def run():
            with (
                mock.patch.object(
                    web_server.access_cue_service,
                    "generate_frames",
                    return_value=iter(
                        [b"--frame\r\nContent-Type: image/jpeg\r\n\r\nx\r\n"]
                    ),
                ),
                mock.patch.object(
                    web_server.access_cue_service, "release_camera"
                ) as release_camera,
            ):
                response = await web_server.video_feed()
                iterator = response.body_iterator
                first = await iterator.__anext__()
                self.assertTrue(first.startswith(b"--frame"))
                await iterator.aclose()
                for _ in range(20):
                    if release_camera.call_count >= 1:
                        break
                    await asyncio.sleep(0.01)
                release_camera.assert_called_once()

        asyncio.run(run())

    def test_restricted_confirmation_sets_short_lived_cookie(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/restricted/confirm"),
            )
            response = await web_server.restricted_confirm(
                request,
                confirmation=web_server.RESTRICTED_CONFIRMATION_PHRASE,
            )
            self.assertIn(
                web_server.RESTRICTED_SESSION_COOKIE,
                response.headers.get("set-cookie", ""),
            )

        asyncio.run(run())

    def test_restricted_confirmation_rejects_missing_or_stale_session(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={},
        )
        with self.assertRaises(HTTPException) as ctx:
            web_server.require_restricted_confirmation(request)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_entry_status_requires_restricted_confirmation_dependency(self):
        sensitive_paths = {"/maintenance/entry_status"}
        for path in sensitive_paths:
            route = next(
                route
                for route in web_server.app.routes
                if getattr(route, "path", None) == path
            )
            dependency_names = {
                item.call.__name__ for item in route.dependant.dependencies
            }
            self.assertIn("require_restricted_confirmation", dependency_names)

    def test_restricted_action_service_rejects_missing_confirmation_session(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={},
        )
        with self.assertRaises(HTTPException) as ctx:
            web_server.require_restricted_action(
                "initialize_container",
                request,
                web_server.INITIALIZE_CONTAINER_PHRASE,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "restricted confirmation required")

    def test_emergency_page_hides_actions_before_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
            )
            with (
                mock.patch.object(web_server, "_guard_page", return_value=None),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                response = await web_server.emergency_page(request)
            self.assertFalse(response.context["restricted_confirmed"])
            self.assertEqual(
                response.context["restricted_session_seconds_remaining"], 0
            )

        asyncio.run(run())

    def test_emergency_page_reports_restricted_session_lifetime(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={web_server.RESTRICTED_SESSION_COOKIE: "token"},
            )
            with (
                mock.patch.object(web_server, "_guard_page", return_value=None),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(
                    web_server,
                    "_restricted_session_seconds_remaining",
                    return_value=74,
                ),
            ):
                response = await web_server.emergency_page(request)
            self.assertTrue(response.context["restricted_confirmed"])
            self.assertEqual(
                response.context["restricted_session_seconds_remaining"], 74
            )

        asyncio.run(run())

    def test_entry_management_page_hides_status_before_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
            )
            with (
                mock.patch.object(web_server, "_guard_page", return_value=None),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                response = await web_server.entry_management_page(request)
            self.assertFalse(response.context["restricted_confirmed"])
            self.assertNotIn("entry_status", response.context)

        asyncio.run(run())

    def test_field_mode_maintenance_hides_paths_before_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
            )
            with (
                mock.patch.object(web_server, "_guard_page", return_value=None),
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                response = await web_server.maintenance_page(request)
            self.assertTrue(response.context["field_mode"])
            self.assertFalse(response.context["restricted_confirmed"])
            self.assertEqual(response.context["state_path"], "")

        asyncio.run(run())

    def test_field_mode_diagnostics_are_neutral_before_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/diagnostics"),
            )
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
                mock.patch.object(
                    web_server,
                    "neutral_status",
                    return_value={
                        "camera_ready": True,
                        "object_state": "none",
                        "device_state": "ready",
                        "local_mode": True,
                    },
                ),
            ):
                response = await web_server.diagnostics(request)
            self.assertEqual(
                set(response.keys()),
                {
                    "device_state",
                    "camera_ready",
                    "object_state",
                    "local_mode",
                    "restricted_confirmation_active",
                },
            )

        asyncio.run(run())

    def test_diagnostics_include_hardware_binding_details_after_restricted_access(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/diagnostics"),
            )
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(
                    web_server,
                    "neutral_status",
                    return_value={
                        "camera_ready": True,
                        "object_state": "none",
                        "device_state": "ready",
                        "local_mode": True,
                    },
                ),
                mock.patch.object(
                    web_server,
                    "hardware_binding_status",
                    return_value=SimpleNamespace(
                        to_dict=lambda: {
                            "host_supported": True,
                            "device_binding_available": True,
                            "external_binding_configured": False,
                        }
                    ),
                ),
            ):
                response = await web_server.diagnostics(request)
            self.assertIn("hardware_binding", response)
            self.assertEqual(
                response["hardware_binding"]["device_binding_available"], True
            )

        asyncio.run(run())

    def test_field_mode_rejects_log_export_without_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/logs"),
            )
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.export_logs(request)
            self.assertEqual(ctx.exception.status_code, 403)

        asyncio.run(run())

    def test_field_mode_rejects_token_rotation_without_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/rotate_token"),
            )
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.rotate_token(request)
            self.assertEqual(ctx.exception.status_code, 403)

        asyncio.run(run())

    def test_deployment_mode_rejects_token_rotation_when_unavailable(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/rotate_token"),
            )
            with mock.patch.dict(os.environ, {"PHASMID_PROFILE": "field"}, clear=True):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.rotate_token(request)
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertEqual(ctx.exception.detail, "operation unavailable")

        asyncio.run(run())

    def test_field_mode_rejects_session_reset_without_restricted_confirmation(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                cookies={},
                url=SimpleNamespace(path="/maintenance/reset_session"),
            )
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.reset_session(request)
            self.assertEqual(ctx.exception.status_code, 403)

        asyncio.run(run())

    def test_hidden_clear_requires_explicit_phrase(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/purge_other"),
            )
            with mock.patch.object(
                web_server, "_restricted_session_valid", return_value=True
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.purge_other(
                        request,
                        accessed_entry="entry_1",
                        confirmation="DELETE",
                    )
            self.assertEqual(ctx.exception.detail, "confirmation rejected")

        asyncio.run(run())

    def test_hidden_clear_ignores_purge_confirmation_environment(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/purge_other"),
            )
            with (
                mock.patch.object(
                    web_server, "purge_confirmation_required", return_value=False
                ),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(web_server.vault, "purge_other_mode") as purge,
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.purge_other(
                        request,
                        accessed_entry="entry_1",
                        confirmation="",
                    )
            purge.assert_not_called()
            self.assertEqual(ctx.exception.detail, "confirmation rejected")

        asyncio.run(run())

    def test_hidden_clear_accepts_confirmation_phrase(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/purge_other"),
            )
            with (
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(web_server.vault, "purge_other_mode") as purge,
            ):
                response = await web_server.purge_other(
                    request,
                    accessed_entry="entry_1",
                    confirmation=web_server.DESTRUCTIVE_CLEAR_PHRASE,
                )
            purge.assert_called_once_with("dummy")
            self.assertIn("cleared", response["status"])

        asyncio.run(run())

    def test_emergency_initialize_requires_confirmation_phrase(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/emergency/initialize"),
            )
            with (
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(web_server.vault, "format_container") as init,
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.emergency_initialize(
                        request,
                        confirmation="INITIALIZE",
                    )
            init.assert_not_called()
            self.assertEqual(ctx.exception.detail, "confirmation rejected")

        asyncio.run(run())

    def test_emergency_initialize_resets_container_and_bindings(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/emergency/initialize"),
            )
            with (
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(web_server.vault, "format_container") as init,
                mock.patch.object(
                    web_server.access_cue_service,
                    "clear_references",
                    return_value=(True, "ok"),
                ) as clear,
            ):
                response = await web_server.emergency_initialize(
                    request,
                    confirmation=web_server.INITIALIZE_CONTAINER_PHRASE,
                )
            init.assert_called_once_with(rotate_access_key=True)
            clear.assert_called_once_with()
            self.assertIn("initialized", response["status"])

        asyncio.run(run())

    def test_duress_mode_auto_purges_dummy_access(self):
        with (
            mock.patch.object(web_server, "duress_mode_enabled", return_value=True),
            mock.patch.object(
                web_server, "purge_confirmation_required", return_value=True
            ),
            mock.patch.object(web_server.vault, "purge_other_mode") as purge,
        ):
            self.assertTrue(web_server._maybe_auto_purge("dummy", source="test"))
        purge.assert_called_once_with("dummy")

    def test_duress_mode_does_not_auto_purge_secret_access(self):
        with (
            mock.patch.object(web_server, "duress_mode_enabled", return_value=True),
            mock.patch.object(
                web_server, "purge_confirmation_required", return_value=True
            ),
            mock.patch.object(web_server.vault, "purge_other_mode") as purge,
        ):
            self.assertFalse(web_server._maybe_auto_purge("secret", source="test"))
        purge.assert_not_called()

    def test_restricted_recovery_password_role_updates_unmatched_entry(self):
        with mock.patch.object(web_server.vault, "purge_other_mode") as purge:
            self.assertTrue(
                web_server._purge_for_password_role(
                    "dummy",
                    web_server.PhasmidVault.PURGE_ROLE,
                    source="test",
                )
            )
        purge.assert_called_once_with("dummy")

    def test_open_password_role_preserves_unmatched_entry(self):
        with mock.patch.object(web_server.vault, "purge_other_mode") as purge:
            self.assertFalse(
                web_server._purge_for_password_role(
                    "dummy",
                    web_server.PhasmidVault.OPEN_ROLE,
                    source="test",
                )
            )
        purge.assert_not_called()

    def test_download_response_uses_neutral_filename_without_state_change_header(self):
        response = web_server.create_file_response(
            b"payload", "source-name.txt", purge_applied=True
        )
        self.assertIn("retrieved_payload.bin", response.headers["content-disposition"])
        self.assertNotIn("x-local-state-updated", response.headers)
        self.assertNotIn("source-name", str(response.headers).lower())

    def test_normal_and_restricted_recovery_responses_are_structurally_identical(self):
        normal_response = web_server.create_file_response(
            b"payload", "any-name.bin", purge_applied=False
        )
        restricted_response = web_server.create_file_response(
            b"payload", "any-name.bin", purge_applied=True
        )
        self.assertEqual(
            normal_response.headers["content-disposition"],
            restricted_response.headers["content-disposition"],
        )
        self.assertEqual(
            normal_response.media_type,
            restricted_response.media_type,
        )
        normal_keys = set(normal_response.headers.keys())
        restricted_keys = set(restricted_response.headers.keys())
        self.assertEqual(normal_keys, restricted_keys)

    def test_restricted_recovery_response_does_not_expose_slot_role(self):
        response = web_server.create_file_response(
            b"payload", "evidence.bin", purge_applied=True
        )
        headers_str = str(response.headers).lower()
        for term in ("purge", "restricted", "slot", "role", "open", "clear"):
            self.assertNotIn(term, headers_str)

    def test_x_result_filename_is_neutral_regardless_of_original_name(self):
        for original in ("classified_notes.txt", "evidence.bin", "my_secret.docx"):
            response = web_server.create_file_response(b"data", original)
            result_filename = response.headers.get("x-result-filename", "")
            self.assertEqual(result_filename, "retrieved_payload.bin")
            self.assertNotIn(original.split(".")[0], result_filename)

    def test_metadata_check_reports_obvious_local_risk(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/metadata/check"),
            )
            upload = UploadFile(
                filename="notes.txt",
                file=_BytesFile(b"author: Alice\npath: /Users/alice/source.txt\n"),
            )
            response = await web_server.metadata_check(request, upload)
            self.assertEqual(response["risk"], "high")
            self.assertIn("local path leakage", response["findings"])
            self.assertIn("best-effort", response["limitation"])

        asyncio.run(run())

    def test_metadata_scrub_uses_neutral_download_name(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/metadata/scrub"),
            )
            upload = UploadFile(
                filename="revealing-name.txt",
                file=_BytesFile(b"author: Alice\npath: /home/alice/source.txt\n"),
            )
            response = await web_server.metadata_scrub(request, upload)
            headers = str(response.headers).lower()
            self.assertIn("metadata_reduced_payload.bin", headers)
            self.assertNotIn("revealing-name", headers)

        asyncio.run(run())

    def test_metadata_scrub_ignores_scrubber_filename_for_headers(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/metadata/scrub"),
            )
            upload = UploadFile(
                filename="original-name.txt",
                file=_BytesFile(b"payload"),
            )
            with mock.patch.object(
                web_server,
                "scrub_metadata",
                return_value={
                    "success": True,
                    "filename": "revealing-result-name.txt",
                    "data": b"payload",
                    "message": "ok",
                    "limitation": "best-effort",
                },
            ):
                response = await web_server.metadata_scrub(request, upload)
            headers = str(response.headers).lower()
            self.assertIn("metadata_reduced_payload.bin", headers)
            self.assertNotIn("revealing-result-name", headers)
            self.assertNotIn("original-name", headers)

        asyncio.run(run())

    def test_metadata_routes_require_web_token_and_ui_unlock(self):
        for path in {"/metadata/check", "/metadata/scrub"}:
            route = next(
                route
                for route in web_server.app.routes
                if getattr(route, "path", None) == path
            )
            dependency_names = {
                item.call.__name__ for item in route.dependant.dependencies
            }
            self.assertIn("require_web_token", dependency_names)
            self.assertIn("require_ui_unlock", dependency_names)

    def test_metadata_scrub_unsupported_type_fails_safely(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/metadata/scrub"),
            )
            upload = UploadFile(
                filename="image.jpg",
                file=_BytesFile(b"\xff\xd8Exif\x00\x00GPS"),
            )
            response = await web_server.metadata_scrub(request, upload)
            self.assertEqual(response.status_code, 422)
            body = response.body.decode("utf-8")
            self.assertIn("not supported", body)
            self.assertIn("best-effort", body)

        asyncio.run(run())

    def _register_key_request(self):
        return SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            url=SimpleNamespace(path="/register_key"),
        )

    def test_register_key_with_image_file_uses_image_binding(self):
        async def run():
            upload = UploadFile(filename="cue.png", file=_BytesFile(b"png-bytes"))
            with (
                mock.patch.object(
                    web_server,
                    "_raw_gate_status",
                    return_value={
                        "registered_modes": {"dummy": False, "secret": False}
                    },
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "register_reference_from_image_bytes",
                    return_value=(True, "bound"),
                ) as register_mock,
                mock.patch.object(web_server, "_capture_entry_binding") as capture_mock,
                mock.patch.object(web_server, "audit_event") as audit_mock,
            ):
                response = await web_server.register_key(
                    self._register_key_request(),
                    entry_hint="entry_1",
                    replace=False,
                    reference_image=upload,
                )
            self.assertEqual(response["status"], web_server.text.OBJECT_BOUND_TO_ENTRY)
            register_mock.assert_called_once_with(
                web_server.ENTRY_TO_MODE["entry_1"], b"png-bytes"
            )
            capture_mock.assert_not_called()
            audit_mock.assert_called_once_with(
                "image_key_registered",
                entry="local_entry",
                source="web",
                binding_source="image_file",
            )

        asyncio.run(run())

    def test_register_key_without_image_uses_camera_capture(self):
        async def run():
            with (
                mock.patch.object(
                    web_server,
                    "_raw_gate_status",
                    return_value={
                        "registered_modes": {"dummy": False, "secret": False}
                    },
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "register_reference_from_image_bytes",
                ) as register_mock,
                mock.patch.object(
                    web_server,
                    "_capture_entry_binding",
                    return_value=(True, "bound"),
                ) as capture_mock,
                mock.patch.object(web_server, "audit_event") as audit_mock,
            ):
                response = await web_server.register_key(
                    self._register_key_request(),
                    entry_hint="entry_1",
                    replace=False,
                    reference_image=None,
                )
            self.assertEqual(response["status"], web_server.text.OBJECT_BOUND_TO_ENTRY)
            capture_mock.assert_called_once_with(web_server.ENTRY_TO_MODE["entry_1"])
            register_mock.assert_not_called()
            audit_mock.assert_called_once_with(
                "image_key_registered",
                entry="local_entry",
                source="web",
                binding_source="camera",
            )

        asyncio.run(run())

    def test_register_key_surfaces_unreadable_image_error(self):
        async def run():
            upload = UploadFile(filename="cue.png", file=_BytesFile(b"junk"))
            with (
                mock.patch.object(
                    web_server,
                    "_raw_gate_status",
                    return_value={
                        "registered_modes": {"dummy": False, "secret": False}
                    },
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "register_reference_from_image_bytes",
                    return_value=(False, web_server.text.AI_GATE_IMAGE_UNREADABLE),
                ),
                mock.patch.object(web_server, "audit_event") as audit_mock,
            ):
                response = await web_server.register_key(
                    self._register_key_request(),
                    entry_hint="entry_1",
                    replace=False,
                    reference_image=upload,
                )
            self.assertEqual(
                response["error"], web_server.text.AI_GATE_IMAGE_UNREADABLE
            )
            audit_mock.assert_not_called()

        asyncio.run(run())

    def test_register_key_masks_image_binding_failure_reasons(self):
        async def run():
            gate_messages = (
                web_server.text.AI_GATE_IMAGE_TOO_SIMPLE,
                web_server.text.AI_GATE_CUES_TOO_SIMILAR,
                web_server.text.AI_GATE_SAVE_FAILED,
            )
            responses = []
            for gate_message in gate_messages:
                upload = UploadFile(filename="cue.png", file=_BytesFile(b"png"))
                with (
                    mock.patch.object(
                        web_server,
                        "_raw_gate_status",
                        return_value={
                            "registered_modes": {"dummy": False, "secret": False}
                        },
                    ),
                    mock.patch.object(
                        web_server.access_cue_service,
                        "register_reference_from_image_bytes",
                        return_value=(False, gate_message),
                    ),
                ):
                    responses.append(
                        await web_server.register_key(
                            self._register_key_request(),
                            entry_hint="entry_1",
                            replace=False,
                            reference_image=upload,
                        )
                    )
                web_server._rate_limit.clear()
            bodies = {tuple(sorted(response.items())) for response in responses}
            self.assertEqual(len(bodies), 1)
            error_message = responses[0]["error"]
            self.assertNotIn(error_message, gate_messages)

        asyncio.run(run())

    def test_register_key_rejects_oversized_image_upload(self):
        async def run():
            oversized = b"x" * (web_server.MAX_UPLOAD_BYTES + 1)
            upload = UploadFile(filename="cue.png", file=_BytesFile(oversized))
            with (
                mock.patch.object(
                    web_server,
                    "_raw_gate_status",
                    return_value={
                        "registered_modes": {"dummy": False, "secret": False}
                    },
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "register_reference_from_image_bytes",
                ) as register_mock,
            ):
                with self.assertRaises(HTTPException) as ctx:
                    await web_server.register_key(
                        self._register_key_request(),
                        entry_hint="entry_1",
                        replace=False,
                        reference_image=upload,
                    )
            self.assertEqual(ctx.exception.status_code, 413)
            register_mock.assert_not_called()

        asyncio.run(run())

    def test_register_key_with_image_still_requires_replace_for_bound_entry(self):
        async def run():
            upload = UploadFile(filename="cue.png", file=_BytesFile(b"png-bytes"))
            registered = {
                "registered_modes": {
                    web_server.ENTRY_TO_MODE["entry_1"]: True,
                    web_server.ENTRY_TO_MODE["entry_2"]: False,
                }
            }
            with (
                mock.patch.object(
                    web_server, "_raw_gate_status", return_value=registered
                ),
                mock.patch.object(
                    web_server.access_cue_service,
                    "register_reference_from_image_bytes",
                ) as register_mock,
            ):
                response = await web_server.register_key(
                    self._register_key_request(),
                    entry_hint="entry_1",
                    replace=False,
                    reference_image=upload,
                )
            self.assertEqual(response["error"], web_server.text.ENTRY_ALREADY_BOUND)
            register_mock.assert_not_called()

        asyncio.run(run())


def _asgi_request(method, path, *, headers=None, cookies=None, body=b"", query=""):
    """Drive the ASGI app directly so routing and dependencies really execute.

    Route-shape assertions cannot catch an inert dependency, which is exactly
    how the unauthenticated surfaces survived review, so these tests exercise
    the real request path instead.  No lifespan events run, so the server does
    not touch the state directory.
    """
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        jar = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw_headers.append((b"cookie", jar.encode()))
    if body:
        raw_headers.append((b"content-type", b"application/x-www-form-urlencoded"))
        raw_headers.append((b"content-length", str(len(body)).encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    captured = {"status": None, "headers": [], "body": b""}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = message["headers"]
        elif message["type"] == "http.response.body":
            captured["body"] += message.get("body", b"")

    asyncio.run(web_server.app(scope, receive, send))
    captured["text"] = captured["body"].decode("utf-8", "replace")
    captured["set_cookie"] = [
        value.decode()
        for name, value in captured["headers"]
        if name.lower() == b"set-cookie"
    ]
    captured["location"] = next(
        (
            value.decode()
            for name, value in captured["headers"]
            if name.lower() == b"location"
        ),
        "",
    )
    return captured


class WebUIPageSessionGateTests(unittest.TestCase):
    """GHSA-2gm6-2phc-wv26 follow-up: the WebUI must authenticate page access.

    Advisory findings 1-3: `_ui_unlocked()` was inert, the mutation token was
    rendered into unauthenticated page HTML, and `/video_feed` had no real gate.
    """

    def setUp(self):
        self._clear()

    def tearDown(self):
        self._clear()

    def _clear(self):
        web_server._rate_limit.clear()
        web_server._restricted_sessions.clear()
        web_server._ui_sessions.clear()
        web_server._unlock_attempts._state.clear()
        web_server._access_attempts._state.clear()

    def _unlocked_cookies(self, client_id="127.0.0.1"):
        return {web_server.UI_SESSION_COOKIE: web_server._create_ui_session(client_id)}

    # ── Finding 1: the page-level gate is no longer a no-op ────────────

    def test_ui_unlocked_is_false_without_session_cookie(self):
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), cookies={})
        self.assertFalse(web_server._ui_unlocked(request))

    def test_ui_session_is_bound_to_the_issuing_client(self):
        token = web_server._create_ui_session("127.0.0.1")
        other_client = SimpleNamespace(
            client=SimpleNamespace(host="10.0.0.9"),
            cookies={web_server.UI_SESSION_COOKIE: token},
        )
        self.assertFalse(web_server._ui_unlocked(other_client))

    def test_expired_ui_session_is_rejected_and_dropped(self):
        token = web_server._create_ui_session("127.0.0.1")
        web_server._ui_sessions[token]["expires_at"] = time.time() - 1
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={web_server.UI_SESSION_COOKIE: token},
        )
        self.assertFalse(web_server._ui_unlocked(request))
        self.assertNotIn(token, web_server._ui_sessions)

    def test_forged_session_cookie_is_rejected(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={web_server.UI_SESSION_COOKIE: "not-a-real-session"},
        )
        self.assertFalse(web_server._ui_unlocked(request))

    def test_locked_page_request_redirects_to_unlock_not_home(self):
        response = _asgi_request("GET", "/")
        self.assertEqual(response["status"], 303)
        self.assertEqual(response["location"], "/unlock")

    def test_every_page_route_redirects_to_unlock_while_locked(self):
        for path in (
            "/",
            "/store",
            "/retrieve",
            "/maintenance",
            "/maintenance/entries",
            "/emergency",
        ):
            with self.subTest(path=path):
                response = _asgi_request("GET", path)
                self.assertEqual(response["status"], 303)
                self.assertEqual(response["location"], "/unlock")

    def test_operator_pages_reject_locked_requests(self):
        for path in (
            "/operator/doctor",
            "/operator/audit",
            "/operator/guided",
            "/operator/inspect",
        ):
            with self.subTest(path=path):
                response = _asgi_request(
                    "GET",
                    path,
                    headers={"X-Phasmid-Token": web_server.WEB_TOKEN},
                )
                self.assertEqual(response["status"], 423)

    # ── Finding 2: the mutation token is never in an unauthenticated body ──

    def test_unauthenticated_page_request_does_not_leak_mutation_token(self):
        for path in ("/", "/store", "/retrieve", "/maintenance", "/emergency"):
            with self.subTest(path=path):
                response = _asgi_request("GET", path)
                self.assertNotIn(web_server.WEB_TOKEN, response["text"])

    def test_unlock_page_does_not_render_the_mutation_token(self):
        response = _asgi_request("GET", "/unlock")
        self.assertEqual(response["status"], 200)
        self.assertNotIn(web_server.WEB_TOKEN, response["text"])

    def test_template_context_withholds_token_until_unlocked(self):
        locked = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), cookies={})
        self.assertEqual(web_server._template_context(locked)["web_token"], "")

        unlocked = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies=self._unlocked_cookies(),
        )
        self.assertEqual(
            web_server._template_context(unlocked)["web_token"],
            web_server.WEB_TOKEN,
        )

    def test_unlocked_page_renders_the_mutation_token_for_the_ui(self):
        response = _asgi_request("GET", "/", cookies=self._unlocked_cookies())
        self.assertEqual(response["status"], 200)
        self.assertIn(web_server.WEB_TOKEN, response["text"])

    # ── Finding 3: /video_feed and /status are authenticated ───────────

    def test_video_feed_rejects_locked_request(self):
        response = _asgi_request("GET", "/video_feed")
        self.assertEqual(response["status"], 423)

    def test_status_rejects_locked_request(self):
        response = _asgi_request("GET", "/status")
        self.assertEqual(response["status"], 423)

    # ── Unlock flow ────────────────────────────────────────────────────

    def test_unlock_with_correct_token_issues_httponly_session_cookie(self):
        response = _asgi_request(
            "POST",
            "/unlock",
            body=urllib.parse.urlencode({"token": web_server.WEB_TOKEN}).encode(),
        )
        self.assertEqual(response["status"], 303)
        self.assertEqual(response["location"], "/")
        cookie = next(
            value
            for value in response["set_cookie"]
            if value.startswith(web_server.UI_SESSION_COOKIE)
        )
        self.assertIn("HttpOnly", cookie)
        self.assertIn("samesite=strict", cookie.lower())
        self.assertNotIn(web_server.WEB_TOKEN, cookie)

    def test_unlock_with_wrong_token_issues_no_session(self):
        response = _asgi_request(
            "POST",
            "/unlock",
            body=urllib.parse.urlencode({"token": "wrong-token"}).encode(),
        )
        self.assertEqual(response["status"], 303)
        self.assertEqual(response["location"], "/unlock?rejected=1")
        self.assertEqual(response["set_cookie"], [])
        self.assertEqual(web_server._ui_sessions, {})

    def test_unlock_locks_out_after_repeated_wrong_tokens(self):
        limiter = web_server.AttemptLimiter(
            max_failures=2, lockout_seconds=60, clock=lambda: 1000
        )
        body = urllib.parse.urlencode({"token": "wrong-token"}).encode()
        with mock.patch.object(web_server, "_unlock_attempts", limiter):
            _asgi_request("POST", "/unlock", body=body)
            _asgi_request("POST", "/unlock", body=body)
            blocked = _asgi_request(
                "POST",
                "/unlock",
                body=urllib.parse.urlencode({"token": web_server.WEB_TOKEN}).encode(),
            )
        self.assertEqual(blocked["status"], 429)
        self.assertEqual(web_server._ui_sessions, {})

    def test_lock_drops_page_and_restricted_sessions(self):
        cookies = self._unlocked_cookies()
        response = _asgi_request("POST", "/lock", cookies=cookies)
        self.assertEqual(response["status"], 303)
        self.assertEqual(response["location"], "/unlock")
        self.assertEqual(web_server._ui_sessions, {})

    # ── Finding 4 / the chained destructive path ───────────────────────

    def test_public_phrases_do_not_reach_destructive_actions_while_locked(self):
        """GET / then POST the public phrases must not reach silent_brick()."""
        harvest = _asgi_request("GET", "/")
        self.assertNotIn(web_server.WEB_TOKEN, harvest["text"])

        with (
            mock.patch.object(web_server.vault, "silent_brick") as silent_brick,
            mock.patch.object(web_server.vault, "purge_other_mode") as purge,
        ):
            confirm = _asgi_request(
                "POST",
                "/restricted/confirm",
                headers={"X-Phasmid-Token": web_server.WEB_TOKEN},
                body=urllib.parse.urlencode(
                    {"confirmation": web_server.RESTRICTED_CONFIRMATION_PHRASE}
                ).encode(),
            )
            brick = _asgi_request(
                "POST",
                "/emergency/brick",
                headers={"X-Phasmid-Token": web_server.WEB_TOKEN},
                body=urllib.parse.urlencode(
                    {"confirmation": web_server.EMERGENCY_BRICK_PHRASE}
                ).encode(),
            )

        self.assertEqual(confirm["status"], 423)
        self.assertEqual(brick["status"], 423)
        self.assertEqual(web_server._restricted_sessions, {})
        silent_brick.assert_not_called()
        purge.assert_not_called()

    def test_panic_route_stays_concealed_and_inert_while_locked(self):
        with mock.patch.object(web_server.vault, "silent_brick") as silent_brick:
            response = _asgi_request(
                "POST",
                "/emergency/panic",
                headers={"X-Phasmid-Token": web_server.WEB_TOKEN},
                body=urllib.parse.urlencode({"secret_trigger": "BRICK"}).encode(),
            )
        self.assertEqual(response["status"], 404)
        silent_brick.assert_not_called()


class RestrictedPhraseAuthorizationTests(unittest.TestCase):
    """Advisory finding 4: confirmation phrases are typo guards, not credentials."""

    def test_correct_phrase_alone_does_not_authorize_a_restricted_action(self):
        policy = web_server.RESTRICTED_ACTION_POLICIES["clear_local_access_path"]
        with self.assertRaises(RestrictedActionRejected):
            evaluate_restricted_action(
                policy,
                capability_allowed=True,
                restricted_confirmed=False,
                confirmation=policy.confirmation_phrase,
            )
        with self.assertRaises(RestrictedActionRejected):
            evaluate_restricted_action(
                policy,
                capability_allowed=False,
                restricted_confirmed=True,
                confirmation=policy.confirmation_phrase,
            )

    def test_every_web_restricted_route_requires_more_than_the_phrase(self):
        """No route may treat a public phrase as its only server-side gate."""
        gated = {
            "/purge_other": "clear_unmatched_entry",
            "/emergency/brick": "clear_local_access_path",
            "/emergency/initialize": "initialize_container",
            "/emergency/panic": "rapid_local_clear",
        }
        for path, action_id in gated.items():
            with self.subTest(path=path):
                route = next(
                    route
                    for route in web_server.app.routes
                    if getattr(route, "path", None) == path
                )
                dependency_names = {
                    item.call.__name__ for item in route.dependant.dependencies
                }
                self.assertIn("require_web_token", dependency_names)

                policy = web_server.RESTRICTED_ACTION_POLICIES[action_id]
                # A phrase-only policy would be authorization by public constant.
                self.assertTrue(
                    policy.require_restricted_confirmation
                    or path == "/emergency/panic",
                    f"{action_id} relies on its public phrase alone",
                )

    def test_rapid_local_clear_is_gated_by_the_page_session_not_the_phrase(self):
        """`rapid_local_clear` skips restricted confirmation, so the session gate
        is the control that keeps its public phrase from being sufficient."""
        policy = web_server.RESTRICTED_ACTION_POLICIES["rapid_local_clear"]
        self.assertFalse(policy.require_restricted_confirmation)

        source = inspect.getsource(web_server.web_panic_trigger)
        self.assertIn("_ui_unlocked(request)", source)


class _BytesFile:
    def __init__(self, content):
        self._content = content
        self._offset = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._content) - self._offset
        end = min(self._offset + size, len(self._content))
        chunk = self._content[self._offset : end]
        self._offset = end
        return chunk

    def close(self):
        pass


if __name__ == "__main__":
    unittest.main()
