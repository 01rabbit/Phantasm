"""
Context profile selector screen for the TUI Operator Console.

Allows the operator to select a context profile before deployment.
The selected profile guides dummy dataset structure and plausibility validation.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Footer, Label, ListItem, ListView, Static

from ...context_profile import BUILT_IN_PROFILES, list_profiles
from .base import OperatorScreen


class ContextProfileSelectorScreen(OperatorScreen):
    """Select a context profile for dummy dataset guidance."""

    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("enter", "select_profile", "Select", show=False),
    ]

    DEFAULT_CSS = """
    ContextProfileSelectorScreen {
        background: $background;
        padding: 1 4;
    }
    ContextProfileSelectorScreen #title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 0 0 1 0;
    }
    ContextProfileSelectorScreen #subtitle {
        color: $text-muted;
        padding: 0 0 1 0;
        text-align: center;
    }
    ContextProfileSelectorScreen #profile-list {
        height: 12;
        border: solid $primary;
        margin: 0 0 1 0;
    }
    ContextProfileSelectorScreen #detail-panel {
        height: 8;
        border: solid $foreground-muted;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text;
    }
    ContextProfileSelectorScreen #warning-panel {
        color: $warning;
        min-height: 1;
        margin: 0 0 1 0;
    }
    ContextProfileSelectorScreen #select-btn {
        width: 100%;
    }
    """

    def __init__(
        self,
        current_profile: str = "travel",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._current_profile = current_profile
        self._selected_profile: str = current_profile

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("CONTEXT PROFILE SELECTION", id="title")
        yield Static(
            "Select the context profile that matches your operational deployment.",
            id="subtitle",
        )
        items = [
            ListItem(
                Label(f"  {name}  —  {BUILT_IN_PROFILES[name].container_name}"),
                id=f"profile-{name}",
            )
            for name in list_profiles()
        ]
        yield ListView(*items, id="profile-list")
        yield Static("", id="detail-panel", markup=False)
        yield Static("", id="warning-panel", markup=True)
        yield Button("Use Selected Profile", id="select-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._update_detail(self._current_profile)
        lv = self.query_one("#profile-list", ListView)
        names = list_profiles()
        if self._current_profile in names:
            try:
                lv.index = names.index(self._current_profile)
            except Exception:
                pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        item_id = event.item.id or ""
        if item_id.startswith("profile-"):
            name = item_id[len("profile-") :]
            self._selected_profile = name
            self._update_detail(name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-btn":
            self.action_select_profile()

    def action_select_profile(self) -> None:
        self.dismiss(self._selected_profile)

    def _update_detail(self, name: str) -> None:
        profile = BUILT_IN_PROFILES.get(name)
        detail = self.query_one("#detail-panel", Static)
        warn = self.query_one("#warning-panel", Static)
        if profile is None:
            detail.update(f"Profile '{name}' not found.")
            warn.update("")
            return

        min_mb = profile.expected_size_range[0] // (1024 * 1024)
        max_mb = profile.expected_size_range[1] // (1024 * 1024)
        content_types = ", ".join(profile.dummy_content_types)
        dirs = ", ".join(profile.typical_directories)
        text = (
            f"{profile.description}\n\n"
            f"Container: {profile.container_name}\n"
            f"Size range: {min_mb} MiB – {max_mb} MiB\n"
            f"Content types: {content_types}\n"
            f"Directories: {dirs}\n"
            f"Min files: {profile.min_file_count}"
        )
        detail.update(text)

        pwarnings = profile.validate()
        if pwarnings:
            warn.update("[yellow]! " + "  ".join(pwarnings) + "[/yellow]")
        else:
            warn.update("")
