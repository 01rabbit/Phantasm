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
            id="protect_file",
            title="Protect a File",
            description="The normal path for placing a file into protected local storage.",
            steps=[
                GuidedStep(1, "Choose or create protected storage.", "Use New from the Simple Operator screen when no storage exists yet."),
                GuidedStep(2, "Choose the file you want to protect.", "Keep unrelated files separate so disclosure remains easier to reason about."),
                GuidedStep(3, "Set the access password.", "Do not pass sensitive passwords as command-line arguments."),
                GuidedStep(4, "Bind the physical access object.", "Use an object that can be presented consistently to the local camera."),
                GuidedStep(5, "Confirm the result, then close the storage when finished.", "Closing preserves the protected state and reduces accidental exposure."),
            ],
        ),
        GuidedWorkflow(
            id="open_file",
            title="Open a Protected File",
            description="The normal path for accessing previously protected content.",
            steps=[
                GuidedStep(1, "Select the protected storage you need.", "Use the Simple Operator list rather than inspection tools."),
                GuidedStep(2, "Present the physical access object.", "Wait for a stable local match before continuing."),
                GuidedStep(3, "Enter the access password.", "Both the object and password are required for the normal access path."),
                GuidedStep(4, "Retrieve only the file you need.", "Avoid copying protected content into broadly readable locations."),
                GuidedStep(5, "Close the storage when finished.", "Clear temporary output when appropriate for the operating environment."),
            ],
        ),
        GuidedWorkflow(
            id="safety_checklist",
            title="Safety Checklist",
            description="Review important operational controls before sensitive use.",
            steps=[
                GuidedStep(1, "Check device health.", "Use Diagnostics from Expert mode if the Simple Operator screen reports a problem."),
                GuidedStep(2, "Keep passwords out of shell history.", "Prefer the TUI or WebUI for interactive password entry."),
                GuidedStep(3, "Check output location permissions.", "Retrieved files should not be written to world-readable locations."),
                GuidedStep(4, "Keep the WebUI closed when it is not needed.", "An active WebUI increases the exposed local interface."),
                GuidedStep(5, "Remember the limits of the system.", "Host compromise, OS artifacts, observation, and operational mistakes can undermine protection."),
            ],
        ),
        GuidedWorkflow(
            id="coerced_disclosure",
            title="Expert: Coerced Disclosure Walkthrough",
            description=(
                "Step through a scenario in which an operator is compelled to "
                "disclose protected contents without the interface asserting the existence "
                "or role of other disclosure faces."
            ),
            steps=[
                GuidedStep(1, "A storage object is inspected.", "An observer examines the file. No header or vault signature is present."),
                GuidedStep(2, "No obvious header or vault structure is asserted.", "The file carries no magic bytes or recognized container metadata."),
                GuidedStep(3, "One disclosure face is opened under pressure.", "The operator provides credentials for one disclosure face. The system opens that face without revealing others."),
                GuidedStep(4, 'The system does not label another face as "truth".', "No UI element identifies which face is primary. Both faces are disclosure faces."),
                GuidedStep(5, "The operator reviews limitations and residual risks.", "Deniability is procedural and depends on operational context. Host compromise, OS artifacts, and metadata may undermine deniability."),
            ],
        ),
        GuidedWorkflow(
            id="headerless_inspection",
            title="Expert: Headerless Storage Inspection",
            description="Demonstrate what an external observer sees when inspecting protected storage.",
            steps=[
                GuidedStep(1, "Select a protected storage file.", "Choose any Vessel from Expert mode."),
                GuidedStep(2, "Run inspection.", "The inspection service reads the file without decrypting it."),
                GuidedStep(3, "Review inspection output.", "Expected output: no recognized header, no obvious magic bytes, and random-like entropy."),
                GuidedStep(4, "Do not treat inspection as proof of deniability.", "An absent header reduces obvious signals but does not remove every forensic trace."),
            ],
        ),
        GuidedWorkflow(
            id="multiple_faces",
            title="Expert: Multiple Disclosure Faces",
            description="Review how different credentials can access different disclosure faces without identifying one as primary.",
            steps=[
                GuidedStep(1, "A Vessel may carry more than one disclosure face.", "Each face uses different credentials. The Vessel does not record which face is primary."),
                GuidedStep(2, "Face labels stay neutral.", "Neutral labels avoid indicating which disclosure face is primary."),
                GuidedStep(3, "Opening one face does not expose the others.", "Normal access to one face provides no UI information about other faces."),
                GuidedStep(4, "Deniability remains procedural.", "Plausibility depends on operating context, not only on the technical design."),
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
