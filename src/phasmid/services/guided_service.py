from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GuidedStep:
    number: int
    text: str
    detail: str = ""


@dataclass
class GuidedWorkflow:
    id: str
    title: str
    description: str
    steps: list[GuidedStep] = field(default_factory=list)


def get_workflows() -> list[GuidedWorkflow]:
    return [
        GuidedWorkflow(
            id="coerced_disclosure",
            title="Coerced Disclosure Walkthrough",
            description=(
                "Step through a scenario in which an operator is compelled to "
                "disclose the contents of a Vessel. Demonstrates how the system "
                "avoids confirming or denying the existence of other disclosure faces."
            ),
            steps=[
                GuidedStep(
                    1,
                    "A storage object is inspected.",
                    "An observer examines the file. No header or vault signature is present.",
                ),
                GuidedStep(
                    2,
                    "No obvious header or vault structure is asserted.",
                    "The file carries no magic bytes or recognized container metadata.",
                ),
                GuidedStep(
                    3,
                    "A disclosure face is opened under pressure.",
                    "The operator provides credentials for one disclosure face. "
                    "The system opens that face without revealing others.",
                ),
                GuidedStep(
                    4,
                    'The system does not label another face as "truth".',
                    "No UI element identifies which face is primary. "
                    "Both faces are disclosure faces.",
                ),
                GuidedStep(
                    5,
                    "The operator reviews limitations and residual risks.",
                    "Deniability is procedural and depends on operational context. "
                    "Host compromise, OS artifacts, and metadata may undermine deniability.",
                ),
            ],
        ),
        GuidedWorkflow(
            id="headerless_inspection",
            title="Headerless Vessel Inspection",
            description=(
                "Demonstrate what an external observer sees when inspecting a Vessel. "
                "No recognized header, no obvious magic bytes, high entropy."
            ),
            steps=[
                GuidedStep(
                    1, "Select a Vessel file.", "Choose any Vessel from the list."
                ),
                GuidedStep(
                    2,
                    "Run inspection.",
                    "The inspection service reads the file without decrypting it.",
                ),
                GuidedStep(
                    3,
                    "Review inspection output.",
                    "Expected output: no recognized header detected, "
                    "no obvious magic bytes detected, high / random-like entropy.",
                ),
                GuidedStep(
                    4,
                    "Note: inspection does not confirm deniability.",
                    "An absent header reduces obvious signals. "
                    "It does not remove all forensic traces.",
                ),
            ],
        ),
        GuidedWorkflow(
            id="multiple_faces",
            title="Multiple Disclosure Faces",
            description=(
                "Walk through the concept of multiple disclosure faces within a Vessel. "
                "Shows how different credentials access different content "
                "without revealing which face is active."
            ),
            steps=[
                GuidedStep(
                    1,
                    "A Vessel carries more than one disclosure face.",
                    "Each face is accessed by different credentials. "
                    "The Vessel does not record which face is primary.",
                ),
                GuidedStep(
                    2,
                    "Face labels are neutral.",
                    "Labels such as Disclosure Face 1 and Disclosure Face 2 "
                    "do not indicate which is primary.",
                ),
                GuidedStep(
                    3,
                    "Opening a face does not expose others.",
                    "Accessing one face provides no information about other faces.",
                ),
                GuidedStep(
                    4,
                    "Deniability is procedural.",
                    "Whether disclosure is plausible depends on operational context, "
                    "not only on the system's technical design.",
                ),
            ],
        ),
        GuidedWorkflow(
            id="safety_checklist",
            title="Operator Safety Checklist",
            description=(
                "Review operational controls and known risks before sensitive use."
            ),
            steps=[
                GuidedStep(
                    1,
                    "Run Doctor to check local configuration.",
                    "Doctor checks configuration directory permissions, "
                    "temporary directory, shell history, and debug logging.",
                ),
                GuidedStep(
                    2,
                    "Review shell history policy.",
                    "Avoid passing passphrases as CLI arguments. "
                    "Use the TUI for interactive workflows.",
                ),
                GuidedStep(
                    3,
                    "Check output directory permissions.",
                    "Extracted files should be written to a restricted directory. "
                    "Avoid world-readable locations.",
                ),
                GuidedStep(
                    4,
                    "Review Audit View.",
                    "Confirm system position, cryptographic controls, "
                    "and known limitations are understood.",
                ),
                GuidedStep(
                    5,
                    "Acknowledge limitations.",
                    "Host compromise may defeat confidentiality. "
                    "OS artifacts may reveal usage. "
                    "Deniability is procedural, not absolute.",
                ),
            ],
        ),
    ]


class GuidedService:
    def get_workflows(self) -> list[GuidedWorkflow]:
        return get_workflows()

    def get_workflow(self, workflow_id: str) -> GuidedWorkflow | None:
        for wf in get_workflows():
            if wf.id == workflow_id:
                return wf
        return None
