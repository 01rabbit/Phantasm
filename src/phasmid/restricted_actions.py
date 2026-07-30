"""Policy for restricted local actions shared by the CLI and the WebUI.

Confirmation phrases in this module are **confirmation-only**.  They are public
constants in an open-source repository, so they carry no entropy and are not an
authorization control.  Their only job is to stop an operator from destroying
local state by a mis-click or a stray keystroke.

Authorization for a restricted action is the combination of:

- the deployment capability (`capabilities.py`),
- a live restricted confirmation session, where the policy requires one, and
- for the WebUI, an unlocked page session plus the per-process mutation token
  (`web_server.require_ui_unlock` and `web_server.require_web_token`).

Never add an action whose only gate is a phrase from this module.
"""

from dataclasses import dataclass

from . import strings as text
from .capabilities import Capability


class RestrictedActionRejected(Exception):
    def __init__(self, message=text.OPERATION_REJECTED):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class RestrictedActionPolicy:
    action_id: str
    capability: Capability
    confirmation_phrase: str | None = None
    require_restricted_confirmation: bool = True
    require_password_reentry: bool = False
    require_object_cue: bool = False


# Central confirmation phrases shared by CLI and WebUI.
# Public constants: typo guards, not credentials.  See the module docstring.
DESTRUCTIVE_CLEAR_PHRASE = "CLEAR LOCAL ENTRY"
INITIALIZE_CONTAINER_PHRASE = "INITIALIZE LOCAL CONTAINER"
EMERGENCY_BRICK_PHRASE = "CLEAR LOCAL ACCESS PATH"
RESTRICTED_CONFIRMATION_PHRASE = "CONFIRM LOCAL CONTROL"
OVERWRITE_CONFIRMATION_PHRASE = "REPLACE LOCAL ENTRY"
# Shared verbatim with `phasmid emergency destroy-face --confirm`, so the two
# interfaces ask for the same words rather than each inventing their own.
DESTROY_FACE_PHRASE = "DESTROY FACE"

RESTRICTED_ACTION_POLICIES = {
    "clear_unmatched_entry": RestrictedActionPolicy(
        action_id="clear_unmatched_entry",
        capability=Capability.RESTRICTED_ACTION,
        confirmation_phrase=DESTRUCTIVE_CLEAR_PHRASE,
    ),
    "clear_local_access_path": RestrictedActionPolicy(
        action_id="clear_local_access_path",
        capability=Capability.RESTRICTED_ACTION,
        confirmation_phrase=EMERGENCY_BRICK_PHRASE,
    ),
    "initialize_container": RestrictedActionPolicy(
        action_id="initialize_container",
        capability=Capability.RESTRICTED_ACTION,
        confirmation_phrase=INITIALIZE_CONTAINER_PHRASE,
    ),
    "destroy_face": RestrictedActionPolicy(
        action_id="destroy_face",
        capability=Capability.RESTRICTED_ACTION,
        confirmation_phrase=DESTROY_FACE_PHRASE,
        # The only action here that is gated by a *credential* rather than by a
        # public phrase alone: the caller must know the Face's destroy password
        # and hold its bound object. A separate restricted-confirmation session
        # on top of that would add no authorization, only a step - and this is
        # the one action reached under duress, where every extra step is a step
        # taken in front of the person applying it.
        require_restricted_confirmation=False,
        require_password_reentry=True,
        require_object_cue=True,
    ),
    "rapid_local_clear": RestrictedActionPolicy(
        action_id="rapid_local_clear",
        capability=Capability.RAPID_LOCAL_CLEAR,
        confirmation_phrase="BRICK",
        require_restricted_confirmation=False,
    ),
}


def evaluate_restricted_action(
    policy: RestrictedActionPolicy,
    *,
    capability_allowed: bool,
    restricted_confirmed: bool,
    confirmation: str = "",
    password_reentered: bool = True,
    object_cue_accepted: bool = True,
):
    """Evaluate a restricted action against its policy.

    `confirmation` is matched against a public phrase, so a caller must never
    treat a successful evaluation as evidence that the caller was authenticated.
    The caller is responsible for establishing authorization first.
    """
    if not capability_allowed:
        raise RestrictedActionRejected(text.OPERATION_UNAVAILABLE)
    if policy.require_restricted_confirmation and not restricted_confirmed:
        raise RestrictedActionRejected(text.RESTRICTED_CONFIRMATION_REQUIRED)
    if (
        policy.confirmation_phrase is not None
        and confirmation != policy.confirmation_phrase
    ):
        raise RestrictedActionRejected(text.CONFIRMATION_REJECTED)
    if policy.require_password_reentry and not password_reentered:
        raise RestrictedActionRejected(text.OPERATION_REJECTED)
    if policy.require_object_cue and not object_cue_accepted:
        raise RestrictedActionRejected(text.OPERATION_REJECTED)
    return True
