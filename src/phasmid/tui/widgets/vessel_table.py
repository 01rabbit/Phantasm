from __future__ import annotations

from typing import cast

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from ...models.vessel import VesselMeta
from ...services.vessel_service import redact_path


class VesselTable(Widget):
    DEFAULT_CSS = """
    VesselTable {
        height: 1fr;
        border: solid $primary 50%;
        padding: 0 1;
    }
    VesselTable .section-title {
        text-style: bold;
        color: $primary;
        padding: 0 1;
    }
    VesselTable .section-sub {
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
        margin-bottom: 1;
    }
    VesselTable DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
    ]

    def __init__(self, vessels: list[VesselMeta] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._vessels: list[VesselMeta] = vessels or []

    def compose(self) -> ComposeResult:
        yield Label("Vessels", classes="section-title")
        yield Label("Deniable container files", classes="section-sub")
        table: DataTable = DataTable(
            id="vessel-data-table", cursor_type="row", zebra_stripes=True
        )
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "Path", "Posture", "State")
        self._populate_table(table)

    def _populate_table(self, table: DataTable) -> None:
        table.clear()
        if not self._vessels:
            table.add_row("[dim]No vessels registered[/dim]", "", "", key="__empty__")
        else:
            for i, v in enumerate(self._vessels):
                table.add_row(
                    v.name,
                    redact_path(v.path),
                    v.posture.value,
                    "open" if v.is_open else "closed",
                    key=str(i),
                )

    def update_vessels(self, vessels: list[VesselMeta]) -> None:
        self._vessels = vessels
        table = self.query_one(DataTable)
        self._populate_table(table)

    @property
    def selected_vessel(self) -> VesselMeta | None:
        table = self.query_one(DataTable)
        if table.cursor_row < 0 or not self._vessels:
            return None
        try:
            return cast(VesselMeta, self._vessels[table.cursor_row])
        except IndexError:
            return None

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_scroll_up()

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_scroll_down()
