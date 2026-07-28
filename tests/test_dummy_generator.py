import json
import os
import string
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from phasmid.context_profile import get_profile
from phasmid.dummy_generator import (
    _BENIGN_TEXT_FRAGMENTS,
    _LOG_LINE_FRAGMENTS,
    DummyGeneratorConfig,
    GeneratedDummyReport,
    generate_dummy_dataset,
    import_sample_directory,
)


class TestGenerateDummyDataset(unittest.TestCase):
    def setUp(self):
        self.profile = get_profile("travel")

    def _make_config(self, output_dir, target_mb=10, occupancy=0.5):
        return DummyGeneratorConfig(
            target_size_bytes=target_mb * 1024 * 1024,
            occupancy_ratio=occupancy,
            profile=self.profile,
            output_dir=output_dir,
        )

    def test_generate_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "dummy_out")
            config = self._make_config(out)
            generate_dummy_dataset(config)
            self.assertTrue(os.path.isdir(out))

    def test_generate_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            report = generate_dummy_dataset(config)
            self.assertGreater(report.files_created, 0)

    def test_generate_returns_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            report = generate_dummy_dataset(config)
            self.assertIsInstance(report, GeneratedDummyReport)
            self.assertEqual(report.profile_name, "travel")

    def test_generate_creates_profile_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp)
            report = generate_dummy_dataset(config)
            self.assertGreater(report.directory_count, 1)

    def test_generate_extension_distribution_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=5)
            report = generate_dummy_dataset(config)
            self.assertTrue(len(report.extension_distribution) > 0)

    def test_generate_files_have_correct_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=5)
            report = generate_dummy_dataset(config)
            expected = set(self.profile.dummy_content_types)
            actual = set(report.extension_distribution.keys())
            self.assertTrue(
                actual.issubset(expected),
                f"Unexpected extensions: {actual - expected}",
            )

    def test_generate_zero_occupancy_produces_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = get_profile("maintenance")
            config = DummyGeneratorConfig(
                target_size_bytes=10 * 1024 * 1024,
                occupancy_ratio=0.0,
                profile=profile,
                output_dir=tmp,
            )
            report = generate_dummy_dataset(config)
            self.assertGreater(len(report.warnings), 0)

    def test_generate_produces_plausibility_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=20)
            report = generate_dummy_dataset(config)
            self.assertIsNotNone(report.plausibility)
            self.assertTrue(os.path.exists(report.evaluation_report_path))
            with open(report.evaluation_report_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIn("container_size_bytes", payload)
            self.assertIn("dummy_size_bytes", payload)
            self.assertIn("occupancy_ratio", payload)
            self.assertIn("file_count", payload)
            self.assertIn("size_distribution", payload)
            self.assertIsInstance(report.size_distribution, dict)

    def test_generate_does_not_produce_disallowed_content(self):
        """Verify no forged system files, kernel logs, or forensic artifacts.

        Asserted against the generator's own vocabulary rather than against a
        sample of its output. Stems are random lowercase alphanumerics of
        length 8-16, so a substring scan of sampled filenames fails by chance
        roughly once in a few hundred runs - a red CI run that says nothing
        about whether the generator forges anything.
        """
        forensic_terms = ("kern", "syslog", "wtmp", "utmp", "dmesg", "auth.log")

        # Nothing the generator can deliberately name or write may look like a
        # forensic artifact.
        vocabulary = [
            fragment.decode("utf-8", errors="ignore").lower()
            for fragment in _BENIGN_TEXT_FRAGMENTS + _LOG_LINE_FRAGMENTS
        ]
        vocabulary += [ext.lower() for ext in self.profile.dummy_content_types]
        for entry in vocabulary:
            for term in forensic_terms:
                self.assertNotIn(
                    term, entry, f"Suspicious generator vocabulary: {entry}"
                )

        # And what it actually writes must stay inside that vocabulary: random
        # stems from [a-z0-9], extensions drawn from the profile.
        allowed_stem = set(string.ascii_lowercase + string.digits)
        allowed_ext = {
            ext.lstrip(".").lower() for ext in self.profile.dummy_content_types
        }
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=5)
            report = generate_dummy_dataset(config)
            own_report = os.path.basename(report.evaluation_report_path)
            written = 0
            for _dirpath, _dirnames, filenames in os.walk(tmp):
                for fname in filenames:
                    if fname == own_report:
                        continue
                    stem, _, ext = fname.rpartition(".")
                    self.assertIn(
                        ext.lower(), allowed_ext, f"Unexpected extension: {fname}"
                    )
                    self.assertTrue(
                        set(stem) <= allowed_stem, f"Unexpected filename stem: {fname}"
                    )
                    written += 1
            self.assertGreater(written, 0)

    def test_effective_dummy_size_bytes(self):
        config = DummyGeneratorConfig(
            target_size_bytes=100 * 1024 * 1024,
            occupancy_ratio=0.25,
            profile=self.profile,
            output_dir="/tmp",
        )
        self.assertEqual(config.effective_dummy_size_bytes(), 25 * 1024 * 1024)

    def test_generate_warns_when_configured_thresholds_not_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=1, occupancy=0.1)
            with mock.patch.dict(
                os.environ,
                {
                    "PHASMID_DUMMY_MIN_SIZE_MB": "5",
                    "PHASMID_DUMMY_MIN_FILE_COUNT": "1000",
                    "PHASMID_DUMMY_OCCUPANCY_WARN": "0.90",
                },
                clear=False,
            ):
                report = generate_dummy_dataset(config)
            joined = " | ".join(report.warnings).lower()
            self.assertIn("configured minimum", joined)
            self.assertIn("disproportionately small", joined)

    def test_generate_disperses_file_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._make_config(tmp, target_mb=2, occupancy=0.5)
            report = generate_dummy_dataset(config)
            self.assertGreater(report.files_created, 0)

            mtimes = set()
            for dirpath, _dirnames, filenames in os.walk(tmp):
                for fname in filenames:
                    if fname == "dummy_profile_eval.json":
                        continue
                    path = os.path.join(dirpath, fname)
                    mtimes.add(os.stat(path).st_mtime_ns)
            self.assertGreater(len(mtimes), 1)


class TestImportSampleDirectory(unittest.TestCase):
    def test_import_copies_files(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            (os.path.join(src, "notes.txt")), "w"
            with open(os.path.join(src, "notes.txt"), "w") as f:
                f.write("sample content\n")
            files, total, warnings = import_sample_directory(src, dst)
            self.assertEqual(files, 1)
            self.assertEqual(len(warnings), 0)

    def test_import_missing_source_returns_warning(self):
        files, total, warnings = import_sample_directory(
            "/nonexistent/path/xyz", "/tmp"
        )
        self.assertEqual(files, 0)
        self.assertTrue(len(warnings) > 0)

    def test_import_respects_allowed_extensions(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            with open(os.path.join(src, "keep.txt"), "w") as f:
                f.write("keep")
            with open(os.path.join(src, "skip.bin"), "wb") as f:
                f.write(b"\x00" * 100)
            files, total, warnings = import_sample_directory(
                src, dst, allowed_extensions=["txt"]
            )
            self.assertEqual(files, 1)
            self.assertTrue(os.path.exists(os.path.join(dst, "keep.txt")))
            self.assertFalse(os.path.exists(os.path.join(dst, "skip.bin")))

    def test_import_respects_max_bytes(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            for i in range(5):
                with open(os.path.join(src, f"file{i}.txt"), "w") as f:
                    f.write("x" * 1000)
            files, total, warnings = import_sample_directory(src, dst, max_bytes=2500)
            self.assertLessEqual(total, 2500 + 1000)
            self.assertTrue(len(warnings) > 0)


if __name__ == "__main__":
    unittest.main()
