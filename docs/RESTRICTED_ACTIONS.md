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

### Clearing an entry from the retrieval field

There are two ways to end a protected entry from the browser, and they exist for
different situations.

`POST /destroy_face` is the deliberate one: a visible panel, the typed
`DESTROY FACE` phrase, and the entry's clearing password. It is the browser
equivalent of `phasmid emergency destroy-face`, and it is the only restricted
action authorized by a credential rather than by a page session and a typed
phrase alone — which is why the phrase alone does not carry it (CLM-42).

The second way exists because the first one is visible. Under observation, going
to a panel labelled with what it does announces the decision before it is made.
So the clearing password is also accepted **in the ordinary retrieval field**,
where the access password goes:

- it is tried only after the access password has failed, so an access password
  can never be shadowed by a clearing password that happens to collide with it;
- the entry it can reach is fixed by the object matched at that moment, not by
  any request parameter, so one entry's clearing password cannot reach another;
- it returns no payload, and the response is byte for byte the response to a
  mistyped password;
- it does not count against the attempt limiter — the credential was correct,
  and an operator who has just ended one entry still needs their attempts.

The cost is deliberate and has to be rehearsed: **success is not reported.** The
operator learns it worked by the entry no longer opening. Anything that
confirmed it would also confirm it to whoever is watching the screen, which is
the only reason this path exists rather than the panel above.

Do not confuse this with `PHASMID_PURGE_CONFIRMATION=0`, which is a separate
thing entirely: it makes an ordinary *successful* retrieval clear the other
entry, with no credential typed and nothing asked. That fires on a correct
access password, so Doctor warns about it (as it does for
`PHASMID_DURESS_MODE`). The clearing password fires only when it is typed.

## Review Checks

Reviewers should test:

- direct restricted-route access without an unlocked page session;
- direct restricted-route access without confirmation;
- correct typed phrase with no page session, no token, or no confirmation window;
- wrong typed phrase;
- expired restricted confirmation;
- deployment capability mode that disables the action;
- Field Mode before and after restricted confirmation.
