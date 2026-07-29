from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Button, Footer, Select, Static

from ...services.access_token_service import (
    ROLE_RECOVER,
    ROLE_STORE,
    AccessTokenGadgetRequired,
    AccessTokenRoleAlreadyIssued,
    access_token_service,
)
from ...services.webui_service import WebUIService
from .base import OperatorScreen

_ROLE_OPTIONS = [
    ("Store (encrypt)", ROLE_STORE),
    ("Recover (decrypt / destroy)", ROLE_RECOVER),
]
_ROLE_LABELS = dict((value, label) for label, value in _ROLE_OPTIONS)


class AccessTokenScreen(OperatorScreen):
    """Issue and revoke the WebUI's two role-scoped access tokens.

    A store-token WebUI session sees the full surface - Face selection,
    normal and restricted passphrase entry - on the assumption that
    encrypting or storing new material only ever happens somewhere safe. A
    recover-token session sees only decrypt/destroy, with the face resolved
    from the passphrase rather than picked from a menu, so an operator
    handed this token has nothing on screen to disclose that a second face
    or a second credential category exists at all.

    Issuing (or reissuing after a revoke) requires a live USB gadget
    connection: this is meant to be granted with the operator's hands
    physically on the device, not reachable over Wi-Fi or from across a
    room.
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
    ]

    DEFAULT_CSS = """
    AccessTokenScreen {
        background: $background;
        padding: 1 4;
    }
    AccessTokenScreen #tokens-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding: 0 0 1 0;
    }
    AccessTokenScreen .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    AccessTokenScreen #status-area {
        color: $text-muted;
        min-height: 2;
        padding: 0 0 1 0;
    }
    AccessTokenScreen #issued-token-area {
        color: $success;
        text-style: bold;
        min-height: 3;
        padding: 1 0;
    }
    AccessTokenScreen #button-row {
        height: auto;
        margin-top: 1;
    }
    AccessTokenScreen #issue-btn, AccessTokenScreen #revoke-btn {
        width: 1fr;
        margin-right: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._webui_svc = WebUIService()

    def compose(self) -> ComposeResult:
        yield self.webui_warning_banner()
        yield Static("ACCESS TOKENS", id="tokens-title")
        yield Static(
            "Issuing or revoking a token requires a live USB gadget connection.",
            id="status-area",
        )
        yield Static("Role", classes="field-label")
        yield Select(
            [(label, value) for label, value in _ROLE_OPTIONS],
            id="role-select",
            value=ROLE_STORE,
        )
        yield Static("", id="issued-token-area")
        yield Button("Issue Token", id="issue-btn", variant="primary")
        yield Button("Revoke Token", id="revoke-btn", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        issued = access_token_service.issued_roles()
        lines = []
        for _label, role in _ROLE_OPTIONS:
            if role in issued:
                lines.append(f"{_ROLE_LABELS[role]}: issued at {issued[role]}")
            else:
                lines.append(f"{_ROLE_LABELS[role]}: not issued")
        self.query_one("#status-area", Static).update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        role = self.query_one("#role-select", Select).value
        if event.button.id == "issue-btn":
            self._issue(str(role))
        elif event.button.id == "revoke-btn":
            self._revoke(str(role))

    def _issue(self, role: str) -> None:
        gadget_ip = self._webui_svc.gadget_ip()
        try:
            token = access_token_service.issue(role, gadget_ip=gadget_ip)
        except AccessTokenGadgetRequired:
            self.app.notify(
                "Connect the USB gadget interface before issuing a token.",
                title="Access Tokens",
                severity="error",
            )
            return
        except AccessTokenRoleAlreadyIssued as exc:
            self.app.notify(str(exc), title="Access Tokens", severity="error")
            return

        self.query_one("#issued-token-area", Static).update(
            f"New {_ROLE_LABELS[role]} token (copy it now - it will not be "
            f"shown again):\n{token}"
        )
        self._refresh_status()

    def _revoke(self, role: str) -> None:
        revoked = access_token_service.revoke(role)
        self.query_one("#issued-token-area", Static).update("")
        if revoked:
            self.app.notify(
                f"{_ROLE_LABELS[role]} token revoked.",
                title="Access Tokens",
                severity="information",
            )
        else:
            self.app.notify(
                f"No {_ROLE_LABELS[role]} token was issued.",
                title="Access Tokens",
                severity="warning",
            )
        self._refresh_status()
