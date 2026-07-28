"""
Silent Standby screen for the TUI Operator Console.

This screen is displayed after standby activation. It contains no sensitive
content and no references to the true disclosure state.

Allowed content: maintenance status, diagnostics, storage checks, update
preparation, local system information.

Disallowed content: any reference to the true profile, vault contents,
protected entries, recognition mode, or restricted recovery state.
"""

from __future__ import annotations

import platform
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Footer, Static

from .base import OperatorScreen

_STANDBY_MESSAGE = """\
STANDBY MODE

Local system is in standby state.
No sensitive operations are available.

To return to normal operation, re-authentication is required.
"""

_MAINTENANCE_ITEMS = [
    "Storage integrity check: OK",
    "Configuration directory: accessible",
    "Local services: idle",
    "Background tasks: none",
    "System clock: synchronized",
]


class StandbyScreen(OperatorScreen):
    """
    Non-sensitive standby screen.

    Displayed after hotkey-triggered standby activation. Contains only
    maintenance-style information. No sensitive UI references.
    """

    BINDINGS = [
        Binding("ctrl+r", "request_recovery", "Re-authenticate", show=True),
        Binding("escape", "request_recovery", "Re-authenticate", show=False),
    ]

    DEFAULT_CSS = """
    StandbyScreen {
        background: $background;
        padding: 1 4;
    }
    StandbyScreen #standby-banner {
        text-align: center;
        color: $text-muted;
        text-style: bold;
        padding: 1 0;
        height: 3;
        dock: top;
    }
    StandbyScreen #status-title {
        color: $text-muted;
        text-style: bold;
        padding: 1 0 0 0;
    }
    StandbyScreen #maintenance-panel {
        height: 10;
        border: solid $foreground-muted;
        padding: 1 2;
        color: $text-muted;
        margin: 0 0 1 0;
    }
    StandbyScreen #time-panel {
        color: $text-muted;
        height: 2;
        margin: 0 0 1 0;
    }
    StandbyScreen #recover-btn {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("[ STANDBY ]", id="standby-banner")
        yield Static("SYSTEM STATUS", id="status-title")
        yield Static("", id="maintenance-panel", markup=False)
        yield Static("", id="time-panel", markup=False)
        yield Button("Re-authenticate to continue", id="recover-btn", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()
        self.set_interval(5, self._refresh_status)

    def _refresh_status(self) -> None:
        lines = list(_MAINTENANCE_ITEMS)
        panel = self.query_one("#maintenance-panel", Static)
        panel.update("\n".join(lines))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        node = platform.node() or "local"
        time_panel = self.query_one("#time-panel", Static)
        time_panel.update(f"Time: {now}  |  Host: {node}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "recover-btn":
            self.action_request_recovery()

    def action_request_recovery(self) -> None:
        """Signal that the operator wants to re-authenticate and return to active."""
        self.dismiss(True)
