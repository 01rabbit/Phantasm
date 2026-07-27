from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, ListItem, ListView, RichLog, Static

from ...services.guided_service import GuidedService, GuidedStep, GuidedWorkflow
from .base import OperatorScreen


def _quick_start_workflows() -> list[GuidedWorkflow]:
    return [
        GuidedWorkflow(
            id="quick_protect",
            title="Protect a File",
            description="Normal-use steps for protecting content without needing expert terminology.",
            steps=[
                GuidedStep(1, "Create or select protected storage."),
                GuidedStep(2, "Choose the file you need to protect."),
                GuidedStep(3, "Set the access password."),
                GuidedStep(4, "Present and bind the physical access object."),
                GuidedStep(
                    5, "Confirm the result and close the storage when finished."
                ),
            ],
        ),
        GuidedWorkflow(
            id="quick_open",
            title="Open a Protected File",
            description="Normal-use steps for opening content that was protected earlier.",
            steps=[
                GuidedStep(1, "Select the protected storage you need."),
                GuidedStep(
                    2, "Present the physical access object and wait for a stable match."
                ),
                GuidedStep(3, "Enter the access password."),
                GuidedStep(4, "Retrieve only the file you need."),
                GuidedStep(5, "Close the storage when finished."),
            ],
        ),
    ]


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
        expert = self._svc.get_workflows()
        for workflow in expert:
            workflow.title = f"Expert: {workflow.title}"
        self._workflows = _quick_start_workflows() + expert
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
