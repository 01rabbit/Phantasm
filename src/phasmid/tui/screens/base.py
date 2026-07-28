from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Static

if TYPE_CHECKING:
    from ..app import PhasmidApp


class OperatorScreen(Screen):
    """Shared operator screen chrome."""

    DEFAULT_CSS = """
    .webui-warning-banner {
        background: $error;
        color: $text;
        text-align: center;
        text-style: bold;
        height: 1;
        dock: top;
        display: none;
    }
    """

    _WEBUI_WARNING_FALLBACK = "WEBUI ACTIVE - PRESS \\[w] TO RETRACT"

    def webui_warning_banner(self) -> Static:
        return Static(
            self._WEBUI_WARNING_FALLBACK,
            id="webui-warning-banner",
            classes="webui-warning-banner",
        )

    def webui_running_message(self) -> str:
        app = cast("PhasmidApp", self.app)
        access_url = app.webui_svc.access_url()
        if access_url:
            return f"WEBUI ACTIVE AT {access_url} - PRESS \\[w] TO RETRACT"
        return self._WEBUI_WARNING_FALLBACK

    def refresh_webui_status(self) -> None:
        try:
            banner = self.query_one("#webui-warning-banner", Static)
        except NoMatches:
            return
        app = cast("PhasmidApp", self.app)
        banner.update(self.webui_running_message())
        banner.display = app.webui_svc.is_running()
