from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ...models.vessel import VesselMeta
from ...services.inspection_service import InspectionService


class VesselSummaryPanel(Widget):
    DEFAULT_CSS = """
    VesselSummaryPanel {
        height: 1fr;
        border: solid $primary 50%;
        padding: 1 2;
    }
    VesselSummaryPanel .panel-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    VesselSummaryPanel .field-row {
        color: $text;
    }
    VesselSummaryPanel .field-label {
        color: $text-muted;
        width: 14;
    }
    VesselSummaryPanel .empty-msg {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, vessel: VesselMeta | None = None, **kwargs):
        super().__init__(**kwargs)
        self._vessel = vessel
        self._entropy_cache_key: tuple[str, int, int] | None = None
        self._entropy_cache_value = ""

    def compose(self) -> ComposeResult:
        yield Static("VESSEL STATUS", classes="panel-title")
        if self._vessel is None:
            yield Static("No vessel selected.", classes="empty-msg")
        else:
            v = self._vessel
            for label, value in [
                ("Name", v.name),
                ("Size", v.size_human),
                ("Header", v.header_status),
                ("Magic Bytes", v.magic_bytes_status),
                ("Faces", str(v.face_count) if v.face_count else "unknown"),
                ("Posture", v.posture.value),
            ]:
                yield Static(
                    f"[dim]{label:<14}[/dim]{value}", classes="field-row", markup=True
                )

    def update_vessel(self, vessel: VesselMeta | None) -> None:
        if self._vessel is None or vessel is None or self._vessel.path != vessel.path:
            self._entropy_cache_key = None
            self._entropy_cache_value = ""
        self._vessel = vessel
        self.remove_children()
        for widget in self._build_children():
            self.mount(widget)

    def _build_children(self):
        from textual.widgets import Static as S

        yield S("VESSEL STATUS", classes="panel-title")
        if self._vessel is None:
            yield S("No vessel selected.", classes="empty-msg")
        else:
            v = self._vessel
            rows = [
                ("Name", v.name),
                ("Size", v.size_human),
                ("Header", v.header_status),
                ("Magic Bytes", v.magic_bytes_status),
                ("Faces", str(v.face_count) if v.face_count else "unknown"),
                ("Posture", v.posture.value),
            ]

            # WebUI Status
            webui_svc = getattr(self.app, "webui_svc", None)
            if webui_svc:
                if webui_svc.is_running():
                    uptime = int(webui_svc.uptime_seconds)
                    m, s = divmod(uptime, 60)
                    status_text = (
                        f"[bold red]ACTIVE[/bold red] [dim]({m:02d}:{s:02d})[/dim]"
                    )
                else:
                    status_text = "[green]OFFLINE[/green]"
                rows.append(("WebUI Exposure", status_text))

            entropy_val = self._get_entropy(v)
            if entropy_val:
                rows.append(("Entropy", entropy_val))
            for label, value in rows:
                yield S(
                    f"[dim]{label:<14}[/dim]{value}", classes="field-row", markup=True
                )

    def _get_entropy(self, vessel: VesselMeta) -> str:
        try:
            stat = vessel.path.stat()
            cache_key = (str(vessel.path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            cache_key = None
        if cache_key is not None and cache_key == self._entropy_cache_key:
            return self._entropy_cache_value

        entropy_value = ""
        try:
            result = InspectionService().inspect(vessel.path)
            if result.ok:
                for field in result.fields:
                    if field.label == "Entropy":
                        note = f"  [dim]({field.note})[/dim]" if field.note else ""
                        entropy_value = f"{field.value}{note}"
                        break
        except Exception:
            pass
        if cache_key is not None:
            self._entropy_cache_key = cache_key
            self._entropy_cache_value = entropy_value
        return entropy_value
