# Restricted Actions

Restricted actions are local operations that can change local access paths, initialize stored data, or alter maintenance state.

They are separated from normal Store and Retrieve flows.

## Guard Model

Restricted actions are evaluated by a shared local policy layer. Depending on the action, the policy can require:

- an unlocked WebUI page session;
- a valid Web mutation token;
- a fresh restricted confirmation window;
- a typed action phrase;
- a deployment capability mode that permits the action.

The guard model is local-only. It does not rely on external approval devices or cloud services.

### Typed phrases are confirmation, not authorization

The phrases in `src/phasmid/restricted_actions.py` — `CLEAR LOCAL ENTRY`,
`INITIALIZE LOCAL CONTAINER`, `CLEAR LOCAL ACCESS PATH`, `CONFIRM LOCAL CONTROL`,
`REPLACE LOCAL ENTRY`, and the rapid-clear trigger — are public constants in an
open-source repository. They carry no entropy and anyone can read them.

Their only purpose is to stop an operator from destroying local state by a
mis-click or a stray keystroke. Authorization comes from the page session, the
mutation token, the restricted confirmation window, and the deployment
capability. Do not add an action whose only server-side gate is a typed phrase,
and do not describe a phrase as confidential in code, documentation, or UI text.

## CLI Behavior

CLI commands must use neutral wording and must not describe internal storage layout, trial order, or restricted recovery side effects.

No high-risk command should provide a single-step `--force` shortcut. Dangerous local actions should remain deliberate, typed, and auditable.

## WebUI Behavior

Normal WebUI navigation does not link to restricted routes. Hidden routes are UX concealment only and are not a security boundary by themselves.

Server-side policy checks remain required even when a route is not visible in navigation.

## Review Checks

Reviewers should test:

- direct restricted-route access without an unlocked page session;
- direct restricted-route access without confirmation;
- correct typed phrase with no page session, no token, or no confirmation window;
- wrong typed phrase;
- expired restricted confirmation;
- deployment capability mode that disables the action;
- Field Mode before and after restricted confirmation.
