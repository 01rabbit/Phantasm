from __future__ import annotations

import time
from typing import Literal

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.timer import Timer
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
    _SECURITY_NOTE = (
        "Object cue capture and recovery use the local camera feed. "
        "Position the bound object before running the operation."
    )

    def __init__(self, vessel_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self._vessel_path = vessel_path
        self._workflow = VesselWorkflowService()
        self._running = False
        self._started_at = 0.0
        self._tick_timer: Timer | None = None

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
        yield Static(self._SECURITY_NOTE, id="security-note")
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
        """Read and validate, then hand the slow part to a worker.

        Everything below the validation blocks for as long as the object cue
        takes to resolve - `collect_auth_sequence()` waits up to ten seconds
        for a match. Run inline from `on_button_pressed`, that froze the whole
        console for those ten seconds with nothing on screen to say why, which
        reads as a hang rather than as a device waiting to be shown something.
        Same defect as the generation freeze fixed in #156, at a smaller scale.
        """
        if self._running:
            return

        path = self.query_one("#vessel-path", Input).value.strip()
        operation = str(self.query_one("#operation-select", Select).value)
        face_selector_visible = operation in self._FACE_SELECTOR_OPERATIONS
        face = (
            str(self.query_one("#face-select", Select).value)
            if face_selector_visible
            else None
        )
        input_file = self.query_one("#input-file", Input).value.strip()
        output_file = self.query_one("#output-file", Input).value.strip()
        passphrase = self.query_one("#passphrase", Input).value
        restricted_passphrase = self.query_one("#restricted-passphrase", Input).value

        problem = self._validate(
            path=path,
            operation=operation,
            input_file=input_file,
            output_file=output_file,
            passphrase=passphrase,
            restricted_passphrase=restricted_passphrase,
        )
        if problem is not None:
            self.app.notify(problem, severity="error")
            return

        self._running = True
        self._started_at = time.monotonic()
        self._set_controls_enabled(False)
        self._tick_operation()
        self._tick_timer = self.set_interval(1.0, self._tick_operation)
        self._run_operation(
            path,
            operation,
            face,
            input_file,
            output_file,
            passphrase,
            restricted_passphrase,
        )

    def _validate(
        self,
        *,
        path: str,
        operation: str,
        input_file: str,
        output_file: str,
        passphrase: str,
        restricted_passphrase: str,
    ) -> str | None:
        """Everything answerable without touching the camera or the Vessel.

        Kept ahead of the worker so a missing field is still reported the
        instant the button is pressed, rather than after a ten-second wait for
        an object cue the operation was never going to use.
        """
        if not path:
            return "Vessel path is required."
        if operation == "add":
            if not input_file:
                return "Input file is required for add."
            if not passphrase or not restricted_passphrase:
                return "Both passphrases are required for add."
        elif operation == "list":
            if not passphrase:
                return "Passphrase is required for listing."
        else:
            if not passphrase:
                return "Passphrase is required for recovery."
            if operation == "retrieve" and not output_file:
                return "Output file is required for recovery."
            if operation != "retrieve":
                if not input_file:
                    return "Stored file name is required for removal."
                if not restricted_passphrase:
                    return "Restricted recovery passphrase is required for removal."
        return None

    def _tick_operation(self) -> None:
        """Say what the wait is for, and that it is bounded.

        The screen cannot show the camera, so the only honest thing it can do
        while the cue resolves is name the wait. Deliberately says nothing
        about whether a match has happened - that would report on the frame in
        front of the camera, which is #158's open half.
        """
        elapsed = int(time.monotonic() - self._started_at)
        try:
            note = self.query_one("#security-note", Static)
        except NoMatches:
            return
        note.update(
            "Waiting for the object cue...\n"
            f"Elapsed: {elapsed:02d}s\n"
            "Hold the bound object in front of the camera. The console stays "
            "responsive."
        )

    @work(thread=True, exclusive=True, group="open-vessel")
    def _run_operation(
        self,
        path: str,
        operation: str,
        face: str | None,
        input_file: str,
        output_file: str,
        passphrase: str,
        restricted_passphrase: str,
    ) -> None:
        try:
            # Add/Remove already named their face above; the operator marked
            # it before entering a passphrase. List/Recover haven't - which
            # face was actually reached is only known once the passphrase (and
            # object cue) resolve it below, so bookkeeping for those runs
            # after, not before.
            if operation in self._FACE_SELECTOR_OPERATIONS:
                self._workflow.open_vessel(path, face_id=str(face))
            access_cue_service.start()
            if operation == "add":
                store_result = self._workflow.add_file(
                    path,
                    input_file,
                    passphrase,
                    restricted_passphrase,
                    selector=str(face),
                    capture_reference=True,
                )
                message = (
                    f"Stored {store_result.bytes_stored:,} bytes in "
                    f"{store_result.vessel_path.name}."
                )
            elif operation == "list":
                listing = self._workflow.list_files(
                    path,
                    passphrase,
                    selector=None,
                    use_attempt_limiter=True,
                )
                self._workflow.open_vessel(path, face_id=listing.face.face_id)
                message = (
                    ", ".join(file.name for file in listing.files) or "No files stored."
                )
            elif operation == "retrieve":
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
                message = (
                    f"Recovered {retrieve_result.bytes_retrieved:,} bytes to "
                    f"{retrieve_result.output_path}."
                )
            else:
                removed = self._workflow.remove_file(
                    path,
                    input_file,
                    passphrase,
                    restricted_passphrase,
                    selector=str(face),
                )
                message = f"Removed file from {removed.face.face_id}."
        except PermissionError as exc:
            self.app.call_from_thread(self._finish_operation, str(exc), "warning")
            return
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
            self.app.call_from_thread(self._finish_operation, str(exc), "error")
            return
        finally:
            access_cue_service.close()

        self.app.call_from_thread(self._finish_operation, message, "information")

    def _finish_operation(
        self, message: str, severity: Literal["information", "warning", "error"]
    ) -> None:
        self._running = False
        if self._tick_timer is not None:
            self._tick_timer.stop()
            self._tick_timer = None
        # The screen can be dismissed while the worker is still waiting on the
        # camera; the thread cannot be interrupted, so its completion callback
        # has to tolerate an unmounted screen rather than raising into the app.
        if not self.is_mounted:
            return
        self._restore_security_note()
        self._set_controls_enabled(True)
        self.app.notify(
            message,
            title="Open Vessel",
            severity=severity,
            timeout=6,
        )
        if severity == "information":
            self.dismiss()

    def _restore_security_note(self) -> None:
        try:
            self.query_one("#security-note", Static).update(self._SECURITY_NOTE)
        except NoMatches:
            return

    def _set_controls_enabled(self, enabled: bool) -> None:
        try:
            self.query_one("#open-btn", Button).disabled = not enabled
        except NoMatches:
            return
