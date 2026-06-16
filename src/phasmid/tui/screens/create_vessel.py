from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Footer, Input, Label, Select, Static

from ...services.vessel_service import VesselService
from ...services.vessel_workflow_service import VesselWorkflowService
from .base import OperatorScreen

_SIZE_OPTIONS = [
    ("64 MiB", "64M"),
    ("128 MiB", "128M"),
    ("256 MiB", "256M"),
    ("512 MiB", "512M"),
    ("1 GiB", "1G"),
    ("2 GiB", "2G"),
    ("Custom", "custom"),
]


class CreateVesselScreen(OperatorScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
    ]

    DEFAULT_CSS = """
    CreateVesselScreen {
        background: $background;
        padding: 1 4;
    }
    CreateVesselScreen #create-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 0 0 1 0;
    }
    CreateVesselScreen .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    CreateVesselScreen #warning-area {
        color: $warning;
        min-height: 2;
        padding: 0 0 1 0;
    }
    CreateVesselScreen #create-btn {
        margin-top: 2;
        width: 100%;
    }
    """

    def __init__(self, initial_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self._initial_path = initial_path
        self._svc = VesselService()
        self._workflow = VesselWorkflowService()

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("NEW VESSEL", id="create-title")
        yield Label("Vessel path", classes="field-label")
        yield Input(
            value=self._initial_path,
            placeholder="e.g. ~/Documents/travel.vessel",
            id="vessel-path",
        )
        yield Label("Container size", classes="field-label")
        yield Select(
            [(label, value) for label, value in _SIZE_OPTIONS],
            id="vessel-size",
            value="512M",
        )
        yield Label("Non-sensitive label (optional)", classes="field-label")
        yield Input(placeholder="e.g. travel", id="vessel-label")
        yield Static("", id="warning-area")
        yield Button("Create Vessel", id="create-btn", variant="primary")
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "vessel-path":
            self._update_warnings(event.value)

    def _update_warnings(self, path: str) -> None:
        warn_area = self.query_one("#warning-area", Static)
        if not path:
            warn_area.update("")
            return
        warnings = self._svc.check_filename_warnings(path)
        p = Path(path).expanduser()
        if p.exists():
            warnings.insert(
                0, f"File already exists: {path}. Creating will overwrite it."
            )
        warn_area.update("\n".join(f"!  {w}" for w in warnings))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-btn":
            self._attempt_create()

    def _attempt_create(self) -> None:
        path = self.query_one("#vessel-path", Input).value.strip()
        size = self.query_one("#vessel-size", Select).value
        label = self.query_one("#vessel-label", Input).value.strip()
        if not path:
            self.query_one("#warning-area", Static).update(
                "!  Vessel path is required."
            )
            return

        p = Path(path).expanduser()
        try:
            result = self._workflow.create_vessel(str(p), str(size), label=label)
        except FileExistsError:
            self.query_one("#warning-area", Static).update(
                "!  File already exists. Choose another path."
            )
            return
        except (ValueError, OSError) as exc:
            self.app.notify(str(exc), title="Create Vessel", severity="error")
            return

        self._svc.register(result.vessel_path)
        self.app.notify(
            f"Local container initialized at {result.vessel_path.name} "
            f"({result.size_bytes:,} bytes).",
            title="Create Vessel",
            severity="information",
            timeout=6,
        )
        self.dismiss()
