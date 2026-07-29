from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Footer, Input, Label, Select, Static

from ...services.access_cue_service import access_cue_service
from ...services.vessel_workflow_service import VesselWorkflowService
from .base import OperatorScreen


class OpenVesselScreen(OperatorScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
    ]

    DEFAULT_CSS = """
    OpenVesselScreen {
        background: $background;
        padding: 1 4;
    }
    OpenVesselScreen #open-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 0 0 1 0;
    }
    OpenVesselScreen .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    OpenVesselScreen #security-note {
        color: $text-muted;
        text-style: italic;
        padding: 1 0;
    }
    OpenVesselScreen #webui-redirect-note {
        color: $text-muted;
        text-style: italic;
        padding: 0 0 1 0;
    }
    OpenVesselScreen #open-btn {
        margin-top: 2;
        width: 100%;
    }
    """

    _FACE_OPTIONS = [
        ("Disclosure Face 1", "face_a"),
        ("Disclosure Face 2", "face_b"),
    ]
    # Add File is deactivated here (#169): fully duplicated by the WebUI's
    # role-gated /store, and the current demo flow registers both Faces there
    # instead. The "add" code path below is deliberately left in place rather
    # than deleted - restoring the option is a one-line revert.
    #
    # Recover File stays active, unlike the issue's suggested scope: it is
    # the only *verified* way to demonstrate the object-absent refusal (the
    # demo's central cue-not-key proof) - the WebUI /retrieve equivalent has
    # not been separately confirmed for that specific case. Deactivate it
    # once that verification happens; until then, removing it here would
    # break the live demo's most important beat with no tested fallback.
    _OPERATION_OPTIONS = [
        ("List Files", "list"),
        ("Recover File", "retrieve"),
        ("Remove File", "remove"),
    ]
    # Add/Remove manage which face a file lives on and cannot avoid saying so:
    # there is no passphrase yet to resolve it from for a fresh Add, and
    # Remove needs the same explicit target. Recover and List have an
    # existing passphrase (and object cue) that already identifies the face,
    # so asking the operator to also name one first would only be handing an
    # onlooker, for free, the fact that more than one face exists.
    _FACE_SELECTOR_OPERATIONS = ("add", "remove")
    _OUTPUT_FILE_OPERATIONS = ("retrieve",)

    def __init__(self, vessel_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self._vessel_path = vessel_path
        self._workflow = VesselWorkflowService()

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("OPEN VESSEL", id="open-title")
        yield Label("Vessel path", classes="field-label")
        yield Input(
            value=self._vessel_path, placeholder="Path to Vessel file", id="vessel-path"
        )
        yield Label("Disclosure Face", classes="field-label", id="face-select-label")
        yield Select(
            [(label, val) for label, val in self._FACE_OPTIONS],
            id="face-select",
            value="face_a",
        )
        yield Label("Operation", classes="field-label")
        yield Select(
            [(label, val) for label, val in self._OPERATION_OPTIONS],
            id="operation-select",
            value="retrieve",
        )
        yield Static(
            "Add File now runs through the WebUI's Store page (store role) - "
            "see Access Tokens. This screen still handles Recover File, "
            "List Files, and Remove File.",
            id="webui-redirect-note",
        )
        yield Label("Input file (store)", classes="field-label", id="input-file-label")
        yield Input(placeholder="Path to local file or stored name", id="input-file")
        yield Label(
            "Output file (recover)", classes="field-label", id="output-file-label"
        )
        yield Input(placeholder="~/Documents/recovered.bin", id="output-file")
        yield Label("Passphrase", classes="field-label")
        yield Input(password=True, id="passphrase")
        yield Label(
            "Restricted recovery passphrase (store)",
            classes="field-label",
            id="restricted-passphrase-label",
        )
        yield Input(password=True, id="restricted-passphrase")
        yield Static(
            "Object cue capture and recovery use the local camera feed. "
            "Position the bound object before running the operation.",
            id="security-note",
        )
        yield Button("Run Operation", id="open-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._sync_field_visibility()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "operation-select":
            self._sync_field_visibility()

    def _sync_field_visibility(self) -> None:
        operation = self.query_one("#operation-select", Select).value
        face_needed = operation in self._FACE_SELECTOR_OPERATIONS
        output_needed = operation in self._OUTPUT_FILE_OPERATIONS
        # Input file is only meaningful alongside the face selector: it names
        # what to store (Add) or what to remove (Remove), both of which
        # already require naming the face explicitly.
        input_needed = face_needed

        self.query_one("#face-select-label", Label).display = face_needed
        self.query_one("#face-select", Select).display = face_needed
        self.query_one("#input-file-label", Label).display = input_needed
        self.query_one("#input-file", Input).display = input_needed
        self.query_one("#output-file-label", Label).display = output_needed
        self.query_one("#output-file", Input).display = output_needed
        self.query_one("#restricted-passphrase-label", Label).display = face_needed
        self.query_one("#restricted-passphrase", Input).display = face_needed

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-btn":
            self._attempt_open()

    def _attempt_open(self) -> None:
        path = self.query_one("#vessel-path", Input).value.strip()
        operation = self.query_one("#operation-select", Select).value
        face_selector_visible = operation in self._FACE_SELECTOR_OPERATIONS
        face = (
            self.query_one("#face-select", Select).value
            if face_selector_visible
            else None
        )
        input_file = self.query_one("#input-file", Input).value.strip()
        output_file = self.query_one("#output-file", Input).value.strip()
        passphrase = self.query_one("#passphrase", Input).value
        restricted_passphrase = self.query_one("#restricted-passphrase", Input).value

        if not path:
            self.app.notify("Vessel path is required.", severity="error")
            return

        try:
            # Add/Remove already named their face above; the operator marked
            # it before entering a passphrase. List/Recover haven't - which
            # face was actually reached is only known once the passphrase (and
            # object cue) resolve it below, so bookkeeping for those runs
            # after, not before.
            if face_selector_visible:
                self._workflow.open_vessel(path, face_id=str(face))
            access_cue_service.start()
            if operation == "add":
                if not input_file:
                    self.app.notify("Input file is required for add.", severity="error")
                    return
                if not passphrase or not restricted_passphrase:
                    self.app.notify(
                        "Both passphrases are required for add.",
                        severity="error",
                    )
                    return
                store_result = self._workflow.add_file(
                    path,
                    input_file,
                    passphrase,
                    restricted_passphrase,
                    selector=str(face),
                    capture_reference=True,
                )
                self.app.notify(
                    f"Stored {store_result.bytes_stored:,} bytes in "
                    f"{store_result.vessel_path.name}.",
                    title="Open Vessel",
                    severity="information",
                    timeout=6,
                )
            elif operation == "list":
                if not passphrase:
                    self.app.notify(
                        "Passphrase is required for listing.", severity="error"
                    )
                    return
                listing = self._workflow.list_files(
                    path,
                    passphrase,
                    selector=None,
                    use_attempt_limiter=True,
                )
                self._workflow.open_vessel(path, face_id=listing.face.face_id)
                names = (
                    ", ".join(file.name for file in listing.files) or "No files stored."
                )
                self.app.notify(
                    names,
                    title="Open Vessel",
                    severity="information",
                    timeout=6,
                )
            else:
                if not passphrase:
                    self.app.notify(
                        "Passphrase is required for recovery.", severity="error"
                    )
                    return
                if operation == "retrieve" and not output_file:
                    self.app.notify(
                        "Output file is required for recovery.",
                        severity="error",
                    )
                    return
                if operation == "retrieve":
                    retrieve_result = self._workflow.retrieve_file(
                        path,
                        passphrase,
                        output_path=output_file,
                        selector=None,
                        use_attempt_limiter=True,
                    )
                    self._workflow.open_vessel(
                        path,
                        face_id=self._workflow.resolve_face_id(retrieve_result.mode),
                    )
                    self.app.notify(
                        f"Recovered {retrieve_result.bytes_retrieved:,} bytes to "
                        f"{retrieve_result.output_path}.",
                        title="Open Vessel",
                        severity="information",
                        timeout=6,
                    )
                else:
                    if not input_file:
                        self.app.notify(
                            "Stored file name is required for removal.",
                            severity="error",
                        )
                        return
                    if not restricted_passphrase:
                        self.app.notify(
                            "Restricted recovery passphrase is required for removal.",
                            severity="error",
                        )
                        return
                    removed = self._workflow.remove_file(
                        path,
                        input_file,
                        passphrase,
                        restricted_passphrase,
                        selector=str(face),
                    )
                    self.app.notify(
                        f"Removed file from {removed.face.face_id}.",
                        title="Open Vessel",
                        severity="information",
                        timeout=6,
                    )
        except PermissionError as exc:
            self.app.notify(str(exc), title="Open Vessel", severity="warning")
            return
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
            self.app.notify(str(exc), title="Open Vessel", severity="error")
            return
        finally:
            access_cue_service.close()

        self.dismiss()
