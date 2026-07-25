# Raspberry Pi Zero 2 W Deployment

This is a compact deployment summary. The authoritative appliance deployment guide is `docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md`.

This document describes a conservative local appliance deployment for Raspberry Pi Zero 2 W class hardware.

Phasmid should remain local-only. The expected access path is localhost during development or USB Ethernet gadget mode during appliance use. Do not expose the WebUI to an untrusted network.

## Network Posture

- Bind the WebUI to `127.0.0.1` by default. This is what the TUI `w` key does with no further configuration.
- Use USB Ethernet gadget access for the operator interface when needed. Set `PHASMID_WEBUI_EXPOSE_GADGET=1` to bind the USB gadget interface address (`usb0` or `enx*`) instead of loopback. It binds that one address, never all interfaces, and falls back to loopback when no gadget address is present.
- Do not set `PHASMID_HOST=0.0.0.0`. The WebUI serves its pages without authentication, so a wildcard bind exposes vault operations to every attached network.
- Disable SSH by default.
- Disable Wi-Fi and Bluetooth by default unless explicitly required for a controlled deployment.
- Do not add cloud unlock, telemetry, analytics, or remote management.
- Configure a firewall so only localhost or the intended USB-side management address can reach the service.

## Service Account

- Run Phasmid as a dedicated unprivileged service user.
- Keep the runtime state directory owned by that user.
- Use `0700` for the state directory.
- Use `0600` for state files.
- Do not run the WebUI as root.

## Storage and Temporary Files

- Keep `vault.bin` and the configured state directory on encrypted local storage when possible.
- For appliance deployments, `docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md` defines the optional LUKS2 storage-layer procedure.
- Disable swap for the appliance deployment.
- Use `tmpfs` for upload and temporary working directories where practical.
- Keep audit logging disabled by default.
- Keep debug mode disabled by default.

## Key-Material Destruction

Restricted local data-loss behavior should be understood primarily as key-material destruction and local access-path invalidation.

On SD cards and other flash media, overwrite behavior is best effort only. Wear leveling, snapshots, backups, filesystem journals, and controller behavior can leave old data behind. Recovery resistance depends primarily on destruction, rotation, or removal of required key material such as `.state/access.bin`, plus any external values supplied through deployment policy.

Best-effort overwrite may still be attempted, but it must not be described as guaranteed secure deletion.

## Example systemd Unit

Adjust paths and user names for the target image.

```ini
[Unit]
Description=Phasmid local WebUI
After=network.target

[Service]
Type=simple
User=phasmid
Group=phasmid
WorkingDirectory=/opt/phasmid
Environment=PYTHONPATH=/opt/phasmid/src
Environment=PHASMID_HOST=127.0.0.1
Environment=PHASMID_PORT=8000
Environment=PHASMID_FIELD_MODE=1
Environment=PHASMID_AUDIT=0
Environment=PHASMID_DEBUG=0
ExecStart=/usr/bin/python3 -m phasmid.web_server
Restart=on-failure
RestartSec=2

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/phasmid /var/lib/phasmid
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
```

## Operational Checklist

- Create a dedicated `phasmid` user.
- Place code under `/opt/phasmid`.
- Place runtime state under `/var/lib/phasmid` or another dedicated directory.
- Set `PHASMID_STATE_DIR` to that runtime path.
- Confirm directory mode `0700`.
- Confirm state file mode `0600`.
- Confirm SSH is disabled unless explicitly needed.
- Confirm Wi-Fi and Bluetooth are disabled unless explicitly needed.
- Confirm swap is disabled.
- Confirm firewall policy blocks unintended inbound traffic.
- Run the full test suite before appliance packaging.
