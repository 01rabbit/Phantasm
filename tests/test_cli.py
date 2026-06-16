import contextlib
import io
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import cli


class CLITests(unittest.TestCase):
    def test_entry_labels_are_neutral(self):
        self.assertEqual(
            cli.display_mode_label(cli.gate.MODES[0]), "selected local entry"
        )
        self.assertEqual(
            cli.display_mode_label(cli.gate.MODES[1]), "selected local entry"
        )
        self.assertEqual(cli.display_mode_label("invalid"), "local entry")

    def test_resolve_mode(self):
        self.assertEqual(cli.resolve_mode("a"), cli.gate.MODES[0])
        self.assertEqual(cli.resolve_mode("b"), cli.gate.MODES[1])
        with self.assertRaises(ValueError):
            cli.resolve_mode("c")

    def test_show_loading(self):
        with unittest.mock.patch("time.sleep"):
            cli.show_loading("test", duration=0.1)

    def test_wait_for_camera_frame(self):
        with unittest.mock.patch("time.sleep"):
            # Case 1: Frame already exists
            with unittest.mock.patch.object(cli.gate, "lock"):
                cli.gate.latest_frame = object()
                self.assertTrue(cli._wait_for_camera_frame(timeout=0.1))

            # Case 2: Timeout
            cli.gate.latest_frame = None
            self.assertFalse(cli._wait_for_camera_frame(timeout=0.1))

    def test_wait_for_reference_match(self):
        with unittest.mock.patch("time.sleep"):
            # Case 1: Match already exists
            cli.gate.last_match_mode = "dummy"
            self.assertTrue(cli._wait_for_reference_match(timeout=0.1))
            self.assertTrue(
                cli._wait_for_reference_match(timeout=0.1, expected_mode="dummy")
            )
            self.assertFalse(
                cli._wait_for_reference_match(timeout=0.1, expected_mode="secret")
            )

            # Case 2: Timeout
            cli.gate.last_match_mode = "none"
            self.assertFalse(cli._wait_for_reference_match(timeout=0.1))

    def test_local_state_confirmation_language_is_neutral(self):
        output = io.StringIO()
        with (
            unittest.mock.patch.object(
                cli, "purge_confirmation_required", return_value=True
            ),
            unittest.mock.patch("builtins.input", return_value=""),
            contextlib.redirect_stdout(output),
        ):
            self.assertFalse(cli._confirm_purge_other_mode(cli.gate.MODES[0]))
        self.assertNotRegex(
            output.getvalue(),
            re.compile(r"profile|dummy|secret|decoy|truth|fake|real", re.I),
        )

    def test_object_registration_output_is_neutral(self):
        output = io.StringIO()
        with (
            unittest.mock.patch("builtins.input", return_value=""),
            unittest.mock.patch.object(
                cli.gate, "capture_reference", return_value=(True, "ok")
            ),
            unittest.mock.patch.object(
                cli, "_wait_for_reference_match", return_value=True
            ),
            contextlib.redirect_stdout(output),
        ):
            success, message = cli._register_reference_key(cli.gate.MODES[0])

        self.assertTrue(success)
        self.assertEqual(message, "Object access cue registered.")
        self.assertNotRegex(
            output.getvalue(),
            re.compile(
                r"profile|Entry A|Entry B|image key|registered image keys|Physical key|"
                r"other profile|other mode|DELETE Entry|TACTICAL|ARMED|Master Key|Biometric",
                re.I,
            ),
        )

    def test_cli_source_does_not_include_retired_user_visible_phrases(self):
        with open(cli.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("Entry A", source)
        self.assertNotIn("Entry B", source)
        self.assertNotIn("AMBIGUOUS KEY", source)
        self.assertNotIn("KEY NOT FOUND", source)
        self.assertNotIn("Performing Argon2id-based key derivation", source)

    def test_store_password_prompt_rejects_short_values(self):
        prompts = iter(["short", "another-short"])

        with unittest.mock.patch(
            "getpass.getpass", side_effect=lambda _: next(prompts)
        ):
            with self.assertRaises(ValueError) as ctx:
                cli._prompt_store_passwords()

        self.assertIn("at least", str(ctx.exception))

    def test_cli_retrieve_respects_attempt_lockout(self):
        output = io.StringIO()

        class LockedLimiter:
            def check(self, _scope):
                return type("Decision", (), {"allowed": False})()

        with (
            unittest.mock.patch.object(sys, "argv", ["phasmid", "retrieve"]),
            unittest.mock.patch.object(
                cli, "_wait_for_camera_frame", return_value=True
            ),
            unittest.mock.patch.object(cli.gate, "start"),
            unittest.mock.patch.object(cli.gate, "close"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "start"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "stop"),
            unittest.mock.patch.object(
                cli, "FileAttemptLimiter", return_value=LockedLimiter()
            ),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn("Access temporarily unavailable", output.getvalue())

    def test_startup_check_failure_is_neutral(self):
        output = io.StringIO()

        with unittest.mock.patch.object(
            cli, "ensure_crypto_self_tests", side_effect=cli.CryptoSelfTestError
        ):
            with contextlib.redirect_stdout(output):
                self.assertFalse(cli._run_startup_checks())

        self.assertIn("Startup check failed", output.getvalue())

    def test_cli_open_no_tui_uses_shared_workflow(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def open_vessel(self, path, face_id="face_a"):
                events.append(("open", path, face_id))
                return type(
                    "Result",
                    (),
                    {"vessel": type("Vessel", (), {"path": path, "open_count": 1})()},
                )()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(sys, "argv", ["phasmid", "open", "travel.vessel", "--no-tui", "--face", "face_b"]),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn(("open", "travel.vessel", "face_b"), events)
        self.assertIn("Vessel opened", output.getvalue())

    def test_cli_close_uses_shared_workflow(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def close_vessel(self, path):
                events.append(("close", path))
                return type("Result", (), {"vessel": type("Vessel", (), {"path": path})()})()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(sys, "argv", ["phasmid", "close", "travel.vessel"]),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn(("close", "travel.vessel"), events)
        self.assertIn("Vessel closed", output.getvalue())

    def test_cli_face_create_uses_shared_workflow(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def create_face(self, path, face_id, label=""):
                events.append(("face_create", path, face_id, label))
                return type(
                    "Result",
                    (),
                    {
                        "vessel": type("Vessel", (), {"path": path})(),
                        "face": type("Face", (), {"face_id": face_id})(),
                    },
                )()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(
                sys,
                "argv",
                ["phasmid", "face", "create", "travel.vessel", "--face", "face_b", "--label", "travel"],
            ),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn(("face_create", "travel.vessel", "face_b", "travel"), events)
        self.assertIn("Face ready", output.getvalue())

    def test_cli_plausibility_inspect_uses_shared_workflow(self):
        output = io.StringIO()
        events = []
        command_name = "dum" + "my"

        class FakeWorkflowService:
            def inspect_dummy_profile(self, path, face_id="face_a"):
                events.append(("inspect_plausibility", path, face_id))
                profile = type(
                    "Profile",
                    (),
                    {
                        "dummy_file_count": 6,
                        "dummy_total_size": 4096,
                        "occupancy_ratio": 0.15,
                        "plausibility_score": 72,
                        "plausibility_level": "HIGH",
                        "file_type_distribution": {"txt": 2, "pdf": 1},
                    },
                )()
                return type(
                    "Result",
                    (),
                    {
                        "face": type("Face", (), {"face_id": face_id})(),
                        "profile": profile,
                        "recommended_action": "Baseline profile is credible.",
                    },
                )()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(
                sys,
                "argv",
                ["phasmid", command_name, "inspect", "travel.vessel", "--face", "face_b"],
            ),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn(("inspect_plausibility", "travel.vessel", "face_b"), events)
        self.assertIn("Plausibility metadata ready", output.getvalue())

    def test_cli_file_add_uses_shared_workflow(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def wait_for_camera_frame(self):
                return True

            def add_file(
                self,
                vessel,
                input_path,
                open_passphrase,
                restricted_passphrase,
                selector="face_a",
                cue_sequence=None,
                capture_reference=False,
                object_image_path=None,
                camera_object=False,
                no_object_binding=False,
                emergency_password=None,
            ):
                events.append(
                    (
                        "file_add",
                        vessel,
                        input_path,
                        open_passphrase,
                        restricted_passphrase,
                        selector,
                        capture_reference,
                        object_image_path,
                        emergency_password,
                    )
                )
                return type(
                    "Result", (), {"input_path": Path(input_path), "vessel_path": Path(vessel)}
                )()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(
                cli, "_resolve_access_password", return_value="pw"
            ),
            unittest.mock.patch.object(sys, "argv", ["phasmid", "file", "add", "travel.vessel", "--face", "face_b", "--input", "note.txt"]),
            unittest.mock.patch.object(cli, "VesselWorkflowService", return_value=FakeWorkflowService()),
            unittest.mock.patch.object(cli.gate, "start"),
            unittest.mock.patch.object(cli.gate, "close"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "start"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "stop"),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        self.assertIn(("file_add", "travel.vessel", "note.txt", "pw", None, "face_b", True, None, None), events)
        self.assertIn("File added to selected face", output.getvalue())

    def test_cli_file_add_with_object_image_skips_camera(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def add_file(
                self,
                vessel,
                input_path,
                open_passphrase,
                restricted_passphrase,
                selector="face_a",
                cue_sequence=None,
                capture_reference=False,
                object_image_path=None,
                camera_object=False,
                no_object_binding=False,
                emergency_password=None,
            ):
                events.append(
                    (
                        "file_add",
                        vessel,
                        input_path,
                        selector,
                        capture_reference,
                        object_image_path,
                        camera_object,
                        no_object_binding,
                        emergency_password,
                    )
                )
                return type(
                    "Result", (), {"input_path": Path(input_path), "vessel_path": Path(vessel)}
                )()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(
                cli, "_resolve_access_password", return_value="pw"
            ),
            unittest.mock.patch.object(
                sys,
                "argv",
                [
                    "phasmid",
                    "file",
                    "add",
                    "travel.vessel",
                    "--face",
                    "face_b",
                    "--input",
                    "note.txt",
                    "--object-image",
                    "object.png",
                ],
            ),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            unittest.mock.patch.object(cli.gate, "start") as gate_start,
            unittest.mock.patch.object(cli.gate, "close"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "start"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "stop"),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        gate_start.assert_not_called()
        self.assertIn(
            ("file_add", "travel.vessel", "note.txt", "face_b", False, "object.png", False, False, None),
            events,
        )

    def test_cli_emergency_destroy_face_uses_shared_workflow(self):
        output = io.StringIO()
        events = []

        class FakeWorkflowService:
            def destroy_face(
                self,
                vessel,
                emergency_password,
                selector="face_a",
                object_image_path=None,
                camera_object=False,
                confirmation="",
            ):
                events.append(
                    (
                        "destroy_face",
                        vessel,
                        emergency_password,
                        selector,
                        object_image_path,
                        confirmation,
                    )
                )
                return type("Result", (), {"face_id": selector})()

        with (
            unittest.mock.patch.object(
                cli, "apply_process_hardening", return_value=None
            ),
            unittest.mock.patch.object(cli, "require_volatile_state", return_value=None),
            unittest.mock.patch.object(cli, "_run_startup_checks", return_value=True),
            unittest.mock.patch.object(
                cli, "_resolve_required_emergency_password", return_value="burn"
            ),
            unittest.mock.patch.object(
                sys,
                "argv",
                [
                    "phasmid",
                    "emergency",
                    "destroy-face",
                    "travel.vessel",
                    "--face",
                    "face_b",
                    "--object-image",
                    "object.png",
                    "--confirm",
                    "DESTROY FACE",
                ],
            ),
            unittest.mock.patch.object(
                cli, "VesselWorkflowService", return_value=FakeWorkflowService()
            ),
            unittest.mock.patch.object(cli.gate, "start") as gate_start,
            unittest.mock.patch.object(cli.gate, "close"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "start"),
            unittest.mock.patch.object(cli.EmergencyDaemon, "stop"),
            contextlib.redirect_stdout(output),
        ):
            cli.main()

        gate_start.assert_not_called()
        self.assertIn(
            ("destroy_face", "travel.vessel", "burn", "face_b", "object.png", "DESTROY FACE"),
            events,
        )
        self.assertIn("Face destroyed explicitly", output.getvalue())


if __name__ == "__main__":
    unittest.main()
