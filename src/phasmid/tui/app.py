from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key

from ..config import standby_hotkey
from ..services.webui_service import WebUIService
from ..standby_state import StandbyStateMachine
from .screens.simple_home import SimpleHomeScreen
from .theme import PHASMID_DARK, PHASMID_LIGHT


class PhasmidApp(App):
    """Phasmid TUI Operator Console."""

    TITLE = "Phasmid"
    SUB_TITLE = "Janus Eidolon System"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("w", "toggle_webui", "WebUI"),
        Binding(standby_hotkey(), "trigger_standby", "Standby", show=False),
    ]

    CSS = """
    Screen {
        background: #0d0d0d;
    }
    """

    def __init__(
        self,
        initial_screen: str = "home",
        vessel_path: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._initial_screen = initial_screen
        self._vessel_path = vessel_path
        self.webui_svc = WebUIService()
        self.webui_svc.set_timeout_callback(self._on_webui_timeout)
        self.standby = StandbyStateMachine()

    def on_mount(self) -> None:
        try:
            self.register_theme(PHASMID_DARK)
            self.register_theme(PHASMID_LIGHT)
            self.theme = "phasmid-dark"
        except Exception:
            pass

        screen_map = {
            "home": self._push_home,
            "guided": self._push_guided,
            "audit": self._push_audit,
            "doctor": self._push_doctor,
            "inspect": self._push_inspect,
            "create": self._push_create,
            "open": self._push_open,
            "luks": self._push_luks,
            "about": self._push_about,
        }
        action = screen_map.get(self._initial_screen, self._push_home)
        action()
        self.set_interval(1, self._refresh_webui_status)
        self._refresh_webui_status()

    def compose(self) -> ComposeResult:
        return iter([])

    def on_key(self, event: Key) -> None:
        """Reset WebUI inactivity timer on any key press."""
        self.webui_svc.reset_timer()

    def action_toggle_webui(self) -> None:
        """Toggle WebUI start/stop."""
        # `w` is an app-level binding and stays live on the Standby screen.
        # Starting the WebUI from a sealed state would re-expose the operator
        # surface that standby just retracted.
        if not self.standby.is_active() and not self.webui_svc.is_running():
            return
        if self.webui_svc.is_running():
            from .screens.confirm_modal import ConfirmModal

            def _on_confirm(result: bool | None) -> None:
                if result:
                    self.webui_svc.stop()
                    self.notify(
                        "WebUI server stopped.", title="WEBUI", severity="warning"
                    )
                    self._refresh_webui_status()

            self.push_screen(
                ConfirmModal(
                    "RETRACT WEB INTERFACE",
                    "You are about to shut down the WebUI server.\nAll active browser sessions will be disconnected.",
                ),
                _on_confirm,
            )
        else:
            if self.webui_svc.start():
                token = self.webui_svc.access_token()
                message = f"WebUI active at {self.webui_svc.access_url()}"
                if token:
                    message += f"\nAccess token: {token}"
                self.notify(
                    message,
                    title="WEBUI EXPOSED",
                    severity="information",
                    timeout=30,
                )
            else:
                log_path = self.webui_svc.log_file
                self.notify(
                    f"Failed to start WebUI server. Check log: {log_path}",
                    title="ERROR",
                    severity="error",
                )
            self._refresh_webui_status()

    def _on_webui_timeout(self) -> None:
        """Called when WebUI is auto-killed."""
        self.notify(
            "WebUI auto-killed due to inactivity (Stealth Mode).",
            title="SECURITY",
            severity="warning",
            timeout=10,
        )
        self._refresh_webui_status()

    def _refresh_webui_status(self) -> None:
        """Inform screens that WebUI status changed."""
        for screen in self.screen_stack:
            if hasattr(screen, "refresh_webui_status"):
                screen.refresh_webui_status()

    def _push_home(self) -> None:
        self.push_screen(SimpleHomeScreen(initial_vessel_path=self._vessel_path))

    def _push_guided(self) -> None:
        from .screens.guided import GuidedScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(GuidedScreen())

    def _push_audit(self) -> None:
        from .screens.audit import AuditScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(AuditScreen())

    def _push_doctor(self) -> None:
        from .screens.doctor import DoctorScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(DoctorScreen())

    def _push_inspect(self) -> None:
        from .screens.inspect_vessel import InspectVesselScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(InspectVesselScreen(vessel_path=self._vessel_path))

    def _push_create(self) -> None:
        from .screens.create_vessel import CreateVesselScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(CreateVesselScreen(initial_path=self._vessel_path or ""))

    def _push_open(self) -> None:
        from .screens.open_vessel import OpenVesselScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(OpenVesselScreen(vessel_path=self._vessel_path or ""))

    def _push_about(self) -> None:
        from .screens.about import AboutScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(AboutScreen())

    def _push_luks(self) -> None:
        from .screens.luks_screen import LuksScreen

        self.push_screen(SimpleHomeScreen())
        self.push_screen(LuksScreen())

    def action_trigger_standby(self) -> None:
        """Hotkey-triggered standby: clear sensitive UI and enter sealed state."""
        if not self.standby.is_active():
            return

        from .screens.standby import StandbyScreen

        try:
            self.standby.trigger_standby()
        except Exception:
            return

        # Concealing the local screen is not enough: while the WebUI keeps
        # serving, the full operator surface stays reachable from a tethered
        # machine over the USB gadget, so the "sealed" state would be sealed
        # on the device only. Retract it with the screen.
        webui_was_running = False
        try:
            if self.webui_svc.is_running():
                webui_was_running = True
                self.webui_svc.stop()
                self._refresh_webui_status()
        except Exception:
            pass

        def _on_standby_dismissed(result: bool | None) -> None:
            if not result:
                return
            try:
                self.standby.recover()
            except Exception:
                pass
            if webui_was_running:
                # Deliberately not restarted automatically: re-exposing the
                # interface is an explicit operator decision.
                self.notify(
                    "WebUI was retracted when standby engaged. "
                    "Press w to expose it again.",
                    title="WEBUI",
                    severity="warning",
                )

        self.push_screen(StandbyScreen(), _on_standby_dismissed)


def run_tui(
    initial_screen: str = "home",
    vessel_path: str | None = None,
) -> None:
    app = PhasmidApp(initial_screen=initial_screen, vessel_path=vessel_path)
    app.run()
