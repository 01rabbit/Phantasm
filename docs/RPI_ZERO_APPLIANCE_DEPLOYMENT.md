# Raspberry Pi Zero 2 W Appliance Deployment

This is the authoritative Raspberry Pi Zero 2 W appliance deployment guide for Phasmid.

This deployment plan reduces exposed services and local leakage for Raspberry Pi Zero 2 W class hardware. It does not provide physical tamper resistance, anti-forensic guarantees, or hardware-grade secure storage.

## Base System

- Use Raspberry Pi OS Lite with only required packages installed.
- Create a dedicated `phasmid` system user.
- Place the application under `/opt/phasmid`.
- Place runtime state under `/var/lib/phasmid` or another dedicated local directory.
- Set `umask 077` for provisioning and service execution.
- Keep the configured state directory mode `0700`.
- Keep sensitive state files mode `0600`.
- Keep audit disabled by default.
- Keep debug disabled by default.
- Disable swap or minimize it as far as the device workload allows.
- Use `tmpfs` for uploads and temporary files when practical.
- Do not add cloud dependencies, telemetry, analytics, remote unlock, or remote management.

## Camera Module

Recommended camera for the Raspberry Pi Zero 2 W prototype:

- Raspberry Pi Camera Module 3 NoIR Wide
- Sony IMX708 12MP sensor
- Mechanical autofocus
- Wide FoV
- NoIR support for optional infrared illumination
- CSI connection

Raspberry Pi Zero 2 W requires a 22-pin to 15-pin Raspberry Pi Zero camera cable. The standard 15-pin camera cable is not compatible with the Pi Zero camera connector.

The camera is used as an operational object-cue capture device. It is not treated as cryptographic key material, biometric identity proof, or a tamper-resistant sensor.

## Hardware Reference Photos

![Phasmid hardware main tripod](./images/phasmid-hardware-main-tripod.jpg)
![Phasmid hardware RPi Zero 2 W](./images/phasmid-hardware-rpi-zero2w.jpg)

## Physical Signature Reduction (Stealth)

To prevent the device from drawing attention via LEDs or serial console activity:

### Disable LEDs

Add the following to `/boot/config.txt`:

```text
# Disable Power LED
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off
# Disable Activity LED
dtparam=act_led_trigger=none
dtparam=act_led_activelow=off
```

### Suppress Boot Console

In `/boot/cmdline.txt`, add `consoleblank=0 loglevel=1 quiet` and remove `console=tty1` to ensure no text is emitted to a connected display during boot.

## Local-Only Network Posture

- Bind the WebUI to `127.0.0.1` by default, including when it is started from the TUI with `w`.
- Use USB Ethernet gadget access for local operator access when required. Set `PHASMID_WEBUI_EXPOSE_GADGET=1`, which binds the gadget interface address (`usb0` or `enx*`) and nothing else. Do not use `PHASMID_HOST=0.0.0.0` for this.
- Disable SSH after provisioning unless a controlled maintenance window requires it.
- Disable Wi-Fi unless explicitly needed.
- Disable Bluetooth.
- Allow loopback traffic.
- Allow the USB gadget interface only when explicitly configured.
- Deny inbound traffic from all other interfaces.
- Do not expose the WebUI as an Internet-facing service.

## Recommended Environment

```text
PHASMID_FIELD_MODE=1
PHASMID_AUDIT=0
PHASMID_DEBUG=0
PHASMID_HOST=127.0.0.1
PHASMID_PORT=8000
PHASMID_STATE_DIR=/var/lib/phasmid
```

Leave `PHASMID_WEBUI_EXPOSE_GADGET` unset unless the operator interface is reached from a USB-tethered host. When it is set, everything on the other end of the USB link can reach the WebUI port. Pages, the mutation token, and `/video_feed` still require a page session opened with the access token, so the tethered host must be given that token before it can operate the device — treat handing it over as granting operator access.

For high-risk deployments, do not store all recovery conditions on the same physical medium. Phasmid is strongest when the encrypted container, local state, memorized password, physical-object cue, and optional external key material are separated.

## systemd Service

An example unit is provided at `contrib/systemd/phasmid.service`.

Recommended hardening options include:

```ini
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/phasmid /var/lib/phasmid /run/phasmid
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallFilter=@system-service
UMask=0077
MemoryDenyWriteExecute=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
```

Adjust `ReadWritePaths` to match the actual application and state paths. Do not place external key material directly in the unit file.

## Firewall Guidance

The appliance should deny inbound traffic except loopback and the explicitly configured USB gadget interface.

Example policy goals:

- allow `lo`;
- allow the USB-side local address if used;
- deny inbound from Wi-Fi, Ethernet, and other interfaces;
- deny Internet-facing WebUI access;
- keep remote unlock and remote management out of scope.

## Key Material and Storage

On flash media, complete overwrite-based deletion cannot be guaranteed across every storage layer. Phasmid therefore treats restricted recovery primarily as key-path invalidation and key-material destruction, with best-effort overwrite as a secondary measure.

External key material can be supplied with `PHASMID_HARDWARE_SECRET_FILE` or `PHASMID_HARDWARE_SECRET_PROMPT=1`. For high-risk deployment, store external key material away from the same SD card that holds `vault.bin` and the state directory.

## Optional Volatile Key-Material Store (tmpfs)

Phasmid supports storing its state directory on a tmpfs mount via the
``PHASMID_TMPFS_STATE`` environment variable.  When configured, key material
(including the local vault access key) lives only in RAM and disappears
on power loss or controlled unmount.

This does NOT protect against live memory capture by a privileged attacker
or a compromised OS.  It reduces the window during which key material persists
on flash storage.

### Setup

Create a dedicated tmpfs mount in systemd:

```ini
# /etc/systemd/system/phasmid-keys.mount
[Unit]
Description=Phasmid volatile key-material store
Before=phasmid.service

[Mount]
What=tmpfs
Where=/run/phasmid-keys
Type=tmpfs
Options=mode=0700,uid=phasmid,gid=phasmid,size=8M,noexec,nosuid,nodev

[Install]
WantedBy=multi-user.target
```

Update `phasmid.service` to depend on the mount and use the volatile path:

```ini
[Unit]
After=phasmid-keys.mount
Requires=phasmid-keys.mount

[Service]
Environment=PHASMID_TMPFS_STATE=/run/phasmid-keys
ReadWritePaths=/run/phasmid-keys
```

### Failure Behavior

If ``PHASMID_TMPFS_STATE`` is set but the path does not exist or is not
accessible, Phasmid will refuse to start rather than silently falling back
to persistent storage.  This prevents accidental key-material leakage to
flash in configurations that expect volatile storage.

### Limitations

- tmpfs contents are lost on power loss.  A controlled reboot requires
  re-provisioning the state directory.
- tmpfs does not protect against a privileged attacker with access to
  ``/proc/<pid>/mem`` or physical RAM extraction.
- Swap must be disabled or encrypted; otherwise pages may be written to disk.
  Confirm swap status in the Doctor page before field evaluation.

## Optional LUKS Storage Layer

An optional dm-crypt/LUKS2 layer can be used as defense in depth for appliance deployments. This is not a compliance claim and does not make Phasmid certified data-at-rest infrastructure.

Use this only after confirming the target SD card layout. The commands below can erase data if pointed at the wrong device.

Recommended placement:

- dedicate a separate partition or external local volume for Phasmid runtime data;
- mount it at `/var/lib/phasmid-secure` or another dedicated path;
- set `PHASMID_STATE_DIR` to a directory on that mounted volume;
- keep `vault.bin` on the same encrypted volume or another encrypted local path;
- use a storage-layer passphrase that is different from Phasmid access passwords.

Example setup outline:

```bash
sudo cryptsetup luksFormat --type luks2 /dev/mmcblk0p3
sudo cryptsetup luksOpen /dev/mmcblk0p3 phasmid-state
sudo mkfs.ext4 -m 0 /dev/mapper/phasmid-state
sudo mkdir -p /var/lib/phasmid-secure
sudo mount /dev/mapper/phasmid-state /var/lib/phasmid-secure
sudo mkdir -p /var/lib/phasmid-secure/.state
sudo chown -R phasmid:phasmid /var/lib/phasmid-secure
sudo chmod 0700 /var/lib/phasmid-secure /var/lib/phasmid-secure/.state
```

Service environment example:

```ini
Environment=PHASMID_STATE_DIR=/var/lib/phasmid-secure/.state
WorkingDirectory=/var/lib/phasmid-secure
ReadWritePaths=/var/lib/phasmid-secure
```

Boot and service ordering:

- The encrypted volume must be opened and mounted before `phasmid.service` starts.
- If the volume is unavailable, the service should fail closed rather than create a fallback state directory on unencrypted storage.
- Record the mount procedure in the deployment notes.
- Test reboot, mount failure, and no-network startup before field evaluation.

Systemd ordering example (for `/etc/crypttab` + `.mount` unit approach):

```ini
# /etc/systemd/system/phasmid.service (additional Unit section entries)
[Unit]
After=var-lib-phasmid\x2dsecure.mount
Requires=var-lib-phasmid\x2dsecure.mount
```

Add to `/etc/crypttab` (opened at boot via systemd-cryptsetup):

```text
phasmid-state /dev/mmcblk0p3 none luks,discard
```

Add to `/etc/fstab`:

```text
/dev/mapper/phasmid-state /var/lib/phasmid-secure ext4 defaults,noatime 0 2
```

With this configuration, systemd will refuse to start `phasmid.service` if
the LUKS volume is not opened and mounted.  This ensures the service never
writes key material to unencrypted storage.

Recovery and backup notes:

- Losing the LUKS passphrase can make the local Phasmid state unavailable.
- Backups of the encrypted volume should be handled as sensitive local media.
- Do not store storage-layer passphrases, Phasmid access passwords, and optional external key material together.
- SD card cloning can copy encrypted containers and stale state; review cloned media before reuse.
- Test boot, mount failure (`cryptsetup luksClose`), and no-network startup scenarios before field evaluation.
