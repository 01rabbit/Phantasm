import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))


def read_text(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


class DocsAndTemplateTests(unittest.TestCase):
    def test_store_template_exposes_metadata_workflow_without_overclaiming(self):
        store = read_text("src/phasmid/templates/store.html")
        self.assertIn("Data minimization", store)
        self.assertIn("Metadata Risk", store)
        self.assertIn("Check metadata risk", store)
        self.assertIn("Download metadata-reduced copy", store)
        self.assertIn("Metadata detection and reduction are best-effort.", store)
        self.assertNotIn("complete metadata removal", store.lower())

    def test_readme_links_field_operational_docs(self):
        readme = read_text("README.md")
        self.assertIn("Quick Start in 60 seconds", readme)
        self.assertIn("docs/README_INDEX.md", readme)
        self.assertIn("docs/PHASMID_ARCHITECTURE.md", readme)
        self.assertIn("docs/THREAT_MODEL.md", readme)
        self.assertIn("docs/SPECIFICATION.md", readme)
        self.assertIn("docs/WEBUI_OPERATOR_GUIDE.md", readme)

    def test_webui_operator_guide_covers_normal_simple_operator_flow(self):
        guide = read_text("docs/WEBUI_OPERATOR_GUIDE.md")
        self.assertIn("Protect a File", guide)
        self.assertIn("Open a Protected File", guide)
        self.assertIn("Guided Mode", guide)
        self.assertIn("Advanced tools", guide)
        self.assertIn("Finish and clear", guide)
        self.assertIn("never replaces the original automatically", guide)
        self.assertIn("not an access-control boundary", guide)

    def test_readme_addresses_reviewer_and_use_boundaries(self):
        readme = read_text("README.md")
        self.assertIn("Who this is for", readme)
        self.assertIn("Janus Eidolon System", readme)
        self.assertIn("local-only operation by default", readme)
        self.assertIn("best effort", readme)
        self.assertIn("field-evaluation prototype", readme)

    def test_specification_defines_field_mode_and_metadata_routes(self):
        spec = read_text("docs/SPECIFICATION.md")
        self.assertIn("PHASMID_FIELD_MODE=1", spec)
        self.assertIn("/metadata/check", spec)
        self.assertIn("/metadata/scrub", spec)
        self.assertIn("no disk", spec.lower())
        self.assertIn("neutral filename", spec.lower())
        self.assertIn("Capture-Visible Surface Rule", spec)
        self.assertIn("Stress-Use UX Principle", spec)
        self.assertIn("Field Mode is not a security boundary", spec)
        self.assertIn("PHASMID_MIN_PASSPHRASE_LENGTH", spec)
        self.assertIn("PHASMID_ACCESS_LOCKOUT_SECONDS", spec)
        self.assertIn("Cryptographic Boundary", spec)
        self.assertIn("not a FIPS validation", spec)

    def test_threat_model_names_leakage_surfaces(self):
        threat = read_text("docs/THREAT_MODEL.md")
        self.assertIn("metadata", threat.lower())
        self.assertIn("Maintenance diagnostics", threat)
        self.assertIn("camera overlay", threat)
        self.assertIn("CLI output", threat)
        self.assertIn("systemd logs", threat)
        self.assertIn("Capture-visible surfaces include", threat)
        self.assertIn("Hidden routes are not access control", threat)

    def test_source_safe_workflow_addresses_mixing_and_labels(self):
        doc = read_text("docs/SOURCE_SAFE_WORKFLOW.md")
        self.assertIn("Do not store source identity", doc)
        self.assertIn("Avoid local labels that reveal", doc)
        self.assertIn("Before travel", doc)

    def test_field_test_procedure_addresses_field_use_limits(self):
        doc = read_text("docs/FIELD_TEST_PROCEDURE.md")
        self.assertIn(
            "Physical shock resistance and tamper-resistant casing are out of scope",
            doc,
        )
        self.assertIn("Test sudden power loss during Retrieve", doc)
        self.assertIn("Review the systemd journal after each power-loss case", doc)

    def test_operations_doc_links_command_checks_and_scenarios(self):
        doc = read_text("docs/OPERATIONS.md")
        self.assertIn("phasmid verify-state", doc)
        self.assertIn("phasmid verify-audit-log", doc)
        self.assertIn("phasmid doctor", doc)
        self.assertIn("phasmid export-redacted-log --out review-events.jsonl", doc)
        self.assertIn("tests/test_operations.py", doc)
        self.assertIn("tests/scenarios/restricted_flows.json", doc)
        self.assertIn("tests/test_scenarios.py", doc)

    def test_architecture_docs_define_jes_and_phasmid_boundary(self):
        janus = read_text("docs/JANUS_EIDOLON_SYSTEM.md")
        architecture = read_text("docs/PHASMID_ARCHITECTURE.md")
        self.assertIn("Janus Eidolon System", janus)
        self.assertIn("Janus System", janus)
        self.assertIn("Phasmid", architecture)
        self.assertIn("src/phasmid", architecture)
        self.assertIn("PHASMID_*", architecture)

    def test_review_validation_record_exists(self):
        record = read_text("docs/REVIEW_VALIDATION_RECORD.md")
        self.assertIn("Review Validation Record", record)
        self.assertRegex(record, r"\d+ tests passed")
        self.assertIn("tests/scenarios/restricted_flows.json", record)
        self.assertIn("Target-hardware validation result", record)
        self.assertRegex(
            record,
            r"(Not field-proven|validated for the recorded deployment conditions)",
        )
        self.assertIn("Solution Readiness", record)

    def test_solution_readiness_plan_bounds_solution_claims(self):
        plan = read_text("docs/SOLUTION_READINESS_PLAN.md")
        self.assertIn("Solution Readiness Plan", plan)
        self.assertIn("readiness gates", plan)
        self.assertIn("target-hardware validation", plan)
        self.assertIn("README claims match the validation record", plan)
        self.assertIn("formatting and static-analysis result", plan)
        self.assertIn("release manifest and SBOM generation result", plan)

    def test_rpi_appliance_doc_is_authoritative(self):
        summary = read_text("docs/RPI_ZERO_DEPLOYMENT.md")
        appliance = read_text("docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md")
        self.assertIn("authoritative appliance deployment guide", summary)
        self.assertIn(
            "authoritative Raspberry Pi Zero 2 W appliance deployment guide", appliance
        )
        self.assertIn("optional LUKS2 storage-layer procedure", summary)
        self.assertIn("Optional LUKS Storage Layer", appliance)


if __name__ == "__main__":
    unittest.main()
