# WebUI Operator Guide

This guide describes the standard local WebUI flow. It is for normal
Protect/Open use; diagnostics, audit information, inspection, and restricted
local updates remain advanced operator tasks.

Phasmid is research software. The WebUI is local-only by default and is not a
substitute for host integrity, full-disk encryption, or a complete response to
compelled disclosure.

## Before You Start

1. Start the WebUI from the TUI with `w`, or run
   `python3 -m phasmid.web_server` for a local development session.
2. Open the address shown by the TUI or use `http://127.0.0.1:8000` when the
   default host and port are in use. The TUI shows the address actually bound.
   Reaching the WebUI from a USB-tethered host requires
   `PHASMID_WEBUI_EXPOSE_GADGET=1`; loopback is the default.
3. Check the visible WebUI-active warning before continuing. Do not expose the
   interface to an untrusted network.

When the TUI manages the WebUI, it stops the server after ten minutes without
operator input. Stop it with `w` when the graphical task is complete.

## Home

The normal home screen has three entry points:

- **Protect a File** starts a new protection operation.
- **Open a Protected File** opens a file that was protected earlier.
- **Guided Mode** presents the same normal flows as step-by-step help.

**Advanced tools** contains maintenance, diagnostics, audit, and inspection.
Use those controls only when the normal flow does not meet the task. Hidden
routes are not an access-control boundary.

## Protect a File

The Protect screen keeps the action disabled until all three requirements are
ready.

1. **Choose the file.** Select one local file within the configured upload
   limit.
2. **Create the access password.** Use a distinct, memorable passphrase that
   meets the local policy. Do not reuse it for the optional restricted recovery
   password.
3. **Set the physical access object.** Present an object clearly to the local
   camera, then select **Capture access object**. Use an object that can be
   presented consistently later.
4. Review the readiness summary. When File, Password, and Access object are
   all ready, select **Protect file**.

The object cue is an operational access cue. It is not cryptographic key
material, and a camera match is not proof of identity.

### Optional advanced security controls

Expand **Advanced security options** only when needed:

- Set an optional restricted recovery password. It must differ from the access
  password.
- Check metadata risk before protection, or download a best-effort
  metadata-reduced copy for supported formats. Reduction is not complete
  sanitization and never replaces the original automatically.
- Add a local note only when it does not reveal sensitive identifying context.

If local space must be replaced, the interface requires restricted
confirmation and typed replacement confirmation. Review the prompt carefully:
replacement is a restricted local update and can remove an existing entry.

## Open a Protected File

1. **Show the access object.** Hold the same object in the camera view until a
   stable match is reported.
2. **Enter the access password.** Select **Open protected file**.
3. When **File ready** appears, select **Download file**.
4. Select **Finish and clear** when you no longer need the result. This clears
   the browser session state; it does not guarantee deletion of downloaded
   copies or browser/operating-system artifacts.

If access is not granted, verify the object, camera view, and password. The
interface intentionally provides limited failure detail.

## After Use

1. Download only the file needed for the task.
2. Clear the local browser session.
3. Return to the TUI and stop the WebUI with `w` when it is no longer needed.

For deployment posture and limits, read the
[Threat Model](THREAT_MODEL.md). For restricted actions, read
[Restricted Actions](RESTRICTED_ACTIONS.md).
