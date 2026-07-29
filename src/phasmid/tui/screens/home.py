from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Static

from ...config import PHASMID_LUKS_MODE
from ...models.vessel import VesselMeta
from ...services.profile_service import load_profile
from ...services.vessel_service import VesselService
from ..banner import COMPACT_BANNER, get_banner
from ..widgets.event_log import EventLog
from ..widgets.status_panel import VesselSummaryPanel
from ..widgets.vessel_table import VesselTable
from ..widgets.warning_box import WarningBox
from .base import OperatorScreen

if TYPE_CHECKING:
    from ..app import PhasmidApp


class HomeScreen(OperatorScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("o", "open_vessel", "Open"),
        Binding("x", "close_vessel", "Close"),
        Binding("c", "create_vessel", "Create"),
        Binding("i", "inspect_vessel", "Inspect"),
        Binding("f", "face_manager", "Faces"),
        Binding("g", "guided", "Guided"),
        Binding("a", "audit", "Audit"),
        Binding("d", "doctor", "Doctor"),
        Binding("s", "settings", "Settings"),
        Binding("t", "access_tokens", "Tokens"),
        Binding("l", "luks_panel", "LUKS"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_vessels", "Refresh", show=False),
        Binding("slash", "about", "About", show=False),
    ]

    DEFAULT_CSS = """
    HomeScreen {
        background: $background;
    }
    HomeScreen #compact-banner {
        color: $primary;
        text-align: left;
        padding: 1 4;
        height: auto;
        dock: top;
        background: $background;
    }
    HomeScreen #profile-status {
        color: $text-muted;
        padding: 0 4 0 4;
        height: 1;
        dock: top;
        background: $background;
    }
    HomeScreen #doctor-badge {
        height: 1;
        dock: top;
        padding: 0 4;
        background: $background;
        display: none;
    }
    HomeScreen #webui-warning-panel {
        margin: 0 4 1 4;
        display: none;
    }
    HomeScreen #main-layout {
        height: 1fr;
        layout: horizontal;
    }
    HomeScreen #vessel-column {
        width: 46;
    }
    HomeScreen #vessel-panel {
        height: 1fr;
    }
    HomeScreen #summary-panel {
        width: 1fr;
    }
    HomeScreen #event-log {
        height: 7;
        dock: bottom;
    }
    """

    def __init__(self, initial_vessel_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._vessel_svc = VesselService()
        self._profile = load_profile()
        self._initial_vessel_path = initial_vessel_path
        self._vessels: list[VesselMeta] = []

    def compose(self) -> ComposeResult:
        from textual.containers import Container, Horizontal

        yield self.webui_warning_banner()
        yield Static(COMPACT_BANNER, id="compact-banner", markup=False)
        yield Static("", id="profile-status", markup=True)
        yield Static("", id="doctor-badge", markup=True)
        yield WarningBox(
            "WebUI active.",
            level="error",
            id="webui-warning-panel",
        )
        with Horizontal(id="main-layout"):
            with Container(id="vessel-column"):
                yield VesselTable(id="vessel-panel")
            yield VesselSummaryPanel(id="summary-panel")
        yield EventLog(id="event-log")
        yield Footer()

    def on_mount(self) -> None:
        self._update_banner()
        self._refresh_vessels()
        self._update_profile_status()
        self.refresh_webui_status()
        self._log("Phasmid operator console ready.")
        self._run_startup_checks()
        self.set_interval(1, self._update_summary)

    def on_resize(self) -> None:
        self._update_banner()

    def refresh_webui_status(self) -> None:
        super().refresh_webui_status()
        try:
            warning = self.query_one("#webui-warning-panel", WarningBox)
        except NoMatches:
            return
        app = cast("PhasmidApp", self.app)
        is_running = app.webui_svc.is_running()
        warning.update_message(
            self.webui_running_message().replace(" - PRESS \\[w] TO RETRACT", "")
        )
        warning.display = is_running

    def _update_profile_status(self) -> None:
        name = self._profile.name if self._profile else "default"
        vessel_count = len(self._vessels)
        text = f"[dim]PROFILE:[/dim] {name}   [dim]VESSELS:[/dim] {vessel_count}"
        self.query_one("#profile-status", Static).update(text)

    def _update_banner(self) -> None:
        force_compact = self._profile.compact_banner if self._profile else False
        banner = get_banner(self.app.size.width, compact=force_compact)
        self.query_one("#compact-banner", Static).update(banner)

    def _refresh_vessels(self) -> None:
        self._vessels = self._vessel_svc.list_all(
            self._profile.default_vessel_dir or None
        )
        table = self.query_one(VesselTable)
        table.update_vessels(self._vessels)
        self._update_summary()
        try:
            self._update_profile_status()
        except Exception:
            pass

    def _update_summary(self) -> None:
        table = self.query_one(VesselTable)
        vessel = table.selected_vessel
        panel = self.query_one(VesselSummaryPanel)
        panel.update_vessel(vessel)

    def _run_startup_checks(self) -> None:
        from ...models.doctor import DoctorLevel
        from ...services.doctor_service import DoctorService

        result = DoctorService().run()
        fail = [c for c in result.checks if c.level == DoctorLevel.FAIL]
        warn = [c for c in result.checks if c.level == DoctorLevel.WARN]
        ok_count = sum(1 for c in result.checks if c.level == DoctorLevel.OK)

        if fail:
            self._log(
                f"Doctor: {len(fail)} FAIL, {len(warn)} WARN — press d to review.",
                "error",
            )
            for c in fail:
                self._log(f"  ✗ {c.name}: {c.message}", "error")
        elif warn:
            self._log(
                f"Doctor: {ok_count} OK, {len(warn)} WARN — press d to review.",
                "warn",
            )
            for c in warn:
                self._log(f"  ! {c.name}: {c.message}", "warn")
        else:
            self._log(f"Doctor: {ok_count} OK — environment checks passed.", "ok")

        self._update_doctor_badge(len(fail), len(warn))

    def _update_doctor_badge(self, fail_count: int, warn_count: int) -> None:
        badge = self.query_one("#doctor-badge", Static)
        if fail_count:
            badge.update(
                f"[bold red]✗ SYSTEM: {fail_count} FAIL"
                + (f", {warn_count} WARN" if warn_count else "")
                + " — press \\[d] to review[/bold red]"
            )
            badge.display = True
        elif warn_count:
            badge.update(
                f"[yellow]! SYSTEM: {warn_count} WARN — press \\[d] to review[/yellow]"
            )
            badge.display = True
        else:
            badge.display = False

    def _log(self, msg: str, level: str = "info") -> None:
        try:
            self.query_one(EventLog).log_event(msg, level)
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_summary()

    def action_refresh_vessels(self) -> None:
        self._refresh_vessels()
        self._run_startup_checks()
        self._log("Vessel list refreshed.")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Footer cells sit at fixed offsets, so anything past the terminal
        # width is simply not drawn - and `w` (WebUI), an app-level binding
        # appended after the screen's own, is the first to be lost. Every
        # binding this screen shows costs columns, so a binding for a
        # subsystem that is switched off should not spend any: LUKS is
        # disabled by default and its panel only reports that fact.
        # Textual treats False as "disabled and not shown"; None would keep
        # the cell and only grey it out, which would not free any columns.
        if action == "luks_panel" and PHASMID_LUKS_MODE.strip().lower() == "disabled":
            return False
        return True

    def action_luks_panel(self) -> None:
        if PHASMID_LUKS_MODE.strip().lower() == "disabled":
            self.app.notify("LUKS layer is disabled.", severity="warning")
            return
        from .luks_screen import LuksScreen

        self.app.push_screen(LuksScreen())

    def action_open_vessel(self) -> None:
        from .confirm_modal import ConfirmModal
        from .open_vessel import OpenVesselScreen

        table = self.query_one(VesselTable)
        vessel = table.selected_vessel
        path = str(vessel.path) if vessel else ""

        def _on_confirm(result: bool | None) -> None:
            if result:
                self.app.push_screen(
                    OpenVesselScreen(vessel_path=path),
                    lambda _result: self._refresh_vessels(),
                )

        self.app.push_screen(
            ConfirmModal(
                "VESSEL DISCLOSURE",
                "You are about to disclose a vessel face.\nPassphrase will be required.",
            ),
            _on_confirm,
        )

    def action_close_vessel(self) -> None:
        from ...services.vessel_workflow_service import VesselWorkflowService
        from .confirm_modal import ConfirmModal

        table = self.query_one(VesselTable)
        vessel = table.selected_vessel
        path = str(vessel.path) if vessel else ""
        if not path:
            self.app.notify("Select a Vessel first.", severity="warning")
            return

        def _on_confirm(result: bool | None) -> None:
            if result:
                try:
                    closed = VesselWorkflowService().close_vessel(path)
                except FileNotFoundError as exc:
                    self.app.notify(str(exc), severity="error")
                    return
                self._refresh_vessels()
                self._log(f"Vessel closed: {closed.vessel.name}", "info")
                self.app.notify("Vessel closed.", severity="information")

        self.app.push_screen(
            ConfirmModal(
                "CLOSE VESSEL",
                "You are about to close the selected Vessel.\nThis preserves local metadata.",
            ),
            _on_confirm,
        )

    def action_create_vessel(self) -> None:
        from .confirm_modal import ConfirmModal
        from .create_vessel import CreateVesselScreen

        def _on_confirm(result: bool | None) -> None:
            if result:
                self.app.push_screen(
                    CreateVesselScreen(), lambda _result: self._refresh_vessels()
                )

        self.app.push_screen(
            ConfirmModal(
                "NEW VESSEL INITIALIZATION",
                "You are about to create a new deniable container.\nThis operation cannot be undone.",
            ),
            _on_confirm,
        )

    def action_inspect_vessel(self) -> None:
        from .inspect_vessel import InspectVesselScreen

        table = self.query_one(VesselTable)
        vessel = table.selected_vessel
        path = str(vessel.path) if vessel else ""
        self.app.push_screen(InspectVesselScreen(vessel_path=path))

    def action_face_manager(self) -> None:
        from .face_manager import FaceManagerScreen

        table = self.query_one(VesselTable)
        vessel = table.selected_vessel
        self.app.push_screen(
            FaceManagerScreen(vessel=vessel), lambda _result: self._refresh_vessels()
        )

    def action_guided(self) -> None:
        from .guided import GuidedScreen

        self.app.push_screen(GuidedScreen())

    def action_audit(self) -> None:
        from .audit import AuditScreen

        self.app.push_screen(AuditScreen())

    def action_doctor(self) -> None:
        from .doctor import DoctorScreen

        self.app.push_screen(DoctorScreen())

    def action_settings(self) -> None:
        from .settings import SettingsScreen

        def _after_settings(_):
            self._profile = load_profile()
            self._refresh_vessels()

        self.app.push_screen(SettingsScreen(), _after_settings)

    def action_about(self) -> None:
        from .about import AboutScreen

        self.app.push_screen(AboutScreen())

    def action_access_tokens(self) -> None:
        from .access_tokens import AccessTokenScreen

        self.app.push_screen(AccessTokenScreen())

    def action_help(self) -> None:
        from .about import AboutScreen

        self.app.push_screen(AboutScreen())

    def action_quit(self) -> None:
        self.app.exit()
