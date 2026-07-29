from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Static

from ...models.vessel import VesselMeta
from ...services.profile_service import load_profile
from ...services.vessel_service import VesselService
from ..banner import COMPACT_BANNER, get_banner
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
        text-align: left;
        padding: 1 4;
        height: auto;
        dock: top;
        background: $background;
    }
    SimpleHomeScreen #simple-subtitle {
        color: $text-muted;
        text-align: left;
        padding: 0 4;
        height: 2;
    }
    SimpleHomeScreen #health {
        height: 3;
        border: solid $primary 30%;
        padding: 0 2;
        margin: 1 0;
        content-align: left middle;
        color: $text-muted;
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
        self._profile = load_profile()
        self._vessels: list[VesselMeta] = []
        self._initial_vessel_path = initial_vessel_path

    _NEXT_STEP_DEFAULT = (
        "[bold]Choose an action:[/bold]  \\[o] Open selected   "
        "\\[n] New protected storage   \\[g] Guided help\n"
        "[dim]Advanced diagnostics and forensic detail are available "
        "under \\[e] Expert.[/dim]"
    )

    _NEXT_STEP_EMPTY = (
        "[bold]No protected storage found.[/bold]\n"
        "Press \\[n] to create one, or \\[g] for guided help."
    )

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static(COMPACT_BANNER, id="simple-title", markup=False)
        yield Static(
            "Protect or open local storage without exposing expert controls.",
            id="simple-subtitle",
        )
        yield Static(
            "Normal controls are ready. Press \\[e] Expert for diagnostics and technical detail.",
            id="health",
            markup=True,
        )
        yield Static("PROTECTED STORAGE", id="storage-label")
        yield DataTable(id="storage-table", cursor_type="row", zebra_stripes=True)
        yield Static(
            self._NEXT_STEP_DEFAULT,
            id="next-step",
            markup=True,
        )
        yield Footer()

    def on_mount(self) -> None:
        self._update_banner()
        table = self.query_one("#storage-table", DataTable)
        table.add_columns("Name", "Status", "Size", "Files")
        self._refresh_table()
        self.refresh_webui_status()

    def on_resize(self) -> None:
        self._update_banner()

    def _update_banner(self) -> None:
        force_compact = self._profile.compact_banner if self._profile else False
        banner = get_banner(self.app.size.width, compact=force_compact)
        self.query_one("#simple-title", Static).update(banner)

    def refresh_webui_status(self) -> None:
        super().refresh_webui_status()

    def _refresh_table(self) -> None:
        default_dir = self._profile.default_vessel_dir if self._profile else None
        self._vessels = self._svc.list_all(default_dir or None)
        table = self.query_one("#storage-table", DataTable)
        table.clear()
        initial_row = None
        for index, vessel in enumerate(self._vessels):
            file_count = (
                sum(face.file_count for face in vessel.faces) if vessel.faces else 0
            )
            table.add_row(
                vessel.name,
                "Open" if vessel.is_open else "Closed",
                vessel.size_human,
                str(file_count),
            )
            if (
                self._initial_vessel_path
                and str(vessel.path) == self._initial_vessel_path
            ):
                initial_row = index
        if initial_row is not None:
            table.move_cursor(row=initial_row)
        # Both branches must be assigned. Setting only the empty-state text left
        # "No protected storage found" on screen after the first Vessel was
        # created, contradicting the table directly above it.
        self.query_one("#next-step", Static).update(
            self._NEXT_STEP_EMPTY if not self._vessels else self._NEXT_STEP_DEFAULT
        )

    def _selected_path(self) -> str:
        table = self.query_one("#storage-table", DataTable)
        row = table.cursor_row
        if row < 0 or row >= len(self._vessels):
            return ""
        return str(self._vessels[row].path)

    def action_open_selected(self) -> None:
        from .open_vessel import OpenVesselScreen

        path = self._selected_path()
        if not path:
            self.app.notify("No protected storage is selected.", severity="warning")
            return
        self.app.push_screen(
            OpenVesselScreen(vessel_path=path), lambda _: self._refresh_table()
        )

    def action_new_storage(self) -> None:
        from .create_vessel import CreateVesselScreen

        self.app.push_screen(CreateVesselScreen(), lambda _: self._refresh_table())

    def action_guided(self) -> None:
        from .guided import GuidedScreen

        self.app.push_screen(GuidedScreen())

    def action_expert(self) -> None:
        from .home import HomeScreen

        self.app.push_screen(
            HomeScreen(initial_vessel_path=self._selected_path() or None),
            lambda _: self._refresh_table(),
        )

    def action_help(self) -> None:
        from .about import AboutScreen

        self.app.push_screen(AboutScreen())

    def action_refresh(self) -> None:
        self._profile = load_profile()
        self._refresh_table()
        self.app.notify("Protected storage list refreshed.", severity="information")

    def action_quit(self) -> None:
        self.app.exit()
