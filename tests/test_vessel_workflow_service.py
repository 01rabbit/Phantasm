from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.services import vessel_service as vessel_service_mod
from phasmid.services.inspection_service import InspectionService
from phasmid.services.vessel_workflow_service import VesselWorkflowService


class VesselWorkflowServiceTests(unittest.TestCase):
    def _patch_registry_dir(self, tmpdir: str):
        return mock.patch.object(vessel_service_mod, "config_dir", lambda: Path(tmpdir))

    def _write_object_image(self, path: Path, color: tuple[int, int, int]) -> None:
        image = np.full((96, 96, 3), color, dtype=np.uint8)
        cv2.rectangle(image, (16, 16), (80, 80), (255, 255, 255), 3)
        cv2.line(image, (0, 95), (95, 0), (0, 0, 0), 2)
        ok = cv2.imwrite(str(path), image)
        self.assertTrue(ok)

    def test_create_store_and_recover_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            output_path = Path(tmpdir) / "recovered.txt"
            input_path.write_text("field note", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                created = svc.create_vessel(vessel_path, "8M")
                self.assertTrue(created.vessel_path.exists())

                cue_sequence = ["reference_dummy_matched"]
                stored = svc.store_file(
                    vessel_path,
                    input_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="a",
                    cue_sequence=cue_sequence,
                )
                self.assertEqual(stored.bytes_stored, len(b"field note"))

                recovered = svc.retrieve_file(
                    vessel_path,
                    "correct horse battery",
                    output_path=output_path,
                    cue_sequence=cue_sequence,
                )
                self.assertEqual(recovered.bytes_retrieved, len(b"field note"))
                self.assertEqual(output_path.read_text(encoding="utf-8"), "field note")

    def test_first_add_initializes_face_a_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            image_path = Path(tmpdir) / "object-a.png"
            input_path.write_text("field note", encoding="utf-8")
            self._write_object_image(image_path, (20, 120, 220))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                stored = svc.add_file(
                    vessel_path,
                    input_path,
                    "access-pw",
                    "emergency-pw",
                    selector="face_a",
                    object_image_path=str(image_path),
                )
                self.assertEqual(stored.bytes_stored, len(b"field note"))
                inspection = InspectionService().inspect(vessel_path)
                labels = {field.label: field.value for field in inspection.fields}
                self.assertIn("face_a:credentials=ready:object=ready", labels["Face Credential State"])

    def test_first_add_initializes_face_b_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            image_path = Path(tmpdir) / "object-b.png"
            input_path.write_text("field note", encoding="utf-8")
            self._write_object_image(image_path, (220, 40, 40))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                stored = svc.add_file(
                    vessel_path,
                    input_path,
                    "access-pw",
                    "emergency-pw",
                    selector="face_b",
                    object_image_path=str(image_path),
                )
                self.assertEqual(stored.mode, "secret")
                listing = svc.list_files(
                    vessel_path,
                    "access-pw",
                    selector="face_b",
                    object_image_path=str(image_path),
                )
                self.assertEqual([item.name for item in listing.files], ["note.txt"])

    def test_create_rejects_existing_vessel_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                with self.assertRaises(FileExistsError):
                    svc.create_vessel(vessel_path, "8M")

    def test_newly_created_vessel_is_inspectable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")

            inspection = InspectionService().inspect(vessel_path)
            self.assertTrue(inspection.ok)
            labels = {field.label: field.value for field in inspection.fields}
            self.assertEqual(labels["Recognized Type"], "unknown")
            self.assertEqual(labels["Vessel Claim"], "not asserted")

    def test_lifecycle_create_open_close_reopen_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M", label="travel")

                opened = svc.open_vessel(vessel_path)
                self.assertTrue(opened.vessel.is_open)
                self.assertEqual(opened.vessel.open_count, 1)
                self.assertEqual(opened.vessel.label, "travel")
                self.assertTrue(opened.vessel.last_opened_at)

                closed = svc.close_vessel(vessel_path)
                self.assertFalse(closed.vessel.is_open)
                self.assertEqual(closed.vessel.open_count, 1)
                self.assertEqual(closed.vessel.label, "travel")
                self.assertTrue(closed.vessel.last_closed_at)

                reopened = svc.open_vessel(vessel_path)
                self.assertTrue(reopened.vessel.is_open)
                self.assertEqual(reopened.vessel.open_count, 2)
                self.assertEqual(reopened.vessel.label, "travel")
                self.assertEqual(reopened.vessel.last_closed_at, closed.vessel.last_closed_at)

                inspection = InspectionService().inspect(vessel_path)
                self.assertTrue(inspection.ok)

    def test_face_lifecycle_persists_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            output_path = Path(tmpdir) / "recovered.txt"
            input_path.write_text("field note", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                face = svc.create_face(vessel_path, "face_b", label="travel")
                self.assertEqual(face.face.face_id, "face_b")
                self.assertEqual(face.face.label, "travel")
                self.assertTrue(face.face.created_at)

                opened = svc.open_vessel(vessel_path, face_id="face_b")
                opened_face = next(face for face in opened.vessel.faces if face.face_id == "face_b")
                self.assertEqual(opened_face.status, "open")
                self.assertTrue(opened_face.last_accessed)

                cue_sequence = ["reference_secret_matched"]
                stored = svc.store_file(
                    vessel_path,
                    input_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_b",
                    cue_sequence=cue_sequence,
                )
                self.assertEqual(stored.mode, "secret")

                closed = svc.close_vessel(vessel_path)
                closed_face = next(face for face in closed.vessel.faces if face.face_id == "face_b")
                self.assertEqual(closed_face.status, "occupied")
                self.assertEqual(closed_face.occupancy, len(b"field note"))
                self.assertEqual(closed_face.file_count, 1)

                reopened = svc.open_vessel(vessel_path, face_id="face_b")
                reopened_face = next(face for face in reopened.vessel.faces if face.face_id == "face_b")
                self.assertEqual(reopened_face.label, "travel")
                self.assertEqual(reopened_face.occupancy, len(b"field note"))

                recovered = svc.retrieve_file(
                    vessel_path,
                    "correct horse battery",
                    output_path=output_path,
                    selector="face_b",
                    cue_sequence=cue_sequence,
                )
                self.assertEqual(recovered.mode, "secret")
                inspection = InspectionService().inspect(vessel_path)
                self.assertTrue(inspection.ok)
                labels = {field.label: field.value for field in inspection.fields}
                self.assertEqual(labels["Face Count"], "2")
                self.assertIn("face_b:occupied:1 files", labels["Face Registry"])
                self.assertIn("face_b:LOW", labels["Plausibility Summary"])

    def test_face_bound_storage_isolated_between_faces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            file_x = Path(tmpdir) / "x.txt"
            file_y = Path(tmpdir) / "y.txt"
            out_x = Path(tmpdir) / "x.txt"
            out_y = Path(tmpdir) / "y.txt"
            file_x.write_text("alpha", encoding="utf-8")
            file_y.write_text("bravo", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                cue_a = ["reference_dummy_matched"]
                cue_b = ["reference_secret_matched"]

                svc.add_file(
                    vessel_path,
                    file_x,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                files_a = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                self.assertEqual([file.name for file in files_a.files], ["x.txt"])
                with self.assertRaisesRegex(ValueError, "credentials not initialized"):
                    svc.list_files(
                        vessel_path,
                        "correct horse battery",
                        selector="face_b",
                        cue_sequence=cue_b,
                    )

                svc.add_file(
                    vessel_path,
                    file_y,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_b",
                    cue_sequence=cue_b,
                )
                files_a = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                files_b = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_b",
                    cue_sequence=cue_b,
                )
                self.assertEqual([file.name for file in files_a.files], ["x.txt"])
                self.assertEqual([file.name for file in files_b.files], ["y.txt"])

                svc.close_vessel(vessel_path)
                svc.open_vessel(vessel_path, face_id="face_a")
                recovered_x = svc.retrieve_file(
                    vessel_path,
                    "correct horse battery",
                    output_path=out_x,
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                self.assertEqual(recovered_x.filename, "x.txt")
                self.assertEqual(out_x.read_text(encoding="utf-8"), "alpha")

                svc.open_vessel(vessel_path, face_id="face_b")
                recovered_y = svc.retrieve_file(
                    vessel_path,
                    "correct horse battery",
                    output_path=out_y,
                    selector="face_b",
                    cue_sequence=cue_b,
                )
                self.assertEqual(recovered_y.filename, "y.txt")
                self.assertEqual(out_y.read_text(encoding="utf-8"), "bravo")

                svc.remove_file(
                    vessel_path,
                    "x.txt",
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                files_a = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=cue_a,
                )
                files_b = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_b",
                    cue_sequence=cue_b,
                )
                self.assertEqual(files_a.files, [])
                self.assertEqual([file.name for file in files_b.files], ["y.txt"])

    def test_dummy_profile_generation_is_face_scoped_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")

                generated = svc.generate_dummy_profile(
                    vessel_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    target_occupancy="15%",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertGreater(generated.profile.dummy_file_count, 0)
                self.assertGreater(generated.profile.dummy_total_size, 0)
                self.assertGreater(generated.profile.occupancy_ratio, 0.0)
                self.assertIn(generated.profile.plausibility_level, {"MEDIUM", "HIGH"})

                repeated = svc.inspect_dummy_profile(vessel_path, "face_a")
                self.assertEqual(
                    repeated.profile.plausibility_score,
                    generated.profile.plausibility_score,
                )
                self.assertEqual(
                    repeated.profile.file_type_distribution,
                    generated.profile.file_type_distribution,
                )

                other_face = svc.inspect_dummy_profile(vessel_path, "face_b")
                self.assertEqual(other_face.profile.dummy_file_count, 0)
                self.assertEqual(other_face.profile.occupancy_ratio, 0.0)

                inspection = InspectionService().inspect(vessel_path)
                labels = {field.label: field.value for field in inspection.fields}
                self.assertIn("face_a:", labels["Plausibility Summary"])
                self.assertNotIn("generated_", labels["Plausibility Summary"])

    def test_dummy_profile_clear_preserves_manual_face_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_path = Path(tmpdir) / "note.txt"
            note_path.write_text("field note", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                cue_sequence = ["reference_dummy_matched"]
                svc.add_file(
                    vessel_path,
                    note_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=cue_sequence,
                )
                svc.generate_dummy_profile(
                    vessel_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    size_spec="1M",
                    cue_sequence=cue_sequence,
                )

                cleared = svc.clear_dummy_profile(
                    vessel_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=cue_sequence,
                )
                self.assertEqual(cleared.profile.dummy_file_count, 0)
                files = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=cue_sequence,
                )
                self.assertEqual([item.name for item in files.files], ["note.txt"])

    def test_image_file_object_binding_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_path = Path(tmpdir) / "note.txt"
            first_image = Path(tmpdir) / "object-a.png"
            second_image = Path(tmpdir) / "object-b.png"
            note_path.write_text("field note", encoding="utf-8")
            self._write_object_image(first_image, (20, 120, 220))
            self._write_object_image(second_image, (220, 40, 40))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    note_path,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    object_image_path=str(first_image),
                )

                listing = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    object_image_path=str(first_image),
                )
                self.assertEqual([item.name for item in listing.files], ["note.txt"])

                with self.assertRaisesRegex(ValueError, "object mismatch"):
                    svc.list_files(
                        vessel_path,
                        "correct horse battery",
                        selector="face_a",
                        object_image_path=str(second_image),
                    )

                with self.assertRaisesRegex(ValueError, "password mismatch"):
                    svc.list_files(
                        vessel_path,
                        "wrong password",
                        selector="face_a",
                        object_image_path=str(first_image),
                    )
                listing_after = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    object_image_path=str(first_image),
                )
                self.assertEqual([item.name for item in listing_after.files], ["note.txt"])

    def test_second_add_wrong_access_password_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            first_file = Path(tmpdir) / "one.txt"
            second_file = Path(tmpdir) / "two.txt"
            image_path = Path(tmpdir) / "object-a.png"
            first_file.write_text("alpha", encoding="utf-8")
            second_file.write_text("bravo", encoding="utf-8")
            self._write_object_image(image_path, (20, 120, 220))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    first_file,
                    "access-pw",
                    "emergency-pw",
                    selector="face_a",
                    object_image_path=str(image_path),
                )
                with self.assertRaisesRegex(ValueError, "password mismatch"):
                    svc.add_file(
                        vessel_path,
                        second_file,
                        "wrong-pw",
                        None,
                        selector="face_a",
                        object_image_path=str(image_path),
                    )

    def test_second_add_preserves_emergency_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            first_file = Path(tmpdir) / "one.txt"
            second_file = Path(tmpdir) / "two.txt"
            image_path = Path(tmpdir) / "object-a.png"
            first_file.write_text("alpha", encoding="utf-8")
            second_file.write_text("bravo", encoding="utf-8")
            self._write_object_image(image_path, (20, 120, 220))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    first_file,
                    "access-pw",
                    "burn-pw",
                    selector="face_a",
                    object_image_path=str(image_path),
                )
                svc.add_file(
                    vessel_path,
                    second_file,
                    "access-pw",
                    None,
                    selector="face_a",
                    object_image_path=str(image_path),
                )
                result = svc.destroy_face(
                    vessel_path,
                    "burn-pw",
                    selector="face_a",
                    object_image_path=str(image_path),
                    confirmation="DESTROY FACE",
                )
                self.assertEqual(result.face_id, "face_a")

    def test_emergency_password_does_not_trigger_normal_list_or_retrieve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_path = Path(tmpdir) / "note.txt"
            image_path = Path(tmpdir) / "object-a.png"
            note_path.write_text("field note", encoding="utf-8")
            self._write_object_image(image_path, (20, 120, 220))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    note_path,
                    "access-pw",
                    "burn-pw",
                    selector="face_a",
                    object_image_path=str(image_path),
                )
                with self.assertRaisesRegex(ValueError, "password mismatch"):
                    svc.list_files(
                        vessel_path,
                        "burn-pw",
                        selector="face_a",
                        object_image_path=str(image_path),
                    )
                with self.assertRaisesRegex(ValueError, "password mismatch"):
                    svc.retrieve_file(
                        vessel_path,
                        "burn-pw",
                        output_path=Path(tmpdir) / "out.txt",
                        selector="face_a",
                        object_image_path=str(image_path),
                    )
                with self.assertRaisesRegex(ValueError, "password mismatch"):
                    svc.remove_file(
                        vessel_path,
                        "note.txt",
                        "burn-pw",
                        None,
                        selector="face_a",
                        object_image_path=str(image_path),
                    )

    def test_emergency_destroy_face_requires_correct_object_password_and_confirmation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_a = Path(tmpdir) / "a.txt"
            note_b = Path(tmpdir) / "b.txt"
            image_a = Path(tmpdir) / "object-a.png"
            image_b = Path(tmpdir) / "object-b.png"
            note_a.write_text("alpha", encoding="utf-8")
            note_b.write_text("bravo", encoding="utf-8")
            self._write_object_image(image_a, (20, 120, 220))
            self._write_object_image(image_b, (220, 40, 40))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    note_a,
                    "access-pw",
                    "burn-a",
                    selector="face_a",
                    object_image_path=str(image_a),
                )
                svc.add_file(
                    vessel_path,
                    note_b,
                    "access-pw",
                    "burn-b",
                    selector="face_b",
                    object_image_path=str(image_b),
                )

                with self.assertRaisesRegex(ValueError, "object mismatch"):
                    svc.destroy_face(
                        vessel_path,
                        "burn-a",
                        selector="face_a",
                        object_image_path=str(image_b),
                        confirmation="DESTROY FACE",
                    )
                with self.assertRaisesRegex(ValueError, "emergency password mismatch"):
                    svc.destroy_face(
                        vessel_path,
                        "wrong",
                        selector="face_a",
                        object_image_path=str(image_a),
                        confirmation="DESTROY FACE",
                    )

                result = svc.destroy_face(
                    vessel_path,
                    "burn-a",
                    selector="face_a",
                    object_image_path=str(image_a),
                    confirmation="DESTROY FACE",
                )
                self.assertEqual(result.face_id, "face_a")
                with self.assertRaisesRegex(ValueError, "credentials not initialized"):
                    svc.list_files(
                        vessel_path,
                        "access-pw",
                        selector="face_a",
                        object_image_path=str(image_a),
                    )
                files_b = svc.list_files(
                    vessel_path,
                    "access-pw",
                    selector="face_b",
                    object_image_path=str(image_b),
                )
                self.assertEqual([item.name for item in files_b.files], ["b.txt"])

    def test_emergency_destroy_before_initialization_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            image_a = Path(tmpdir) / "object-a.png"
            self._write_object_image(image_a, (20, 120, 220))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                with self.assertRaisesRegex(ValueError, "credentials not initialized"):
                    svc.destroy_face(
                        vessel_path,
                        "burn-a",
                        selector="face_a",
                        object_image_path=str(image_a),
                        confirmation="DESTROY FACE",
                    )

    def test_emergency_destroy_vessel_invalidates_all_faces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_a = Path(tmpdir) / "a.txt"
            note_b = Path(tmpdir) / "b.txt"
            image_a = Path(tmpdir) / "object-a.png"
            image_b = Path(tmpdir) / "object-b.png"
            note_a.write_text("alpha", encoding="utf-8")
            note_b.write_text("bravo", encoding="utf-8")
            self._write_object_image(image_a, (20, 120, 220))
            self._write_object_image(image_b, (220, 40, 40))

            with mock.patch.dict(
                os.environ,
                {"PHASMID_STATE_DIR": str(state_dir)},
                clear=False,
            ), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    note_a,
                    "access-pw",
                    "burn-a",
                    selector="face_a",
                    object_image_path=str(image_a),
                )
                svc.add_file(
                    vessel_path,
                    note_b,
                    "access-pw",
                    "burn-b",
                    selector="face_b",
                    object_image_path=str(image_b),
                )
                svc.destroy_vessel(
                    vessel_path,
                    "burn-b",
                    selector="face_b",
                    object_image_path=str(image_b),
                    confirmation="DESTROY VESSEL",
                )
                self.assertIsNone(vessel_service_mod.get_vessel_record(vessel_path))
                with self.assertRaises(ValueError):
                    svc.list_files(
                        vessel_path,
                        "access-pw",
                        selector="face_a",
                        object_image_path=str(image_a),
                    )


if __name__ == "__main__":
    unittest.main()
