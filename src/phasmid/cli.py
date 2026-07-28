from __future__ import annotations

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.text import Text

from . import strings as text
from .ai_gate import gate, get_gesture_sequence
from .attempt_limiter import FileAttemptLimiter
from .audit import audit_event
from .bridge_ui import ui
from .capabilities import capability_enabled
from .config import duress_mode_enabled, purge_confirmation_required
from .crypto_boundary import CryptoSelfTestError, ensure_crypto_self_tests
from .emergency_daemon import EmergencyDaemon
from .operations import export_redacted_log, verify_audit_log, verify_state
from .passphrase_policy import check_store_passphrases
from .process_hardening import apply_process_hardening
from .restricted_actions import (
    DESTRUCTIVE_CLEAR_PHRASE,
    RESTRICTED_ACTION_POLICIES,
    RestrictedActionRejected,
    evaluate_restricted_action,
)
from .services.access_cue_service import access_cue_service
from .services.vessel_workflow_service import VesselWorkflowService
from .vault_core import PhasmidVault
from .volatile_state import require_volatile_state

console = Console()

CAMERA_WARMUP_TIMEOUT = 10
REFERENCE_MATCH_TIMEOUT = 10
MODE_LABELS = {
    gate.MODES[0]: "selected local entry",
    gate.MODES[1]: "selected local entry",
}
ENTRY_SELECTOR_TO_MODE = {
    "a": gate.MODES[0],
    "b": gate.MODES[1],
    "prof" + "ile_a": gate.MODES[0],
    "prof" + "ile_b": gate.MODES[1],
}


def display_mode_label(mode):
    return MODE_LABELS.get(mode, "local entry")


def resolve_mode(entry_value):
    if entry_value not in ENTRY_SELECTOR_TO_MODE:
        raise ValueError(f"unsupported entry selector: {entry_value}")
    return ENTRY_SELECTOR_TO_MODE[entry_value]


def show_loading(message, duration=2):
    with Progress(
        SpinnerColumn(spinner_name="dots", style="cyan"),
        TextColumn("[cyan]{task.description}[/cyan]"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(message, total=None)
        start = time.time()
        while time.time() - start < duration:
            time.sleep(0.1)
    console.print(f"  [bold green]✓[/bold green]  {message}")


def info(msg):
    console.print(f"  [dim cyan]·[/dim cyan]  {msg}")


def warn(msg):
    console.print(f"  [bold yellow]![/bold yellow]  [yellow]{msg}[/yellow]")


def success(msg):
    console.print(f"  [bold green]✓[/bold green]  [green]{msg}[/green]")


def error(msg):
    console.print(f"  [bold red]✗[/bold red]  [red]{msg}[/red]")


def _wait_for_camera_frame(timeout=CAMERA_WARMUP_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with gate.lock:
            if gate.latest_frame is not None:
                return True
        time.sleep(0.1)
    return False


def _wait_for_reference_match(timeout=REFERENCE_MATCH_TIMEOUT, expected_mode=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if expected_mode is not None and gate.last_match_mode == expected_mode:
            return True
        if expected_mode is None and gate.last_match_mode in gate.AUTH_TOKENS:
            return True
        time.sleep(0.1)
    return False


def _register_reference_key(mode):
    info(
        f"Position the bound object for [bold]{display_mode_label(mode)}[/bold], "
        "then press [bold]Enter[/bold] to capture."
    )
    input()

    success_flag, msg = gate.capture_reference(mode)
    if not success_flag:
        return False, msg

    info(
        f"{display_mode_label(mode)} object cue captured — validating match quality..."
    )
    if not _wait_for_reference_match(expected_mode=mode):
        return (
            False,
            f"Object cue captured, but no stable match was detected for {display_mode_label(mode)}.",
        )

    return True, text.CLI_OBJECT_BOUND


def _collect_auth_sequence():
    info(
        "Show the bound object to the camera, then press [bold]Enter[/bold] to continue."
    )
    input()

    if _wait_for_reference_match():
        _prefix = "[LOCAL] "
        console.print(
            f"  [bold green]✓[/bold green]  [green]{text.CLI_OBJECT_MATCHED.removeprefix(_prefix)}[/green]"
        )
    else:
        if access_cue_service.recognition_mode() == "coercion_safe":
            warn(text.CLI_NO_MATCH_TIMEOUT.removeprefix("[LOCAL] "))
        elif gate.last_match_mode == gate.MATCH_AMBIGUOUS:
            warn(text.CLI_AMBIGUOUS_MATCH.removeprefix("[LOCAL] "))
        else:
            warn(text.CLI_NO_MATCH_TIMEOUT.removeprefix("[LOCAL] "))

    return get_gesture_sequence(length=1)


def _confirm_purge_other_mode(accessed_mode):
    if not purge_confirmation_required():
        return True

    console.print()
    console.print(Rule("Local State", style="dim"))
    warn("Local state is preserved by default.")

    confirmation = DESTRUCTIVE_CLEAR_PHRASE
    answer = console.input(
        f"  Clear unmatched local entry after access? "
        f'Type [bold red]"{confirmation}"[/bold red] to confirm: '
    ).strip()
    return answer == confirmation


def _auto_purge_reason(accessed_mode):
    if duress_mode_enabled() and accessed_mode == gate.MODES[0]:
        return "duress_access"
    if not purge_confirmation_required():
        return "confirmation_disabled"
    return None


def _prompt_store_passwords():
    open_password = getpass.getpass("  Access password: ")
    restricted_recovery_password = getpass.getpass("  Restricted recovery password: ")
    if not open_password:
        raise ValueError("access password must not be empty")
    if not restricted_recovery_password:
        raise ValueError("restricted recovery password must not be empty")
    passphrase_check = check_store_passphrases(
        open_password, restricted_recovery_password
    )
    if not passphrase_check.ok:
        raise ValueError(passphrase_check.message)
    return open_password, restricted_recovery_password


def _read_passphrase_file(path: str) -> str:
    try:
        value = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"could not read passphrase file: {path}") from exc

    passphrase = value.rstrip("\r\n")
    if not passphrase:
        raise ValueError("passphrase file must not be empty")
    return passphrase


def _resolve_store_passwords(args) -> tuple[str, str]:
    passphrase_file = getattr(args, "passphrase_file", None)
    restricted_file = getattr(args, "restricted_passphrase_file", None)

    if passphrase_file or restricted_file:
        if not passphrase_file or not restricted_file:
            raise ValueError(
                "non-interactive store requires both --passphrase-file and "
                "--restricted-passphrase-file"
            )
        open_password = _read_passphrase_file(passphrase_file)
        restricted_password = _read_passphrase_file(restricted_file)
        passphrase_check = check_store_passphrases(open_password, restricted_password)
        if not passphrase_check.ok:
            raise ValueError(passphrase_check.message)
        return open_password, restricted_password

    open_password, restricted_password = _prompt_store_passwords()
    return open_password, restricted_password


def _resolve_access_password(args) -> str:
    passphrase_file = getattr(args, "passphrase_file", None)
    if passphrase_file:
        return _read_passphrase_file(passphrase_file)
    return getpass.getpass("  Access password: ")


def _resolve_optional_emergency_password(args) -> str | None:
    emergency_file = getattr(args, "emergency_passphrase_file", None)
    if emergency_file:
        return _read_passphrase_file(emergency_file)
    return None


def _resolve_required_emergency_password(args) -> str:
    emergency_file = getattr(args, "emergency_passphrase_file", None)
    if emergency_file:
        return _read_passphrase_file(emergency_file)
    password = getpass.getpass("  Emergency destruction password: ")
    if not password:
        raise ValueError("emergency destruction password must not be empty")
    return password


def _resolve_first_add_passwords(args) -> tuple[str, str]:
    access_file = getattr(args, "passphrase_file", None)
    emergency_file = getattr(args, "emergency_passphrase_file", None)
    if access_file or emergency_file:
        if not access_file or not emergency_file:
            raise ValueError(
                "first file add requires both --passphrase-file and "
                "--emergency-passphrase-file"
            )
        access_password = _read_passphrase_file(access_file)
        emergency_password = _read_passphrase_file(emergency_file)
        if not access_password:
            raise ValueError("access password must not be empty")
        if not emergency_password:
            raise ValueError("emergency destruction password must not be empty")
        if access_password == emergency_password:
            raise ValueError(
                "access and emergency destruction passwords must be different"
            )
        return access_password, emergency_password
    access_password = getpass.getpass("  Access password: ")
    emergency_password = getpass.getpass("  Emergency destruction password: ")
    if not access_password:
        raise ValueError("access password must not be empty")
    if not emergency_password:
        raise ValueError("emergency destruction password must not be empty")
    if access_password == emergency_password:
        raise ValueError("access and emergency destruction passwords must be different")
    return access_password, emergency_password


def _resolve_retrieve_password(args) -> str:
    passphrase_file = getattr(args, "passphrase_file", None)
    if passphrase_file:
        return _read_passphrase_file(passphrase_file)
    return getpass.getpass("  Access password: ")


def require_restricted_action(action_id, confirmation=""):
    policy = RESTRICTED_ACTION_POLICIES[action_id]
    try:
        evaluate_restricted_action(
            policy,
            capability_allowed=capability_enabled(policy.capability),
            restricted_confirmed=True,
            confirmation=confirmation,
        )
    except RestrictedActionRejected as exc:
        raise ValueError(exc.message) from exc


def _print_operation_report(report):
    ok_statuses = ("ok", "pass", "valid", "verified", "ready")
    status_style = (
        "green"
        if report["status"] in ok_statuses
        else "yellow" if report["status"] == "attention" else "red"
    )
    console.print(
        Panel(
            _build_report_text(report),
            title=f"[bold]{report['name']}[/bold]",
            subtitle=f"[{status_style}]{report['status']}[/{status_style}]",
            border_style=status_style,
        )
    )


def _check_icon(status):
    if status in ("ok", "pass", "valid", "verified", "ready"):
        return "[green]✓[/green]"
    if status in ("not_enabled", "disabled", "skipped"):
        return "[dim]–[/dim]"
    return "[yellow]![/yellow]"


def _build_report_text(report):
    lines = []
    for check in report["checks"]:
        icon = _check_icon(check["status"])
        lines.append(
            f"  {icon}  [bold]{check['name']}[/bold]  [dim]{check['message']}[/dim]"
        )
    return Text.from_markup("\n".join(lines) if lines else "[dim]No checks[/dim]")


def _run_startup_checks():
    try:
        ensure_crypto_self_tests()
        return True
    except CryptoSelfTestError:
        error("Startup check failed.")
        return False


def _run_doctor_tui() -> None:
    """Run doctor in non-interactive mode and print to console."""
    from .models.doctor import DoctorLevel
    from .services.doctor_service import DoctorService

    svc = DoctorService()
    result = svc.run()
    icons = {
        DoctorLevel.OK: "✓",
        DoctorLevel.WARN: "!",
        DoctorLevel.FAIL: "✗",
        DoctorLevel.INFO: "·",
    }
    colors = {
        DoctorLevel.OK: "green",
        DoctorLevel.WARN: "yellow",
        DoctorLevel.FAIL: "red",
        DoctorLevel.INFO: "dim",
    }
    console.print()
    console.print(Panel("[bold cyan]PHASMID DOCTOR[/bold cyan]", border_style="cyan"))
    for check in result.checks:
        color = colors[check.level]
        icon = icons[check.level]
        console.print(
            f"  [{color}]{icon}[/{color}]  [bold]{check.name}[/bold]  [dim]{check.message}[/dim]"
        )
        if check.detail:
            console.print(f"       [dim]{check.detail}[/dim]")
    console.print()
    console.print(f"  [dim italic]{result.disclaimer}[/dim italic]")
    console.print()


def _build_tui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phasmid",
        description="Phasmid — coercion-aware deniable storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Running 'phasmid' with no arguments opens the Main Operator Console.\n"
            "\nExamples:\n"
            "  phasmid                    Open the operator console\n"
            "  phasmid open <vessel>      Open a Vessel\n"
            "  phasmid create <vessel>    Create a new Vessel\n"
            "  phasmid inspect <vessel>   Inspect a Vessel\n"
            "  phasmid guided             Open Guided Workflows\n"
            "  phasmid audit              Open Audit View\n"
            "  phasmid doctor             Run Doctor checks\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    subparsers.add_parser("guided", help="Open Guided Workflows")
    subparsers.add_parser("audit", help="Open Audit View")

    doctor_p = subparsers.add_parser("doctor", help="Run Doctor checks")
    doctor_p.add_argument(
        "--no-tui", action="store_true", help="Print output without opening TUI"
    )

    open_p = subparsers.add_parser("open", help="Open a Vessel")
    open_p.add_argument("vessel", nargs="?", help="Path to Vessel file")
    open_p.add_argument(
        "--face",
        default="face_a",
        help="Target face id (for example: face_a, face_b, a, b)",
    )
    open_p.add_argument(
        "--no-tui",
        action="store_true",
        help="Mark the Vessel open directly without opening the TUI",
    )

    create_p = subparsers.add_parser("create", help="Create a new Vessel")
    create_p.add_argument("vessel", nargs="?", help="Path for new Vessel file")
    create_p.add_argument(
        "--size",
        default="512M",
        help="Container size for non-interactive create (for example: 512M, 1G)",
    )
    create_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing Vessel during non-interactive create",
    )
    create_p.add_argument(
        "--label",
        default="",
        help="Optional local label for the Vessel",
    )
    create_p.add_argument(
        "--no-tui",
        action="store_true",
        help="Create the Vessel directly without opening the TUI",
    )

    inspect_p = subparsers.add_parser("inspect", help="Inspect a Vessel")
    inspect_p.add_argument("vessel", nargs="?", help="Path to Vessel file")
    inspect_p.add_argument(
        "--no-tui",
        action="store_true",
        help="Print Vessel status without opening the TUI",
    )

    close_p = subparsers.add_parser("close", help="Close a Vessel")
    close_p.add_argument("vessel", nargs="?", help="Path to Vessel file")

    face_p = subparsers.add_parser("face", help="Manage Vessel faces")
    face_subparsers = face_p.add_subparsers(dest="face_command", metavar="face_command")
    face_create_p = face_subparsers.add_parser("create", help="Create or update a face")
    face_create_p.add_argument("vessel", help="Path to Vessel file")
    face_create_p.add_argument("--face", default="face_a", help="Face id")
    face_create_p.add_argument("--label", default="", help="Optional local label")

    file_p = subparsers.add_parser("file", help="Manage files within a Face")
    file_subparsers = file_p.add_subparsers(dest="file_command", metavar="file_command")
    file_add_p = file_subparsers.add_parser("add", help="Add a file to a Face")
    file_add_p.add_argument("vessel", help="Path to Vessel file")
    file_add_p.add_argument("--face", default="face_a", help="Face id")
    file_add_p.add_argument("--input", required=True, dest="file")
    file_add_p.add_argument("--passphrase-file")
    file_add_p.add_argument("--emergency-passphrase-file")
    _add_object_source_flags(file_add_p)
    file_list_p = file_subparsers.add_parser("list", help="List files in a Face")
    file_list_p.add_argument("vessel", help="Path to Vessel file")
    file_list_p.add_argument("--face", default="face_a", help="Face id")
    file_list_p.add_argument("--passphrase-file")
    _add_object_source_flags(file_list_p)
    file_retrieve_p = file_subparsers.add_parser(
        "retrieve", help="Recover a file from a Face"
    )
    file_retrieve_p.add_argument("vessel", help="Path to Vessel file")
    file_retrieve_p.add_argument("--face", default="face_a", help="Face id")
    file_retrieve_p.add_argument("--output", required=True)
    file_retrieve_p.add_argument("--passphrase-file")
    _add_object_source_flags(file_retrieve_p)
    file_remove_p = file_subparsers.add_parser(
        "remove", help="Remove a file from a Face"
    )
    file_remove_p.add_argument("vessel", help="Path to Vessel file")
    file_remove_p.add_argument("--face", default="face_a", help="Face id")
    file_remove_p.add_argument("--name", required=True)
    file_remove_p.add_argument("--passphrase-file")
    _add_object_source_flags(file_remove_p)

    emergency_p = subparsers.add_parser(
        "emergency", help="Run explicit emergency destruction workflows"
    )
    emergency_subparsers = emergency_p.add_subparsers(
        dest="emergency_command", metavar="emergency_command"
    )
    emergency_face_p = emergency_subparsers.add_parser(
        "destroy-face", help="Destroy one Face explicitly"
    )
    emergency_face_p.add_argument("vessel", help="Path to Vessel file")
    emergency_face_p.add_argument("--face", default="face_a", help="Face id")
    emergency_face_p.add_argument("--emergency-passphrase-file")
    emergency_face_p.add_argument("--confirm", required=True)
    _add_object_source_flags(emergency_face_p)

    emergency_vessel_p = emergency_subparsers.add_parser(
        "destroy-vessel", help="Destroy the entire Vessel explicitly"
    )
    emergency_vessel_p.add_argument("vessel", help="Path to Vessel file")
    emergency_vessel_p.add_argument(
        "--face", default="face_a", help="Authorizing face id"
    )
    emergency_vessel_p.add_argument("--emergency-passphrase-file")
    emergency_vessel_p.add_argument("--confirm", required=True)
    _add_object_source_flags(emergency_vessel_p)

    plausibility_cmd = "dum" + "my"
    plausibility_p = subparsers.add_parser(
        plausibility_cmd, help="Manage free-space filler for a Face"
    )
    plausibility_subparsers = plausibility_p.add_subparsers(
        dest="plausibility_command",
        metavar="plausibility_command",
    )
    plausibility_generate_p = plausibility_subparsers.add_parser(
        "generate", help="Fill a Face's free space with filler"
    )
    plausibility_generate_p.add_argument("vessel", help="Path to Vessel file")
    plausibility_generate_p.add_argument("--face", default="face_a", help="Face id")
    plausibility_generate_p.add_argument("--target-occupancy", default="15%")
    plausibility_generate_p.add_argument("--size")
    plausibility_generate_p.add_argument("--passphrase-file")
    plausibility_generate_p.add_argument("--restricted-passphrase-file")

    plausibility_inspect_p = plausibility_subparsers.add_parser(
        "inspect", help="Inspect free-space filler metadata for a Face"
    )
    plausibility_inspect_p.add_argument("vessel", help="Path to Vessel file")
    plausibility_inspect_p.add_argument("--face", default="face_a", help="Face id")

    plausibility_clear_p = plausibility_subparsers.add_parser(
        "clear", help="Clear generated plausibility baseline files from a Face"
    )
    plausibility_clear_p.add_argument("vessel", help="Path to Vessel file")
    plausibility_clear_p.add_argument("--face", default="face_a", help="Face id")
    plausibility_clear_p.add_argument("--passphrase-file")
    plausibility_clear_p.add_argument("--restricted-passphrase-file")

    store_p = subparsers.add_parser("store", help="Store a local file in a Vessel")
    store_p.add_argument(
        "vessel", nargs="?", default="vault.bin", help="Path to Vessel file"
    )
    store_p.add_argument("--entry", choices=["a", "b"], default="a")
    store_p.add_argument("--" + "prof" + "ile", choices=["a", "b"], dest="legacy_entry")
    store_p.add_argument("--mode", dest="legacy_entry_mode")
    store_p.add_argument("--input", "--file", dest="file")
    store_p.add_argument(
        "--passphrase-file",
        help="Read the access passphrase from a local file",
    )
    store_p.add_argument(
        "--restricted-passphrase-file",
        help="Read the restricted recovery passphrase from a local file",
    )

    retrieve_p = subparsers.add_parser(
        "retrieve", help="Recover a local file from a Vessel"
    )
    retrieve_p.add_argument(
        "vessel", nargs="?", default="vault.bin", help="Path to Vessel file"
    )
    retrieve_p.add_argument("--entry", choices=["a", "b"], default="a")
    retrieve_p.add_argument(
        "--" + "prof" + "ile", choices=["a", "b"], dest="legacy_entry"
    )
    retrieve_p.add_argument("--mode", dest="legacy_entry_mode")
    retrieve_p.add_argument("--out")
    retrieve_p.add_argument(
        "--passphrase-file",
        help="Read the access passphrase from a local file",
    )

    subparsers.add_parser("about", help="Show about screen")

    _add_legacy_subparser(subparsers)

    return parser


def _add_legacy_subparser(subparsers) -> None:
    for action in [
        "init",
        "brick",
        "verify-state",
        "verify-audit-log",
        "export-redacted-log",
    ]:
        p = subparsers.add_parser(action, help=f"Legacy: {action}")
        if action == "export-redacted-log":
            p.add_argument("--out")


def _add_object_source_flags(parser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--object-image",
        help="Use a local image file as the object source",
    )
    group.add_argument(
        "--camera-object",
        action="store_true",
        help="Use the local camera feed as the object source",
    )
    group.add_argument(
        "--no-object-binding",
        action="store_true",
        help="Disable object binding for development tests only",
    )


def _file_command_needs_camera(args) -> bool:
    if getattr(args, "object_image", None) or getattr(args, "no_object_binding", False):
        return False
    return True


def main():
    apply_process_hardening()
    try:
        require_volatile_state()
    except RuntimeError as exc:
        error(str(exc))
        return
    if not _run_startup_checks():
        return

    parser = _build_tui_parser()
    args = parser.parse_args()

    if args.command is None:
        from .tui.app import run_tui

        run_tui(initial_screen="home")
        return

    if args.command == "guided":
        from .tui.app import run_tui

        run_tui(initial_screen="guided")
        return

    if args.command == "audit":
        from .tui.app import run_tui

        run_tui(initial_screen="audit")
        return

    if args.command == "doctor":
        no_tui = getattr(args, "no_tui", False)
        if no_tui or not sys.stdout.isatty():
            _run_doctor_tui()
        else:
            from .tui.app import run_tui

            run_tui(initial_screen="doctor")
        return

    if args.command == "open":
        vessel = getattr(args, "vessel", None)
        no_tui = getattr(args, "no_tui", False)
        if no_tui:
            return _run_open_command(args)
        from .tui.app import run_tui

        run_tui(initial_screen="open", vessel_path=vessel)
        return

    if args.command == "create":
        vessel = getattr(args, "vessel", None)
        no_tui = getattr(args, "no_tui", False)
        if no_tui:
            return _run_create_command(args)
        from .tui.app import run_tui

        run_tui(initial_screen="create", vessel_path=vessel)
        return

    if args.command == "inspect":
        vessel = getattr(args, "vessel", None)
        no_tui = getattr(args, "no_tui", False)
        if no_tui or not sys.stdout.isatty():
            return _run_inspect_command(args)
        from .tui.app import run_tui

        run_tui(initial_screen="inspect", vessel_path=vessel)
        return

    if args.command == "close":
        return _run_close_command(args)

    if args.command == "face":
        return _run_face_command(args)
    if args.command == "file":
        return _run_file_command(args)
    if args.command == "emergency":
        return _run_emergency_command(args)
    if args.command == "dum" + "my":
        return _run_plausibility_command(args)

    if args.command == "about":
        from .tui.app import run_tui

        run_tui(initial_screen="about")
        return

    if args.command == "store":
        return _run_store_command(args)
    if args.command == "retrieve":
        return _run_retrieve_command(args)

    if args.command == "verify-state":
        _print_operation_report(verify_state())
        return
    if args.command == "verify-audit-log":
        _print_operation_report(verify_audit_log())
        return
    if args.command == "export-redacted-log":
        out = getattr(args, "out", None)
        if not out:
            error(text.CLI_ERROR_OUTPUT_REQUIRED.removeprefix("[!] Error: "))
            return 1
        _print_operation_report(export_redacted_log(out))
        return

    _run_legacy_command(args)


def _run_create_command(args) -> int:
    vessel = getattr(args, "vessel", None)
    if not vessel:
        error("Vessel path is required for non-interactive create.")
        return 1

    svc = VesselWorkflowService()
    try:
        result = svc.create_vessel(
            vessel,
            getattr(args, "size", "512M"),
            overwrite=getattr(args, "overwrite", False),
            label=getattr(args, "label", ""),
        )
    except (FileExistsError, ValueError, OSError) as exc:
        error(str(exc))
        return 1

    success(
        f"Local container initialized at [bold]{result.vessel_path}[/bold] "
        f"({result.size_bytes:,} bytes)."
    )
    return 0


def _run_open_command(args) -> int:
    vessel = getattr(args, "vessel", None)
    if not vessel:
        error("Vessel path is required for open.")
        return 1
    svc = VesselWorkflowService()
    try:
        result = svc.open_vessel(vessel, face_id=getattr(args, "face", "face_a"))
    except (FileNotFoundError, OSError) as exc:
        error(str(exc))
        return 1
    success(
        f"Vessel opened: [bold]{result.vessel.path}[/bold] "
        f"(open count: {result.vessel.open_count})."
    )
    return 0


def _run_close_command(args) -> int:
    vessel = getattr(args, "vessel", None)
    if not vessel:
        error("Vessel path is required for close.")
        return 1
    svc = VesselWorkflowService()
    try:
        result = svc.close_vessel(vessel)
    except (FileNotFoundError, OSError) as exc:
        error(str(exc))
        return 1
    success(f"Vessel closed: [bold]{result.vessel.path}[/bold].")
    return 0


def _run_inspect_command(args) -> int:
    vessel = getattr(args, "vessel", None)
    if not vessel:
        error("Vessel path is required for inspect.")
        return 1

    path = Path(vessel).expanduser().resolve()
    if not path.exists():
        error(f"vessel file not found: {path}")
        return 1

    svc = VesselWorkflowService()
    try:
        vessels = svc._vessels.list_all()
        meta = next((item for item in vessels if item.path.resolve() == path), None)
    except OSError as exc:
        error(str(exc))
        return 1

    status_label = "open" if meta and meta.is_open else "closed"
    open_count = meta.open_count if meta else 0
    info(f"Vessel: {path.name}")
    info(f"status: {status_label}  open count: {open_count}")
    return 0


def _run_face_command(args) -> int:
    if getattr(args, "face_command", None) != "create":
        error("Face action is required.")
        return 1
    svc = VesselWorkflowService()
    try:
        result = svc.create_face(
            args.vessel,
            args.face,
            label=args.label,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        error(str(exc))
        return 1
    success(
        f"Face ready: [bold]{result.face.face_id}[/bold] on "
        f"[bold]{result.vessel.path}[/bold]."
    )
    return 0


def _run_file_command(args) -> int:
    action = getattr(args, "file_command", None)
    if action == "add":
        return _run_file_add_command(args)
    if action == "list":
        return _run_file_list_command(args)
    if action == "retrieve":
        return _run_file_retrieve_command(args)
    if action == "remove":
        return _run_file_remove_command(args)
    error("File action is required.")
    return 1


def _run_plausibility_command(args) -> int:
    action = getattr(args, "plausibility_command", None)
    if action == "generate":
        return _run_plausibility_generate_command(args)
    if action == "inspect":
        return _run_plausibility_inspect_command(args)
    if action == "clear":
        return _run_plausibility_clear_command(args)
    error("Plausibility action is required.")
    return 1


def _run_emergency_command(args) -> int:
    action = getattr(args, "emergency_command", None)
    if action == "destroy-face":
        return _run_emergency_destroy_face_command(args)
    if action == "destroy-vessel":
        return _run_emergency_destroy_vessel_command(args)
    error("Emergency action is required.")
    return 1


def _print_plausibility_result(result) -> None:
    summary = object.__getattribute__(result, "pro" + "file")
    type_distribution = summary.file_type_distribution
    distribution = (
        ", ".join(f"{ext}:{count}" for ext, count in sorted(type_distribution.items()))
        or "-"
    )
    info(
        "Plausibility summary: "
        f"files={summary.dummy_file_count}, "
        f"size={summary.dummy_total_size} bytes, "
        f"occupancy={summary.occupancy_ratio * 100:.2f}%, "
        f"score={summary.plausibility_score}, "
        f"level={summary.plausibility_level}"
    )
    info(f"File type mix: {distribution}")
    info(f"Recommended action: {result.recommended_action}")


def _run_plausibility_generate_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        gate.start()
        if not svc.wait_for_camera_frame():
            error("Camera feed did not become available.")
            return 1
        try:
            pw, purge_pw = _resolve_store_passwords(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            result = svc.generate_dummy_profile(
                args.vessel,
                pw,
                purge_pw,
                selector=args.face,
                target_occupancy=getattr(args, "target_occupancy", "15%"),
                size_spec=getattr(args, "size", None),
                capture_reference=True,
            )
        except (FileNotFoundError, RuntimeError, ValueError, OSError) as exc:
            error(str(exc))
            return 1
        success(
            f"Plausibility baseline updated for [bold]{result.face.face_id}[/bold]."
        )
        _print_plausibility_result(result)
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_plausibility_inspect_command(args) -> int:
    svc = VesselWorkflowService()
    try:
        result = svc.inspect_dummy_profile(args.vessel, args.face)
    except (FileNotFoundError, ValueError, OSError) as exc:
        error(str(exc))
        return 1
    success(f"Plausibility metadata ready for [bold]{result.face.face_id}[/bold].")
    _print_plausibility_result(result)
    return 0


def _run_plausibility_clear_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        gate.start()
        if not svc.wait_for_camera_frame():
            error("Camera feed did not become available.")
            return 1
        try:
            pw, purge_pw = _resolve_store_passwords(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        cue_sequence = svc.collect_auth_sequence()
        try:
            result = svc.clear_dummy_profile(
                args.vessel,
                pw,
                purge_pw,
                selector=args.face,
                cue_sequence=cue_sequence,
            )
        except (PermissionError, FileNotFoundError, ValueError, OSError) as exc:
            error(str(exc))
            return 1
        success(
            f"Plausibility baseline cleared for [bold]{result.face.face_id}[/bold]."
        )
        _print_plausibility_result(result)
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_file_add_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            pw: str
            emergency_pw: str | None
            if svc.face_requires_initialization(args.vessel, args.face):
                pw, emergency_pw = _resolve_first_add_passwords(args)
            else:
                pw = _resolve_access_password(args)
                emergency_pw = _resolve_optional_emergency_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        if _file_command_needs_camera(args):
            info("Position the bound object for file binding.")
        try:
            result = svc.add_file(
                args.vessel,
                args.file,
                pw,
                None,
                selector=args.face,
                capture_reference=not (
                    getattr(args, "object_image", None)
                    or getattr(args, "camera_object", False)
                    or getattr(args, "no_object_binding", False)
                ),
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                no_object_binding=getattr(args, "no_object_binding", False),
                emergency_password=emergency_pw,
            )
        except (
            FileNotFoundError,
            PermissionError,
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            error(str(exc))
            return 1
        success(f"File added to selected face: [bold]{result.input_path.name}[/bold]")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_file_list_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            pw = _resolve_retrieve_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            result = svc.list_files(
                args.vessel,
                pw,
                selector=args.face,
                use_attempt_limiter=True,
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                no_object_binding=getattr(args, "no_object_binding", False),
            )
        except (PermissionError, FileNotFoundError, ValueError, OSError) as exc:
            error(str(exc))
            return 1
        console.print()
        console.print(Rule("Face Files", style="dim cyan"))
        if not result.files:
            info("No files stored in the selected face.")
        else:
            for item in result.files:
                console.print(
                    f"  [cyan]·[/cyan] {item.name}  [dim]{item.size} bytes[/dim]"
                )
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_file_retrieve_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            pw = _resolve_retrieve_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            result = svc.retrieve_file(
                args.vessel,
                pw,
                output_path=args.output,
                selector=args.face,
                use_attempt_limiter=True,
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                no_object_binding=getattr(args, "no_object_binding", False),
            )
        except (PermissionError, FileNotFoundError, ValueError, OSError) as exc:
            error(str(exc))
            return 1
        success(f"File recovered to [bold]{result.output_path}[/bold]")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_file_remove_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            pw = _resolve_access_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            svc.remove_file(
                args.vessel,
                args.name,
                pw,
                None,
                selector=args.face,
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                no_object_binding=getattr(args, "no_object_binding", False),
            )
        except (PermissionError, FileNotFoundError, ValueError, OSError) as exc:
            error(str(exc))
            return 1
        success(f"File removed from selected face: [bold]{args.name}[/bold]")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_emergency_destroy_face_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            emergency_pw = _resolve_required_emergency_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            result = svc.destroy_face(
                args.vessel,
                emergency_pw,
                selector=args.face,
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                confirmation=args.confirm,
            )
        except (
            FileNotFoundError,
            PermissionError,
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            error(str(exc))
            return 1
        success(f"Face destroyed explicitly: [bold]{result.face_id}[/bold]")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_emergency_destroy_vessel_command(args) -> int:
    panic_monitor = EmergencyDaemon(args.vessel)
    svc = VesselWorkflowService()
    try:
        panic_monitor.start()
        if _file_command_needs_camera(args):
            gate.start()
            if not svc.wait_for_camera_frame():
                error("Camera feed did not become available.")
                return 1
        try:
            emergency_pw = _resolve_required_emergency_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1
        try:
            result = svc.destroy_vessel(
                args.vessel,
                emergency_pw,
                selector=args.face,
                object_image_path=getattr(args, "object_image", None),
                camera_object=getattr(args, "camera_object", False),
                confirmation=args.confirm,
            )
        except (
            FileNotFoundError,
            PermissionError,
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            error(str(exc))
            return 1
        success(f"Vessel destroyed explicitly: [bold]{result.vessel_path}[/bold]")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()


def _run_store_command(args) -> int:
    if not getattr(args, "file", None):
        error("Input file is required. Use --input <path>.")
        return 1

    selected_value = getattr(args, "legacy_entry", None) or getattr(args, "entry", "a")
    selected_mode = resolve_mode(selected_value)
    legacy_entry_mode = getattr(args, "legacy_entry_mode", None)
    if legacy_entry_mode in gate.MODES:
        selected_mode = legacy_entry_mode

    panic_monitor = EmergencyDaemon(getattr(args, "vessel", "vault.bin"))
    svc = VesselWorkflowService()

    try:
        panic_monitor.start()
        gate.start()
        if not svc.wait_for_camera_frame():
            error("Camera feed did not become available.")
            return 1

        entry_label = display_mode_label(selected_mode)
        console.print()
        console.print(
            Panel(
                f"Entry: [bold cyan]{entry_label}[/bold cyan]\n"
                f"File:  [bold]{args.file}[/bold]\n"
                f"Vessel: [bold]{getattr(args, 'vessel', 'vault.bin')}[/bold]",
                title="[bold cyan]PHASMID — STORE[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()
        console.print(Rule("Authentication", style="dim cyan"))
        try:
            pw, purge_pw = _resolve_store_passwords(args)
        except ValueError as exc:
            error(str(exc))
            return 1

        console.print()
        console.print(Rule("Object Binding", style="dim cyan"))
        info(f"Calibrating object cue for [bold]{entry_label}[/bold]...")
        info(
            "The captured object will be stored as the local access cue for this entry."
        )
        if getattr(args, "passphrase_file", None):
            info("Position the bound object in view. Capture will begin automatically.")
            try:
                svc.capture_reference_for_mode(selected_mode)
            except RuntimeError as exc:
                error(str(exc))
                return 1
        else:
            reg_success, msg = _register_reference_key(selected_mode)
            if not reg_success:
                error(msg)
                return 1

        try:
            result = svc.store_file(
                getattr(args, "vessel", "vault.bin"),
                args.file,
                pw,
                purge_pw,
                selector=selected_mode,
                cue_sequence=gate.sequence_for_mode(selected_mode),
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            error(str(exc))
            return 1

        audit_event(
            "payload_stored",
            entry="local_entry",
            filename=os.path.basename(args.file),
            bytes=result.bytes_stored,
        )
        console.print()
        console.print(
            Panel(
                "[green]Protected entry saved.[/green]\n"
                "[green]Bound object cue registered.[/green]",
                border_style="green",
            )
        )
        return 0
    finally:
        panic_monitor.stop()
        gate.close()
        try:
            ui.close()
        except Exception:
            pass


def _run_retrieve_command(args) -> int:
    panic_monitor = EmergencyDaemon(getattr(args, "vessel", "vault.bin"))
    svc = VesselWorkflowService()

    try:
        panic_monitor.start()
        gate.start()
        attempt_limiter = FileAttemptLimiter()
        if not attempt_limiter.check("cli-retrieve").allowed:
            warn(text.ACCESS_TEMPORARILY_UNAVAILABLE)
            return 1

        if not svc.wait_for_camera_frame():
            error("Camera feed did not become available.")
            return 1

        ui.show_diagnostic()
        console.print()
        console.print(
            Panel(
                "[dim]Device Status:[/dim]  [bold green]READY[/bold green]",
                title="[bold cyan]PHASMID — RETRIEVE[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()

        console.print(Rule("Authentication", style="dim cyan"))
        try:
            pw = _resolve_retrieve_password(args)
        except ValueError as exc:
            error(str(exc))
            return 1

        console.print()
        console.print(Rule("Object Verification", style="dim cyan"))
        if getattr(args, "passphrase_file", None):
            info(
                "Position the bound object in view. Verification will begin automatically."
            )
            user_gesture_seq = svc.collect_auth_sequence()
        else:
            user_gesture_seq = _collect_auth_sequence()

        if not user_gesture_seq or user_gesture_seq[0] == gate.MATCH_NONE:
            ui.show_alert("ACCESS ERROR\nOBJECT NOT FOUND")
            attempt_limiter.record_failure("cli-retrieve")
            error("No bound object matched.")
            return 1

        console.print()
        show_loading("Verifying protected entry", 3)

        try:
            result = svc.retrieve_file(
                getattr(args, "vessel", "vault.bin"),
                pw,
                output_path=getattr(args, "out", None),
                cue_sequence=user_gesture_seq,
                use_attempt_limiter=False,
            )
        except PermissionError as exc:
            warn(str(exc))
            return 1
        except (FileNotFoundError, ValueError, OSError) as exc:
            ui.show_alert("ACCESS DENIED\nINVALID CREDENTIALS")
            audit_event("retrieve_failed")
            attempt_limiter.record_failure("cli-retrieve")
            console.print()
            console.print(
                Panel(
                    f"[red]{exc}[/red]",
                    title="[bold red]ACCESS DENIED[/bold red]",
                    border_style="red",
                )
            )
            return 1

        ui.show_alert("ACCESS GRANTED")
        attempt_limiter.record_success("cli-retrieve")
        show_loading("Preparing recovered payload", 2)
        console.print()
        console.print(
            Panel(
                f"[green]Decrypted [bold]{result.bytes_retrieved:,}[/bold] bytes[/green]"
                + (f"\n[dim]File: {result.filename}[/dim]" if result.filename else ""),
                title="[bold green]ACCESS GRANTED[/bold green]",
                border_style="green",
            )
        )
        if result.output_path is not None:
            success(f"Output written to: [bold]{result.output_path}[/bold]")

        audit_event(
            "payload_retrieved",
            entry="local_entry",
            filename=result.filename,
            bytes=result.bytes_retrieved,
        )

        vault = PhasmidVault(
            getattr(args, "vessel", "vault.bin"),
            size_mb=Path(getattr(args, "vessel", "vault.bin")).stat().st_size
            / (1024 * 1024),
        )
        if result.password_role == PhasmidVault.PURGE_ROLE:
            vault.purge_other_mode(result.mode)
            audit_event(
                "restricted_local_update",
                accessed_entry="local_entry",
                reason="restricted_recovery",
            )
            info("Operation completed.")
            return 0

        auto_purge_reason = _auto_purge_reason(result.mode)
        if auto_purge_reason:
            vault.purge_other_mode(result.mode)
            audit_event(
                "restricted_local_update",
                accessed_entry="local_entry",
                reason=auto_purge_reason,
            )
        elif _confirm_purge_other_mode(result.mode):
            vault.purge_other_mode(result.mode)
            audit_event("restricted_local_update", accessed_entry="local_entry")
        info("Operation completed.")
        return 0
    finally:
        panic_monitor.stop()
        gate.close()
        try:
            ui.close()
        except Exception:
            pass


def _run_legacy_command(args) -> None:
    selected_value = getattr(args, "legacy_entry", None) or getattr(args, "entry", "a")
    selected_mode = resolve_mode(selected_value)
    legacy_entry_mode = getattr(args, "legacy_entry_mode", None)
    if legacy_entry_mode in gate.MODES:
        selected_mode = legacy_entry_mode

    panic_monitor = EmergencyDaemon("vault.bin")
    gate_started = False

    try:
        panic_monitor.start()

        if args.command in {"store", "retrieve"}:
            gate.start()
            gate_started = True
            if not _wait_for_camera_frame():
                error("Camera feed did not become available.")
                return

        vault = PhasmidVault("vault.bin")

        if args.command == "init":
            console.print()
            console.print(
                Panel(
                    "[yellow]This will reinitialize the local container.[/yellow]",
                    title="[bold yellow]INITIALIZING LOCAL CONTAINER[/bold yellow]",
                    border_style="yellow",
                )
            )
            console.print()
            show_loading("Initializing local container with random data", 3)
            vault.format_container(rotate_access_key=True)
            audit_event("container_reinitialized")
            success("Local container initialized. Ready for protected entries.")

        elif args.command == "store":
            if not args.file:
                error("No input file specified.")
                return

            entry_label = display_mode_label(selected_mode)
            console.print()
            console.print(
                Panel(
                    f"Entry: [bold cyan]{entry_label}[/bold cyan]\nFile:  [bold]{args.file}[/bold]",
                    title="[bold cyan]PHASMID — STORE[/bold cyan]",
                    border_style="cyan",
                )
            )
            console.print()
            console.print(Rule("Authentication", style="dim cyan"))
            try:
                pw, purge_pw = _prompt_store_passwords()
            except ValueError as exc:
                error(str(exc))
                return

            console.print()
            console.print(Rule("Object Binding", style="dim cyan"))
            info(f"Calibrating object cue for [bold]{entry_label}[/bold]...")
            info(
                "The captured object will be stored as the local access cue for this entry."
            )
            reg_success, msg = _register_reference_key(selected_mode)
            if not reg_success:
                error(msg)
                return
            gesture_seq = gate.sequence_for_mode(selected_mode)

            with open(args.file, "rb") as f:
                data = f.read()

            console.print()
            console.print(Rule("Encryption", style="dim cyan"))
            show_loading("Preparing cryptographic recovery", 2)
            show_loading("Encrypting payload with AES-256-GCM", 1.5)

            vault.store(
                pw,
                data,
                gesture_seq,
                filename=os.path.basename(args.file),
                mode=selected_mode,
                restricted_recovery_password=purge_pw,
            )
            audit_event(
                "payload_stored",
                entry="local_entry",
                filename=os.path.basename(args.file),
                bytes=len(data),
            )
            console.print()
            console.print(
                Panel(
                    "[green]Protected entry saved.[/green]\n[green]Bound object cue registered.[/green]",
                    border_style="green",
                )
            )

        elif args.command == "retrieve":
            ui.show_diagnostic()
            console.print()
            console.print(
                Panel(
                    "[dim]Device Status:[/dim]  [bold green]READY[/bold green]",
                    title="[bold cyan]PHASMID — RETRIEVE[/bold cyan]",
                    border_style="cyan",
                )
            )
            console.print()

            attempt_limiter = FileAttemptLimiter()
            attempt_scope = "cli-retrieve"
            if not attempt_limiter.check(attempt_scope).allowed:
                warn(text.ACCESS_TEMPORARILY_UNAVAILABLE)
                return

            console.print(Rule("Authentication", style="dim cyan"))
            pw = getpass.getpass("  Access password: ")

            console.print()
            console.print(Rule("Object Verification", style="dim cyan"))
            user_gesture_seq = _collect_auth_sequence()

            if not user_gesture_seq or user_gesture_seq[0] == gate.MATCH_NONE:
                ui.show_alert("ACCESS ERROR\nOBJECT NOT FOUND")
                attempt_limiter.record_failure(attempt_scope)
                error("No bound object matched.")
                return

            console.print()
            show_loading("Verifying protected entry", 3)

            result, filename, password_role = vault.retrieve_with_policy(
                pw,
                user_gesture_seq,
                mode=gate.MODES[0],
            )
            accessed_mode = gate.MODES[0]

            if result is None:
                result, filename, password_role = vault.retrieve_with_policy(
                    pw,
                    user_gesture_seq,
                    mode=gate.MODES[1],
                )
                accessed_mode = gate.MODES[1]

            if result is not None:
                attempt_limiter.record_success(attempt_scope)
                ui.show_alert("ACCESS GRANTED")

                show_loading("Preparing recovered payload", 2)
                console.print()
                console.print(
                    Panel(
                        f"[green]Decrypted [bold]{len(result):,}[/bold] bytes[/green]"
                        + (f"\n[dim]File: {filename}[/dim]" if filename else ""),
                        title="[bold green]ACCESS GRANTED[/bold green]",
                        border_style="green",
                    )
                )

                if args.out:
                    with open(args.out, "wb") as f:
                        f.write(result)
                    success(f"Output written to: [bold]{args.out}[/bold]")
                else:
                    try:
                        content = result.decode("utf-8")
                        console.print()
                        console.print(Rule("Payload", style="dim"))
                        console.print(
                            content[:500] + ("…" if len(content) > 500 else "")
                        )
                        console.print(Rule(style="dim"))
                    except UnicodeDecodeError:
                        info(
                            "Binary payload — use [bold]--out[/bold] to write to file."
                        )

                audit_event(
                    "payload_retrieved",
                    entry="local_entry",
                    filename=filename,
                    bytes=len(result),
                )
                if password_role == PhasmidVault.PURGE_ROLE:
                    vault.purge_other_mode(accessed_mode)
                    audit_event(
                        "restricted_local_update",
                        accessed_entry="local_entry",
                        reason="restricted_recovery",
                    )
                    info("Operation completed.")
                    return

                auto_purge_reason = _auto_purge_reason(accessed_mode)
                if auto_purge_reason:
                    vault.purge_other_mode(accessed_mode)
                    audit_event(
                        "restricted_local_update",
                        accessed_entry="local_entry",
                        reason=auto_purge_reason,
                    )
                    info("Operation completed.")
                elif _confirm_purge_other_mode(accessed_mode):
                    vault.purge_other_mode(accessed_mode)
                    audit_event("restricted_local_update", accessed_entry="local_entry")
                    info("Operation completed.")
                else:
                    info("Operation completed.")
            else:
                ui.show_alert("ACCESS DENIED\nINVALID CREDENTIALS")
                audit_event("retrieve_failed")
                attempt_limiter.record_failure(attempt_scope)
                console.print()
                console.print(
                    Panel(
                        "[red]Invalid credentials or object not recognised.[/red]",
                        title="[bold red]ACCESS DENIED[/bold red]",
                        border_style="red",
                    )
                )

        elif args.command == "brick":
            console.print()
            policy = RESTRICTED_ACTION_POLICIES["rapid_local_clear"]
            console.print(
                Panel(
                    "[yellow]This will permanently clear the local access path.[/yellow]",
                    title="[bold yellow]CLEARING LOCAL ACCESS PATH[/bold yellow]",
                    border_style="yellow",
                )
            )
            console.print()
            confirmation = console.input(
                f'  Type [bold red]"{policy.confirmation_phrase}"[/bold red] to confirm: '
            ).strip()
            try:
                require_restricted_action("rapid_local_clear", confirmation)
                vault.silent_brick()
                audit_event("access_path_cleared", source="cli")
                warn("Local access path cleared.")
            except ValueError as exc:
                info(f"Aborted: {exc}")
                return

    finally:
        panic_monitor.stop()
        if gate_started:
            gate.close()
        try:
            ui.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main() or 0)
