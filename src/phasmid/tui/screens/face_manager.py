from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Input, Label, Select, Static

from ...models.vessel import VesselMeta
from ...services.vessel_workflow_service import VesselWorkflowService
from .base import OperatorScreen


class FaceManagerScreen(OperatorScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
    ]

    DEFAULT_CSS = """
    FaceManagerScreen {
        background: $background;
        padding: 1 4;
    }
    FaceManagerScreen #face-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 0 0 1 0;
    }
    FaceManagerScreen #face-note {
        color: $text-muted;
        text-style: italic;
        padding: 0 0 1 0;
    }
    FaceManagerScreen #face-table {
        height: 8;
        border: solid $primary 50%;
        margin-bottom: 1;
    }
    FaceManagerScreen #plausibility-summary {
        min-height: 4;
        border: solid $primary 50%;
        padding: 1;
        margin-top: 1;
    }
    FaceManagerScreen .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, vessel: VesselMeta | None = None, **kwargs):
        super().__init__(**kwargs)
        self._vessel = vessel
        self._workflow = VesselWorkflowService()

    def compose(self) -> ComposeResult:
        vessel_name = self._vessel.name if self._vessel else "No vessel selected"
        yield self.webui_warning_banner()
        yield Static("DISCLOSURE FACES", id="face-title")
        yield Static(
            f"Vessel: [bold]{vessel_name}[/bold]\n\n"
            "Face labels are local metadata only. "
            "They do not affect the Vessel file or cryptographic structure.",
            id="face-note",
            markup=True,
        )
        table: DataTable = DataTable(id="face-table", cursor_type="row")
        yield table
        yield Label("Face id", classes="field-label")
        yield Select(
            [("Face A", "face_a"), ("Face B", "face_b")],
            id="face-id",
            value="face_a",
        )
        yield Label("Add face label", classes="field-label")
        yield Input(placeholder="Disclosure Face label (e.g. travel)", id="new-label")
        yield Button("Create Face", id="add-label-btn", variant="primary")
        yield Label("Passphrase", classes="field-label")
        yield Input(password=True, id="passphrase")
        yield Label("Restricted recovery passphrase", classes="field-label")
        yield Input(password=True, id="restricted-passphrase")
        yield Label("Target occupancy", classes="field-label")
        yield Input(value="15%", id="target-occupancy")
        yield Static("", id="plausibility-summary")
        yield Button("Inspect Plausibility", id="inspect-plausibility-btn")
        yield Button("Generate Plausibility", id="generate-plausibility-btn")
        yield Button("Clear Plausibility", id="clear-plausibility-btn")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Face", "Label", "Status", "Files", "Occupancy", "Last Accessed")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        if self._vessel and self._vessel.faces:
            for face in self._vessel.faces:
                table.add_row(
                    face.face_id,
                    face.label,
                    face.status,
                    str(face.file_count),
                    str(face.occupancy),
                    face.last_accessed or "-",
                )
        else:
            table.add_row("face_a", "Disclosure Face 1", "available", "0", "0", "-")
            table.add_row("face_b", "Disclosure Face 2", "available", "0", "0", "-")
        self._refresh_plausibility_summary()

    def _selected_face_id(self) -> str:
        return str(self.query_one("#face-id", Select).value)

    def _refresh_plausibility_summary(self) -> None:
        summary = self.query_one("#plausibility-summary", Static)
        if self._vessel is None:
            summary.update("No Vessel selected.")
            return
        face_id = self._selected_face_id()
        face = next((item for item in self._vessel.faces if item.face_id == face_id), None)
        if face is None:
            summary.update("No Face metadata recorded.")
            return
        profile = face.dummy_profile
        distribution = ", ".join(
            f"{ext}:{count}"
            for ext, count in sorted(profile.file_type_distribution.items())
        ) or "-"
        summary.update(
            "Plausibility Profile\n"
            f"Level: {profile.plausibility_level}  "
            f"Score: {profile.plausibility_score}  "
            f"Files: {profile.dummy_file_count}\n"
            f"Occupancy: {profile.occupancy_ratio * 100:.2f}%  "
            f"Size: {profile.dummy_total_size} bytes\n"
            f"Types: {distribution}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-label-btn":
            if self._vessel is None:
                self.app.notify("Select a Vessel first.", severity="warning")
                return
            face_id = self.query_one("#face-id", Select).value
            label = self.query_one("#new-label", Input).value.strip()
            try:
                face_result = self._workflow.create_face(
                    self._vessel.path,
                    str(face_id),
                    label=label,
                )
            except (FileNotFoundError, ValueError, OSError) as exc:
                self.app.notify(str(exc), severity="error")
                return
            self._vessel = face_result.vessel
            self._refresh_table()
            self.query_one("#new-label", Input).value = ""
            self.app.notify(
                f'Face "{face_result.face.face_id}" is ready.', severity="information"
            )
            return

        if event.button.id == "inspect-plausibility-btn":
            if self._vessel is None:
                self.app.notify("Select a Vessel first.", severity="warning")
                return
            try:
                profile_result = self._workflow.inspect_dummy_profile(
                    self._vessel.path,
                    self._selected_face_id(),
                )
            except (FileNotFoundError, ValueError, OSError) as exc:
                self.app.notify(str(exc), severity="error")
                return
            self._vessel = profile_result.vessel
            self._refresh_table()
            self.app.notify(profile_result.recommended_action, severity="information")
            return

        if event.button.id == "generate-plausibility-btn":
            if self._vessel is None:
                self.app.notify("Select a Vessel first.", severity="warning")
                return
            passphrase = self.query_one("#passphrase", Input).value
            restricted = self.query_one("#restricted-passphrase", Input).value
            target = self.query_one("#target-occupancy", Input).value.strip() or "15%"
            if not passphrase or not restricted:
                self.app.notify(
                    "Both passphrases are required for plausibility generation.",
                    severity="error",
                )
                return
            try:
                profile_result = self._workflow.generate_dummy_profile(
                    self._vessel.path,
                    passphrase,
                    restricted,
                    selector=self._selected_face_id(),
                    target_occupancy=target,
                )
            except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
                self.app.notify(str(exc), severity="error")
                return
            self._vessel = profile_result.vessel
            self._refresh_table()
            self.app.notify(profile_result.recommended_action, severity="information")
            return

        if event.button.id == "clear-plausibility-btn":
            if self._vessel is None:
                self.app.notify("Select a Vessel first.", severity="warning")
                return
            passphrase = self.query_one("#passphrase", Input).value
            restricted = self.query_one("#restricted-passphrase", Input).value
            if not passphrase or not restricted:
                self.app.notify(
                    "Both passphrases are required to clear generated content.",
                    severity="error",
                )
                return
            try:
                profile_result = self._workflow.clear_dummy_profile(
                    self._vessel.path,
                    passphrase,
                    restricted,
                    selector=self._selected_face_id(),
                )
            except (FileNotFoundError, ValueError, OSError) as exc:
                self.app.notify(str(exc), severity="error")
                return
            self._vessel = profile_result.vessel
            self._refresh_table()
            self.app.notify(profile_result.recommended_action, severity="information")
