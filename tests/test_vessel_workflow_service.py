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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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
                self.assertIn(
                    "face_a:credentials=ready:object=ready",
                    labels["Face Credential State"],
                )

    def test_first_add_initializes_face_b_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            image_path = Path(tmpdir) / "object-b.png"
            input_path.write_text("field note", encoding="utf-8")
            self._write_object_image(image_path, (220, 40, 40))

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                with self.assertRaises(FileExistsError):
                    svc.create_vessel(vessel_path, "8M")

    def test_newly_created_vessel_is_inspectable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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
                self.assertEqual(
                    reopened.vessel.last_closed_at, closed.vessel.last_closed_at
                )

                inspection = InspectionService().inspect(vessel_path)
                self.assertTrue(inspection.ok)

    def test_face_lifecycle_persists_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            input_path = Path(tmpdir) / "note.txt"
            output_path = Path(tmpdir) / "recovered.txt"
            input_path.write_text("field note", encoding="utf-8")

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                face = svc.create_face(vessel_path, "face_b", label="travel")
                self.assertEqual(face.face.face_id, "face_b")
                self.assertEqual(face.face.label, "travel")
                self.assertTrue(face.face.created_at)

                opened = svc.open_vessel(vessel_path, face_id="face_b")
                opened_face = next(
                    face for face in opened.vessel.faces if face.face_id == "face_b"
                )
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
                closed_face = next(
                    face for face in closed.vessel.faces if face.face_id == "face_b"
                )
                self.assertEqual(closed_face.status, "occupied")
                self.assertEqual(closed_face.occupancy, len(b"field note"))
                self.assertEqual(closed_face.file_count, 1)

                reopened = svc.open_vessel(vessel_path, face_id="face_b")
                reopened_face = next(
                    face for face in reopened.vessel.faces if face.face_id == "face_b"
                )
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

    def test_labelling_a_face_preserves_its_generated_dummy_profile(self):
        """`create_face` on a populated slot must not re-initialise it.

        Creating a Vessel auto-provisions both faces, so the Create Face
        button never creates anything - it always targets an existing slot to
        attach a label. Whether that wiped an already-generated decoy profile
        was never established, and the failure mode would be quiet: roughly
        four minutes of generation discarded, with the operator still
        believing a high-plausibility decoy was in place. It only surfaces
        under exactly the conditions the profile exists for.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

                labelled = svc.create_face(vessel_path, "face_a", label="travel")
                self.assertEqual(labelled.face.face_id, "face_a")
                self.assertEqual(labelled.face.label, "travel")

                after = svc.inspect_dummy_profile(vessel_path, "face_a")
                self.assertEqual(
                    after.profile.dummy_file_count,
                    generated.profile.dummy_file_count,
                )
                self.assertEqual(
                    after.profile.dummy_total_size,
                    generated.profile.dummy_total_size,
                )
                self.assertEqual(
                    after.profile.plausibility_level,
                    generated.profile.plausibility_level,
                )
                self.assertEqual(
                    after.profile.plausibility_score,
                    generated.profile.plausibility_score,
                )

    def test_dummy_profile_clear_preserves_manual_face_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            note_path = Path(tmpdir) / "note.txt"
            note_path.write_text("field note", encoding="utf-8")

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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
                self.assertEqual(
                    [item.name for item in listing_after.files], ["note.txt"]
                )

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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

    def test_emergency_destroy_face_requires_correct_object_password_and_confirmation(
        self,
    ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
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


class WebAndConsoleShareStorageTests(unittest.TestCase):
    """The WebUI and the operator console must act on the same container.

    They did not: the console worked on Vessels while `web_server` held a
    module-level `PhasmidVault("vault.bin")` and stored straight through it.
    A file saved from a browser therefore never appeared in any Vessel, in
    Audit, or in VESSEL STATUS - two operator surfaces on one device
    disagreeing about what was stored.
    """

    def _patch_registry_dir(self, tmpdir: str):
        return mock.patch.object(vessel_service_mod, "config_dir", lambda: Path(tmpdir))

    def test_payload_stored_by_the_web_path_is_readable_by_the_console(self):
        from phasmid.services.web_target_service import face_for_mode

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            payload = b"# field notes\nrecovered through the console\n"

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")

                # What the WebUI does: bytes from an upload, addressed by the
                # access mode rather than by a face id.
                svc.add_payload(
                    vessel_path,
                    "notes.md",
                    payload,
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector=face_for_mode("dummy"),
                    cue_sequence=["reference_dummy_matched"],
                )

                # What the console sees afterwards.
                listing = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertIn("notes.md", [item.name for item in listing.files])

                recovered, result = svc.retrieve_payload(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertEqual(recovered, payload)
                self.assertEqual(result.filename, "notes.md")
                self.assertEqual(result.bytes_retrieved, len(payload))
                self.assertIsNone(result.output_path)

    def test_add_payload_preserves_files_already_in_the_face(self):
        """Writing through PhasmidVault directly would clobber the namespace.

        A face holds a JSON namespace of many files, not one payload. Anyone
        unifying the two surfaces by simply repointing `PhasmidVault` at a
        `.vessel` path would overwrite that namespace and destroy whatever
        the face already held, so the shared entry point has to go through
        the namespace like the console does.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            vessel_path = Path(tmpdir) / "travel.vessel"
            first = Path(tmpdir) / "first.txt"
            first.write_text("stored from the console", encoding="utf-8")

            with (
                mock.patch.dict(
                    os.environ,
                    {"PHASMID_STATE_DIR": str(state_dir)},
                    clear=False,
                ),
                self._patch_registry_dir(tmpdir),
            ):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel_path, "8M")
                svc.add_file(
                    vessel_path,
                    first,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                svc.add_payload(
                    vessel_path,
                    "second.txt",
                    b"stored from the browser",
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )

                listing = svc.list_files(
                    vessel_path,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertEqual(
                    {"first.txt", "second.txt"},
                    {item.name for item in listing.files},
                )


class RetrievalSelectionTests(unittest.TestCase):
    """Which file an unnamed retrieval returns.

    The WebUI never names a file, so whatever this picks is what the operator
    gets back. Three separate defects have landed here already: alphabetical
    first (unreachable later stores), generated filler outranking a real
    upload, and same-second ties falling back to the alphabetical order the
    selection exists to avoid.
    """

    def _patch_registry_dir(self, tmpdir: str):
        return mock.patch.object(vessel_service_mod, "config_dir", lambda: Path(tmpdir))

    def _env(self, tmpdir):
        return mock.patch.dict(
            os.environ,
            {"PHASMID_STATE_DIR": str(Path(tmpdir) / "state")},
            clear=False,
        )

    def test_generated_filler_never_shadows_an_operator_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vessel = Path(tmpdir) / "travel.vessel"
            note = Path(tmpdir) / "note.txt"
            note.write_text("operator content", encoding="utf-8")
            with self._env(tmpdir), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel, "8M")
                svc.add_file(
                    vessel,
                    note,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                svc.generate_dummy_profile(
                    vessel,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_a",
                    target_occupancy="15%",
                    cue_sequence=["reference_dummy_matched"],
                )
                data, result = svc.retrieve_payload(
                    vessel,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertEqual(result.filename, "note.txt")
                self.assertEqual(data, b"operator content")

    def test_same_second_stores_return_the_later_one(self):
        """added_at has one-second granularity; two stores can tie."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vessel = Path(tmpdir) / "travel.vessel"
            fixed = "2026-07-28T00:00:00Z"
            with self._env(tmpdir), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel, "8M")
                with mock.patch("time.strftime", lambda *a, **k: fixed):
                    for name, body in (
                        ("zzz_first.txt", b"first"),
                        ("aaa_second.txt", b"second"),
                    ):
                        svc.add_payload(
                            vessel,
                            name,
                            body,
                            "correct horse battery",
                            restricted_passphrase="restricted recovery only",
                            selector="face_a",
                            cue_sequence=["reference_dummy_matched"],
                        )
                data, result = svc.retrieve_payload(
                    vessel,
                    "correct horse battery",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                # Both records carry the same added_at, so a name-based
                # tie-break would return zzz_first only by alphabetical luck.
                self.assertEqual(result.filename, "aaa_second.txt")
                self.assertEqual(data, b"second")

    def test_generation_does_not_overwrite_a_colliding_operator_file(self):
        """Filler names come from a fixed pool and can collide."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vessel = Path(tmpdir) / "travel.vessel"
            with self._env(tmpdir), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel, "8M")
                svc.add_payload(
                    vessel,
                    "seed.txt",
                    b"seed",
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector="face_b",
                    cue_sequence=["reference_secret_matched"],
                )
                generated = svc.generate_dummy_profile(
                    vessel,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_b",
                    target_occupancy="15%",
                    cue_sequence=["reference_secret_matched"],
                )
                self.assertGreater(generated.profile.dummy_file_count, 0)
                listing = svc.list_files(
                    vessel,
                    "correct horse battery",
                    selector="face_b",
                    cue_sequence=["reference_secret_matched"],
                )
                filler_name = next(
                    item.name for item in listing.files if item.name != "seed.txt"
                )

                svc.add_payload(
                    vessel,
                    filler_name,
                    b"operator content that must survive",
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector="face_b",
                    cue_sequence=["reference_secret_matched"],
                )
                svc.generate_dummy_profile(
                    vessel,
                    "correct horse battery",
                    "restricted recovery only",
                    selector="face_b",
                    target_occupancy="15%",
                    cue_sequence=["reference_secret_matched"],
                )
                data, _result = svc.retrieve_payload(
                    vessel,
                    "correct horse battery",
                    selector="face_b",
                    cue_sequence=["reference_secret_matched"],
                    filename=filler_name,
                )
                self.assertEqual(data, b"operator content that must survive")

    def test_named_file_that_does_not_exist_is_an_error_not_a_substitution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vessel = Path(tmpdir) / "travel.vessel"
            with self._env(tmpdir), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel, "8M")
                svc.add_payload(
                    vessel,
                    "present.txt",
                    b"here",
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                with self.assertRaises(FileNotFoundError):
                    svc.retrieve_payload(
                        vessel,
                        "correct horse battery",
                        selector="face_a",
                        cue_sequence=["reference_dummy_matched"],
                        filename="absent.txt",
                    )

    def test_output_path_name_is_a_hint_and_still_falls_back(self):
        """Recovering README.md to recovered.md is ordinary usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vessel = Path(tmpdir) / "travel.vessel"
            out = Path(tmpdir) / "recovered.md"
            with self._env(tmpdir), self._patch_registry_dir(tmpdir):
                svc = VesselWorkflowService()
                svc.create_vessel(vessel, "8M")
                svc.add_payload(
                    vessel,
                    "README.md",
                    b"# readme",
                    "correct horse battery",
                    restricted_passphrase="restricted recovery only",
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                result = svc.retrieve_file(
                    vessel,
                    "correct horse battery",
                    output_path=out,
                    selector="face_a",
                    cue_sequence=["reference_dummy_matched"],
                )
                self.assertEqual(result.filename, "README.md")
                self.assertEqual(out.read_bytes(), b"# readme")
