from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Static

from ...models.vessel import VesselMeta
from ...services.vessel_service import VesselService
from .base import OperatorScreen


class SimpleHomeScreen(OperatorScreen):
    """Low-cognitive-load entry point for normal Phasmid use."""

    BINDINGS = [
        Binding("o", "open_selected", "Open"),
        Binding("n", "new_storage", "New"),
        Binding("g", "guided", "Guided"),
        Binding("e", "expert", "Expert"),
        Binding("question_mark", "help", "Help", show=False),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh", show=False),
    ]

    DEFAULT_CSS = """
    SimpleHomeScreen {
        background: $background;
        padding: 1 3;
    }
    SimpleHomeScreen #simple-title {
        color: $primary;
        text-style: bold;
        text-align: center;
        padding: 1 0 0 0;
        height: 3;
    }
    SimpleHomeScreen #simple-subtitle {
        color: $text-muted;
        text-align: center;
        height: 2;
    }
    SimpleHomeScreen #health {
        height: 3;
        border: solid $success 40%;
        padding: 0 2;
        margin: 1 0;
        content-align: left middle;
    }
    SimpleHomeScreen #storage-label {
        color: $text-muted;
        height: 2;
        padding-top: 1;
    }
    SimpleHomeScreen #storage-table {
        height: 1fr;
        border: solid $primary 40%;
        background: $surface;
    }
    SimpleHomeScreen #next-step {
        min-height: 4;
        margin-top: 1;
        border: solid $primary 25%;
        padding: 1 2;
        color: $text;
    }
    """

    def __init__(self, initial_vessel_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._svc = VesselService()
        self._vessels: list[VesselMeta] = []
        self._initial_vessel_path = initial_vessel_path

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("PHASMID", id="simple-title")
        yield Static("Protect or open local storage without exposing expert controls.", id="simple-subtitle")
        yield Static("[green]✓[/green] Device ready for local use", id="health", markup=True)
        yield Static("PROTECTED STORAGE", id="storage-label")
        yield DataTable(id="storage-table", cursor_type="row", zebra_stripes=True)
        yield Static(
            "[bold]Choose an action:[/bold]  [o] Open selected   [n] New protected storage   "
            "[g] Guided help\n[dim]Advanced diagnostics and forensic detail are available under [e] Expert.[/dim]",
            id="next-step",
            markup=True,
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#storage-table", DataTable)
        table.add_columns("Name", "Status", "Size", "Files")
        self._refresh_table()
        self.refresh_webui_status()

    def refresh_webui_status(self) -> None:
        super().refresh_webui_status()

    def _refresh_table(self) -> None:
        self._vessels = self._svc.list_all(None)
        table = self.query_one("#storage-table", DataTable)
        table.clear()
        for vessel in self._vessels:
            file_count = sum(face.file_count for face in vessel.faces) if vessel.faces else 0
            table.add_row(
                vessel.name,
                "Open" if vessel.is_open else "Closed",
                vessel.size_human,
                str(file_count),
                key=str(vessel.path),
            )
        if not self._vessels:
            self.query_one("#next-step", Static).update(
                "[bold]No protected storage found.[/bold]\n"
                "Press [n] to create one, or [g] for guided help."
            )

    def _selected_path(self) -> str:
        table = self.query_one("#storage-table", DataTable)
        if table.row_count == 0 or table.cursor_row < 0:
            return ""
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return str(row_key.value) if row_key else ""

    def action_open_selected(self) -> None:
        from .open_vessel import OpenVesselScreen

        path = self._selected_path()
        if not path:
            self.app.notify("No protected storage is selected.", severity="warning")
            return
        self.app.push_screen(OpenVesselScreen(vessel_path=path), lambda _: self._refresh_table())

    def action_new_storage(self) -> None:
        from .create_vessel import CreateVesselScreen

        self.app.push_screen(CreateVesselScreen(), lambda _: self._refresh_table())

    def action_guided(self) -> None:
        from .guided import GuidedScreen

        self.app.push_screen(GuidedScreen())

    def action_expert(self) -> None:
        from .home import HomeScreen

        self.app.push_screen(HomeScreen(initial_vessel_path=self._selected_path() or None))

    def action_help(self) -> None:
        from .about import AboutScreen

        self.app.push_screen(AboutScreen())

    def action_refresh(self) -> None:
        self._refresh_table()
        self.app.notify("Protected storage list refreshed.", severity="information")

    def action_quit(self) -> None:
        self.app.exit()
