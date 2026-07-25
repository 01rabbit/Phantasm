from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, ListItem, ListView, RichLog, Static

from ...services.guided_service import GuidedService, GuidedWorkflow
from .base import OperatorScreen


class GuidedScreen(OperatorScreen):
    BINDINGS = [
        Binding("escape", "back_or_dismiss", "Back"),
        Binding("q", "dismiss", "Back"),
    ]

    DEFAULT_CSS = """
    GuidedScreen {
        background: $background;
        padding: 1 2;
    }
    GuidedScreen #guided-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        height: 2;
    }
    GuidedScreen #guided-help {
        color: $text-muted;
        text-align: center;
        height: 2;
    }
    GuidedScreen #layout {
        height: 1fr;
        layout: horizontal;
    }
    GuidedScreen #workflow-list-container {
        width: 38;
    }
    GuidedScreen #workflow-list {
        width: 100%;
        border: solid $primary 50%;
        background: $surface;
    }
    GuidedScreen #workflow-detail {
        width: 1fr;
        border: solid $primary 50%;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, start_workflow: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._svc = GuidedService()
        self._workflows = self._svc.get_workflows()
        self._start_workflow = start_workflow
        self._selected_idx = 0

    def compose(self) -> ComposeResult:
        from textual.containers import Container, Horizontal

        yield self.webui_warning_banner()
        yield Static("GUIDED HELP", id="guided-title")
        yield Static(
            "Start with Protect a File or Open a Protected File. Expert walkthroughs are optional.",
            id="guided-help",
        )
        with Horizontal(id="layout"):
            with Container(id="workflow-list-container"):
                yield ListView(
                    *[ListItem(Static(wf.title)) for wf in self._workflows],
                    id="workflow-list",
                    initial_index=self._selected_idx,
                )
            yield RichLog(id="workflow-detail", highlight=False, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        if self._start_workflow:
            for i, wf in enumerate(self._workflows):
                if wf.id == self._start_workflow:
                    self._selected_idx = i
                    break
        self.query_one(ListView).index = self._selected_idx
        self._show_workflow(self._workflows[self._selected_idx])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self._workflows_index(event.item)
        if idx is not None:
            self._selected_idx = idx
            self._show_workflow(self._workflows[idx])

    def _workflows_index(self, item) -> int | None:
        lv = self.query_one(ListView)
        for i, child in enumerate(lv.children):
            if child is item:
                return i
        return None

    def _show_workflow(self, wf: GuidedWorkflow) -> None:
        log = self.query_one(RichLog)
        log.clear()
        log.write(f"[bold $primary]{wf.title}[/]\n")
        log.write(f"[dim]{wf.description}[/]\n")
        log.write("")
        for step in wf.steps:
            log.write(f"[bold]Step {step.number}[/bold]  {step.text}")
            if step.detail:
                log.write(f"    [dim]{step.detail}[/dim]")
            log.write("")

    def action_back_or_dismiss(self) -> None:
        self.dismiss()
