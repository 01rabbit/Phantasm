import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid import strings, web_server
from phasmid.capabilities import Capability
from phasmid.context_profile import (
    BUILT_IN_PROFILES,
    get_profile,
    validate_against_profile,
)
from phasmid.dummy_generator import DummyGeneratorConfig, generate_dummy_dataset
from phasmid.restricted_actions import (
    RestrictedActionPolicy,
    RestrictedActionRejected,
    evaluate_restricted_action,
)
from phasmid.standby_state import (
    InvalidTransitionError,
    StandbyState,
    StandbyStateMachine,
)

SCENARIO_PATH = os.path.join(ROOT, "tests", "scenarios", "restricted_flows.json")
HARDWARE_AVAILABLE = os.environ.get("RUN_HARDWARE_TESTS", "0") == "1"
hardware_only = unittest.skipUnless(HARDWARE_AVAILABLE, "requires RUN_HARDWARE_TESTS=1")


def load_scenarios():
    with open(SCENARIO_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_repo_text(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


class RestrictedFlowScenarioTests(unittest.TestCase):
    def setUp(self):
        # Same reason as WebServerBoundaryTests: the restricted-route
        # scenarios reach active_vault(), which resolves through the Vessel
        # registry, so an unisolated run depends on the Vessels registered on
        # the machine rather than on the scenario definitions.
        self._isolated_dirs = tempfile.TemporaryDirectory()
        root = self._isolated_dirs.name
        self._isolated_env = mock.patch.dict(
            os.environ,
            {
                "PHASMID_CONFIG_DIR": os.path.join(root, "config"),
                "PHASMID_STATE_DIR": os.path.join(root, "state"),
            },
        )
        self._isolated_env.start()
        self.addCleanup(self._isolated_dirs.cleanup)
        self.addCleanup(self._isolated_env.stop)

    def tearDown(self):
        web_server._rate_limit.clear()
        web_server._restricted_sessions.clear()
        web_server._ui_sessions.clear()

    def _unlocked_request(self, host="127.0.0.1", **extra):
        """A request that has already cleared the WebUI page-session gate."""
        return SimpleNamespace(
            client=SimpleNamespace(host=host),
            cookies={web_server.UI_SESSION_COOKIE: web_server._create_ui_session(host)},
            **extra,
        )

    def test_required_scenarios_are_defined(self):
        scenario_ids = {scenario["id"] for scenario in load_scenarios()}
        self.assertEqual(
            {
                "hidden-restricted-route-before-confirmation",
                "restricted-action-without-password-reentry",
                "object-cue-mismatch-before-retrieve",
                "field-mode-maintenance-without-confirmation",
                "container-initialization-after-valid-confirmation",
                "local-access-path-clear-after-valid-confirmation",
                "stale-restricted-session-rejection",
                "rapid-local-clear-without-confirmation",
            },
            scenario_ids,
        )

    def test_scenarios_reference_documented_procedures(self):
        for scenario in load_scenarios():
            with self.subTest(scenario=scenario["id"]):
                refs = scenario.get("procedure_refs")
                self.assertTrue(refs, "scenario must define procedure_refs")
                for ref in refs:
                    with self.subTest(path=ref["path"]):
                        doc = read_repo_text(ref["path"])
                        self.assertIn(ref["text"], doc)

    def test_policy_scenarios(self):
        scenarios = [
            scenario
            for scenario in load_scenarios()
            if scenario["kind"] == "restricted_policy"
        ]
        policies = {
            "clear_unmatched_entry": RestrictedActionPolicy(
                action_id="clear_unmatched_entry",
                capability=Capability.RESTRICTED_ACTION,
                confirmation_phrase="CLEAR LOCAL ENTRY",
            ),
            "password_guarded_action": RestrictedActionPolicy(
                action_id="password_guarded_action",
                capability=Capability.RESTRICTED_ACTION,
                confirmation_phrase="CONFIRM",
                require_password_reentry=True,
            ),
            "rapid_local_clear": RestrictedActionPolicy(
                action_id="rapid_local_clear",
                capability=Capability.RAPID_LOCAL_CLEAR,
                confirmation_phrase="BRICK",
                require_restricted_confirmation=False,
            ),
        }

        for scenario in scenarios:
            with self.subTest(scenario=scenario["id"]):
                with self.assertRaises(RestrictedActionRejected) as ctx:
                    evaluate_restricted_action(
                        policies[scenario["action"]],
                        capability_allowed=scenario["capability_allowed"],
                        restricted_confirmed=scenario["restricted_confirmed"],
                        confirmation=scenario["confirmation"],
                        password_reentered=scenario.get("password_reentered", True),
                    )
                self.assertEqual(ctx.exception.message, scenario["expected_error"])

    def test_object_cue_mismatch_before_retrieve(self):
        scenario = _scenario("object-cue-mismatch-before-retrieve")

        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/retrieve"),
            )
            with (
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
                response = await web_server.retrieve(request, password="pw")
            self.assertEqual(response["error"], scenario["expected_error"])

        asyncio.run(run())

    def test_field_mode_maintenance_scenario(self):
        async def run():
            request = self._unlocked_request()
            with (
                mock.patch.object(web_server, "field_mode_enabled", return_value=True),
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=False
                ),
            ):
                response = await web_server.maintenance_page(request)
            self.assertTrue(response.context["field_mode"])
            self.assertFalse(response.context["restricted_confirmed"])

        asyncio.run(run())

    def test_valid_restricted_route_scenarios(self):
        async def run():
            request = SimpleNamespace(
                client=SimpleNamespace(host="127.0.0.1"),
                url=SimpleNamespace(path="/emergency"),
            )
            with (
                mock.patch.object(
                    web_server, "_restricted_session_valid", return_value=True
                ),
                mock.patch.object(
                    web_server.vault, "format_container"
                ) as format_container,
                mock.patch.object(
                    web_server.access_cue_service,
                    "clear_references",
                    return_value=(True, "ok"),
                ),
                mock.patch.object(web_server.vault, "silent_brick") as silent_brick,
            ):
                init_response = await web_server.emergency_initialize(
                    request,
                    confirmation="INITIALIZE LOCAL CONTAINER",
                )
                clear_response = await web_server.emergency_brick(
                    request,
                    confirmation="CLEAR LOCAL ACCESS PATH",
                )

            format_container.assert_called_once_with(rotate_access_key=True)
            silent_brick.assert_called_once()
            self.assertEqual(init_response["status"], strings.CONTAINER_INITIALIZED)
            self.assertEqual(
                clear_response["status"], strings.LOCAL_ACCESS_PATH_CLEARED
            )

        asyncio.run(run())

    def test_stale_restricted_session_rejection(self):
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            cookies={web_server.RESTRICTED_SESSION_COOKIE: "stale-token"},
        )
        web_server._restricted_sessions["stale-token"] = {
            "client_id": "127.0.0.1",
            "expires_at": time.time() - 1,
        }

        with self.assertRaises(HTTPException) as ctx:
            web_server.require_restricted_confirmation(request)

        self.assertEqual(ctx.exception.detail, strings.RESTRICTED_CONFIRMATION_REQUIRED)


class TestContextProfileToDatasetPipeline(unittest.TestCase):
    def test_all_built_in_profiles_produce_valid_dataset(self):
        for name in BUILT_IN_PROFILES:
            with self.subTest(profile=name):
                profile = get_profile(name)
                self.assertIsNotNone(profile)
                with tempfile.TemporaryDirectory() as tmpdir:
                    config = DummyGeneratorConfig(
                        target_size_bytes=1024 * 512,
                        occupancy_ratio=0.5,
                        profile=profile,
                        output_dir=tmpdir,
                    )
                    report = generate_dummy_dataset(config)
                    self.assertGreater(report.files_created, 0)
                    self.assertGreater(report.total_bytes_written, 0)

    def test_dataset_plausibility_validates_against_source_profile(self):
        profile = get_profile("travel")
        self.assertIsNotNone(profile)
        with tempfile.TemporaryDirectory() as tmpdir:
            config = DummyGeneratorConfig(
                target_size_bytes=1024 * 256,
                occupancy_ratio=0.8,
                profile=profile,
                output_dir=tmpdir,
            )
            report = generate_dummy_dataset(config)
            result = validate_against_profile(
                profile=profile,
                container_size_bytes=config.target_size_bytes,
                dummy_size_bytes=report.total_bytes_written,
                file_count=report.files_created,
                extension_distribution=report.extension_distribution,
            )
            self.assertIsNotNone(result)

    def test_dataset_uses_no_weak_randomness(self):
        import inspect

        import phasmid.dummy_generator as mod

        source = inspect.getsource(mod)
        self.assertNotIn("import random", source)
        self.assertNotIn("random.random(", source)
        self.assertNotIn("random.randint(", source)


class TestStandbyStateMachineIntegration(unittest.TestCase):
    def test_full_lifecycle_active_to_sealed_to_active(self):
        sm = StandbyStateMachine()
        self.assertEqual(sm.state, StandbyState.ACTIVE)
        sm.trigger_standby()
        self.assertEqual(sm.state, StandbyState.SEALED)
        sm.recover()
        self.assertEqual(sm.state, StandbyState.ACTIVE)

    def test_sealed_to_dummy_disclosure_and_back(self):
        sm = StandbyStateMachine()
        sm.trigger_standby()
        sm.enter_dummy_disclosure()
        self.assertEqual(sm.state, StandbyState.DUMMY_DISCLOSURE)
        sm.seal_dummy()
        self.assertEqual(sm.state, StandbyState.SEALED)

    def test_status_dict_contains_no_sensitive_labels(self):
        sm = StandbyStateMachine()
        sm.trigger_standby()
        status = sm.status_dict()
        status_str = str(status).lower()
        for term in ("passphrase", "vault", "key", "entry", "true", "real"):
            self.assertNotIn(term, status_str, f"status_dict exposed term: {term!r}")

    def test_trigger_standby_is_idempotent_when_already_sealed(self):
        sm = StandbyStateMachine()
        sm.trigger_standby()
        with self.assertRaises(InvalidTransitionError):
            sm.trigger_standby()
        self.assertEqual(sm.state, StandbyState.SEALED)

    def test_recover_requires_sealed_state(self):
        sm = StandbyStateMachine()
        with self.assertRaises(InvalidTransitionError):
            sm.recover()
        self.assertEqual(sm.state, StandbyState.ACTIVE)


class TestRecognitionRoutingIntegration(unittest.TestCase):
    def setUp(self):
        os.environ.pop("PHASMID_RECOGNITION_MODE", None)
        os.environ.pop("PHASMID_TRUE_UNLOCK_THRESHOLD", None)
        os.environ.pop("PHASMID_DUMMY_FALLBACK_THRESHOLD", None)

    def tearDown(self):
        os.environ.pop("PHASMID_RECOGNITION_MODE", None)
        os.environ.pop("PHASMID_TRUE_UNLOCK_THRESHOLD", None)
        os.environ.pop("PHASMID_DUMMY_FALLBACK_THRESHOLD", None)

    def test_coercion_safe_mode_routes_low_confidence_to_controlled_disclosure(self):
        from phasmid.config import (
            dummy_fallback_threshold,
            recognition_mode,
            true_unlock_threshold,
        )

        os.environ["PHASMID_RECOGNITION_MODE"] = "coercion_safe"
        os.environ["PHASMID_TRUE_UNLOCK_THRESHOLD"] = "0.85"
        os.environ["PHASMID_DUMMY_FALLBACK_THRESHOLD"] = "0.40"

        self.assertEqual(recognition_mode(), "coercion_safe")
        self.assertAlmostEqual(true_unlock_threshold(), 0.85)
        self.assertAlmostEqual(dummy_fallback_threshold(), 0.40)

        score = 0.30
        if score <= dummy_fallback_threshold():
            route = "controlled_disclosure"
        elif score >= true_unlock_threshold():
            route = "unlock"
        else:
            route = "deny"
        self.assertEqual(route, "controlled_disclosure")

    def test_strict_mode_denies_low_confidence(self):
        from phasmid.config import recognition_mode

        os.environ["PHASMID_RECOGNITION_MODE"] = "strict"
        self.assertEqual(recognition_mode(), "strict")

    def test_standby_state_unaffected_by_recognition_mode_config(self):
        os.environ["PHASMID_RECOGNITION_MODE"] = "coercion_safe"
        sm = StandbyStateMachine()
        self.assertEqual(sm.state, StandbyState.ACTIVE)
        sm.trigger_standby()
        self.assertEqual(sm.state, StandbyState.SEALED)


@hardware_only
class TestPiZero2WCoercionSafeHardware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pi_host = os.environ.get("PHASMID_PI_HOST", "")
        if not cls.pi_host:
            raise unittest.SkipTest("PHASMID_PI_HOST not set")

    def _ssh(self, cmd: str, timeout: int = 30):
        import subprocess

        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", self.pi_host, cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr

    def test_pi_phasmid_import_succeeds(self):
        rc, _, err = self._ssh(
            "python3 -c 'import phasmid; print(phasmid.__version__)'"
        )
        self.assertEqual(rc, 0, f"phasmid import failed: {err}")

    def test_pi_context_profile_loads(self):
        rc, out, err = self._ssh(
            "python3 -c 'from phasmid.context_profile import get_profile; "
            'p = get_profile("travel"); print(p.profile_name)\''
        )
        self.assertEqual(rc, 0, f"context_profile import failed: {err}")
        self.assertIn("travel", out)

    def test_pi_standby_state_machine_runs(self):
        rc, out, err = self._ssh(
            "python3 -c 'from phasmid.standby_state import StandbyStateMachine; "
            "sm = StandbyStateMachine(); sm.trigger_standby(); print(sm.state.value)'"
        )
        self.assertEqual(rc, 0, f"standby_state failed: {err}")
        self.assertIn("sealed", out)

    def test_pi_dummy_generator_runs(self):
        rc, out, err = self._ssh(
            "python3 -c '"
            "import tempfile; "
            "from phasmid.context_profile import get_profile; "
            "from phasmid.dummy_generator import DummyGeneratorConfig, generate_dummy_dataset; "
            'p = get_profile("travel"); '
            "cfg = DummyGeneratorConfig(target_size_bytes=65536, occupancy_ratio=0.5, profile=p, output_dir=tempfile.mkdtemp()); "
            "r = generate_dummy_dataset(cfg); print(r.files_created)'"
        )
        self.assertEqual(rc, 0, f"dummy_generator failed: {err}")
        self.assertGreater(int(out.strip()), 0)

    def test_pi_recognition_mode_config(self):
        rc, out, err = self._ssh(
            "PHASMID_RECOGNITION_MODE=coercion_safe python3 -c "
            "'from phasmid.config import recognition_mode; print(recognition_mode())'"
        )
        self.assertEqual(rc, 0, f"recognition_mode config failed: {err}")
        self.assertIn("coercion_safe", out)


def _scenario(scenario_id):
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    raise AssertionError(f"scenario not found: {scenario_id}")


if __name__ == "__main__":
    unittest.main()
