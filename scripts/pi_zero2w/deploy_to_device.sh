#!/usr/bin/env bash
# scripts/pi_zero2w/deploy_to_device.sh
#
# Put the current repository onto the device, over the USB link, without the
# device needing the internet.
#
# Run from macOS, from the repository root, with the Pi attached over USB and
# the operator console stopped.
#
#   export PHASMID_PI_SSH=phasmid           # an ssh_config Host alias
#   bash scripts/pi_zero2w/deploy_to_device.sh
#
# `PHASMID_PI_SSH` is used verbatim as the ssh destination, so a ~/.ssh/config
# block is honoured whole - user, hostname, port, key, agent behaviour. Nothing
# here reconstructs any of it, because a script that rebuilds half of an ssh
# config gets the other half wrong: with
#
#     Host phasmid
#         HostName phasmid-pi.local
#         User phasmid
#
# the older `PHASMID_PI_USER`/`PHASMID_PI_HOST` pair would have connected as
# `pi` to a machine whose account is `phasmid`, and deployed into a home
# directory that does not exist.
#
# Without an alias, the older variables still work:
#   export PHASMID_PI_HOST=10.12.194.1
#   export PHASMID_PI_USER=phasmid
#
# Three things this does that a bare `git pull` on the device cannot:
#
#   * It refuses to start when the Mac's default route points at the Pi. The
#     gadget hands out a DHCP lease with a router option, macOS ranks that
#     service above Wi-Fi, and every packet meant for the internet goes to a
#     device that has no upstream. `git pull` then fails, or worse, quietly
#     succeeds against a stale cache and you deploy yesterday's tree.
#   * It carries the dependency wheels across itself. The device is meant to
#     stay off networks; making it fetch from PyPI to be updated contradicts
#     the thing being demonstrated, and on a Pi Zero 2 W a source build of the
#     OpenSSL bindings is not a thing that finishes.
#   * It verifies afterwards, on the device, rather than reporting success
#     because rsync exited zero.
#
# Optional:
#   PHASMID_PI_SSH_PORT   default 22
#   PHASMID_PI_SSH_KEY    path to a private key; ssh-agent is used if unset
#   PHASMID_DEPLOY_REF    what the local tree must match; default origin/main

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT" || exit 1

: "${PHASMID_DEPLOY_REF:=origin/main}"
# Deliberately not defaulted: the remote directory is asked of the device
# below, because $HOME depends on the account and the account depends on the
# ssh config. A default of /home/pi/Phasmid is a guess that deploys silently
# into the wrong place on any device whose user is not `pi`.
: "${PHASMID_PI_REMOTE_DIR:=}"

WHEEL_DIR="$REPO_ROOT/.deploy-wheels"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die()  { printf '\n\033[1;31mSTOP:\033[0m %s\n' "$*" >&2; exit 1; }

SSH_OPTS=(-o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

if [[ -n "${PHASMID_PI_SSH:-}" ]]; then
    SSH_DEST="$PHASMID_PI_SSH"
else
    [[ -n "${PHASMID_PI_HOST:-}" ]] || die \
        "Neither PHASMID_PI_SSH nor PHASMID_PI_HOST is set. With a ~/.ssh/config
       Host block, the short form is all you need:
           export PHASMID_PI_SSH=phasmid"
    SSH_DEST="${PHASMID_PI_USER:-pi}@$PHASMID_PI_HOST"
    SSH_OPTS+=(-p "${PHASMID_PI_SSH_PORT:-22}")
    [[ -n "${PHASMID_PI_SSH_KEY:-}" ]] && SSH_OPTS+=(-i "$PHASMID_PI_SSH_KEY")
fi

pi_ssh() { ssh "${SSH_OPTS[@]}" "$SSH_DEST" "$@"; }

# ── 1. reach the device, and ask it where it is ───────────────────────────────
# The address is taken from the connection rather than from a variable. The
# destination may be an ssh_config alias or an mDNS name, and `route -n get`
# needs an address; asking the far end removes the guess. mDNS keeps working
# even when the default route is wrong, because it is link-local multicast -
# which is why this can run before the check below rather than after it.

say "Reaching the device"

conn="$(pi_ssh 'echo "$SSH_CONNECTION"' 2>/dev/null)"
[[ -n "$conn" ]] || die "cannot ssh to '$SSH_DEST'. Check that the device is
       attached, that sshd is up, and that the alias resolves:
           ssh -G $SSH_DEST | head"
# SSH_CONNECTION is "client-ip client-port server-ip server-port".
pi_addr="$(awk '{print $3}' <<<"$conn")"
info "device address  : $pi_addr"

if [[ -z "$PHASMID_PI_REMOTE_DIR" ]]; then
    PHASMID_PI_REMOTE_DIR="$(pi_ssh 'echo "$HOME/Phasmid"' 2>/dev/null)"
    [[ -n "$PHASMID_PI_REMOTE_DIR" ]] || die "cannot determine the remote
       directory. Set PHASMID_PI_REMOTE_DIR explicitly."
fi
info "remote directory: $PHASMID_PI_REMOTE_DIR"
pi_ssh "test -d '$PHASMID_PI_REMOTE_DIR/.git'" || die \
    "$PHASMID_PI_REMOTE_DIR on the device is not a checkout. Set
       PHASMID_PI_REMOTE_DIR to the right path."

# ── 2. the default route ──────────────────────────────────────────────────────
# The reported failure. Checked before any download, because everything after
# this assumes the Mac can still reach the internet.

say "Checking that the device has not taken the default route"

if command -v route >/dev/null 2>&1; then
    pi_iface="$(route -n get "$pi_addr" 2>/dev/null | awk '/interface:/{print $2}')"
    default_iface="$(route -n get default 2>/dev/null | awk '/interface:/{print $2}')"
    info "route to the Pi : ${pi_iface:-unknown}"
    info "default route   : ${default_iface:-none}"

    if [[ -n "$pi_iface" && "$pi_iface" == "$default_iface" ]]; then
        cat >&2 <<EOF

The Mac is sending internet traffic to the Pi. The Pi has no upstream, so
nothing will resolve and nothing will download.

Fix it once, in System Settings > Network > (...) > Set Service Order:
drag Wi-Fi ABOVE the USB gadget service, then Apply. macOS takes the default
route from the highest active service, so this survives replugging.

Or from a shell, to see the current order and put Wi-Fi first:

  networksetup -listnetworkserviceorder
  sudo networksetup -ordernetworkservices "Wi-Fi" "<gadget service name>" <the rest, in order>

To unblock this session only, without changing anything permanent:

  sudo route -n delete default -interface $pi_iface

The device stays reachable at $pi_addr either way - removing the default route
does not remove the route to its own directly-connected subnet.
EOF
        die "default route points at the device"
    fi
fi

# HEAD, not GET: /simple/ is the entire package index, tens of megabytes, and
# -m bounds the whole transfer rather than the connection. The first version of
# this check asked for that whole index inside a 10-second budget and stopped a
# deployment on a network that was working - the transfer was slow, not absent.
#
# And the failure is named rather than summarised, because more than one thing
# produces "cannot reach pypi.org" and they need different fixes. Comparing
# interfaces, as the check above does, catches the Pi holding the *route* - it
# does not catch the Pi holding the *resolver*. macOS merges DNS servers from
# every active service, so a gadget lease carrying `dhcp-option 6` can put the
# device in the resolver list while the default route is correctly on Wi-Fi;
# name resolution then fails with routing that looks perfect. curl's exit code
# separates that from a refused connection and from a timeout, so it is
# reported instead of guessed at.
for host in https://pypi.org/simple/ https://files.pythonhosted.org/; do
    reach_error="$(curl -fsS -I --connect-timeout 5 -m 20 -o /dev/null "$host" 2>&1)"
    reach_code=$?
    [[ $reach_code -eq 0 ]] && continue

    case $reach_code in
        6) cause="DNS. The name did not resolve.

       Look at the resolver actually being used before assuming a cause -
       a hotel or conference network answers here far more often than the
       device does:

           scutil --dns | grep -A2 'resolver #1'
           networksetup -getdnsservers Wi-Fi

       If the address listed is the device's, macOS has merged its resolver in
       (it merges resolvers from every active service, so this happens with the
       default route correctly on Wi-Fi). The durable fix is then on the device
       - stop the lease carrying a DNS server at all (dnsmasq: dhcp-option=6).
       See scripts/pi_zero2w/README.md. To confirm, unplug it and re-run.

       If the address belongs to the network you are on, the device is not
       involved: the venue's resolver is failing, and a public one on Wi-Fi
       only (networksetup -setdnsservers Wi-Fi 1.1.1.1) gets you moving." ;;
        7) cause="the connection was refused or unreachable - a route or a firewall,
       not a name." ;;
        28) cause="the request timed out. Traffic is being accepted and then dropped,
       which is what a split-tunnel VPN or a captive portal looks like." ;;
        *) cause="curl exited $reach_code." ;;
    esac

    die "the Mac cannot reach $host

       $cause

       curl said: ${reach_error:-nothing}

       The wheels for the device are downloaded here, not there, so this has to
       work before anything is deployed."
done
info "pypi.org and files.pythonhosted.org reachable"

# ── 3. the local tree ─────────────────────────────────────────────────────────

say "Bringing the local repository to $PHASMID_DEPLOY_REF"

remote_name="${PHASMID_DEPLOY_REF%%/*}"
git fetch "$remote_name" || die "git fetch failed"

if [[ -n "$(git status --porcelain)" ]]; then
    git status --short
    die "the working tree has uncommitted changes. Deploying it would put a
       tree on the device that exists nowhere else. Commit or stash first."
fi

git merge --ff-only "$PHASMID_DEPLOY_REF" || die \
    "cannot fast-forward to $PHASMID_DEPLOY_REF. Resolve the local branch first."
info "at $(git rev-parse --short HEAD)  $(git log -1 --format=%s)"

# ── 4. wheels for the device's own Python ─────────────────────────────────────
# Asked, not assumed: the interpreter on the device decides which wheels match,
# and guessing produces an install that fails after the files are already there.

say "Collecting dependency wheels for the device"

pi_python="$PHASMID_PI_REMOTE_DIR/.venv/bin/python"
pi_tags="$(pi_ssh "$pi_python -c \"import sys,sysconfig;print(f'{sys.version_info.major}.{sys.version_info.minor}',sysconfig.get_platform())\"" 2>/dev/null)"
[[ -n "$pi_tags" ]] || die "cannot run $pi_python on the device. Is it attached,
       is SSH up, and does the venv exist?"

pi_pyver="${pi_tags%% *}"
pi_platform="${pi_tags##* }"
info "device Python   : $pi_pyver"
info "device platform : $pi_platform"

case "$pi_platform" in
    *aarch64*) ;;
    *) die "the device reports '$pi_platform', not aarch64. A 32-bit OS cannot
       run this - see scripts/pi_zero2w/README.md." ;;
esac

rm -rf "$WHEEL_DIR"
mkdir -p "$WHEEL_DIR"
python3 -m pip download -r requirements.txt -d "$WHEEL_DIR" \
    --only-binary=:all: \
    --implementation cp \
    --python-version "$pi_pyver" \
    --platform manylinux2014_aarch64 \
    --platform manylinux_2_17_aarch64 \
    --platform manylinux_2_28_aarch64 \
    --platform manylinux_2_34_aarch64 \
    >/dev/null || die "could not download wheels for $pi_pyver/aarch64.
       Run the same command without the redirect to see which package refused."
# The build requirements travel too. `pip install -e .` builds the package,
# and building is isolated: pip creates a fresh environment and fetches
# setuptools into it. `--no-deps` suppresses runtime dependencies and has no
# effect on that, so the device reached for pypi.org and failed with
# "Could not find a version that satisfies the requirement setuptools>=40.8.0"
# after everything else had already installed cleanly.
#
# Python 3.12 stopped seeding new virtual environments with setuptools, and the
# device runs 3.13, so it is genuinely absent rather than merely unpinned.
# These are py3-none-any, so the host's own tags are fine.
python3 -m pip download setuptools wheel -d "$WHEEL_DIR" --only-binary=:all: \
    >/dev/null || die "could not download the build requirements (setuptools, wheel)."

info "$(find "$WHEEL_DIR" -name '*.whl' | wc -l | tr -d ' ') wheels"

local_pip="$(python3 -m pip --version 2>/dev/null | awk '{print $2}')"
case "$local_pip" in
    2[0-3].*) info "note: local pip is $local_pip, which predates some of the
                 platform tags a 3.13 target can use. If a wheel is missing
                 below, upgrade it first: python3 -m pip install -U pip" ;;
esac

# ── 5. carry it across ────────────────────────────────────────────────────────
# The device's own state is never touched: .state, the vault and the venv are
# excluded, so a deployment cannot destroy a bound object or a stored file.

say "Syncing to $SSH_DEST:$PHASMID_PI_REMOTE_DIR"

rsync -az --delete \
    --exclude '.git/' \
    --exclude '.venv/' \
    --exclude '.state/' \
    --exclude '.deploy-wheels/' \
    --exclude '_pi_field_test/' \
    --exclude 'release/' \
    --exclude '*.vessel' \
    --exclude 'vault.bin' \
    --exclude '__pycache__/' \
    -e "ssh $(printf '%q ' "${SSH_OPTS[@]}")" \
    "$REPO_ROOT/" "$SSH_DEST:$PHASMID_PI_REMOTE_DIR/" \
    || die "rsync failed"

rsync -az -e "ssh $(printf '%q ' "${SSH_OPTS[@]}")" \
    "$WHEEL_DIR/" "$SSH_DEST:$PHASMID_PI_REMOTE_DIR/.deploy-wheels/" \
    || die "could not copy the wheels"

# ── 6. install, offline ───────────────────────────────────────────────────────

say "Installing on the device, with no network"

# Three steps, in this order, and none of them may reach a network.
#   1. the build requirements, so that step 3 has a setuptools to use;
#   2. the runtime dependencies;
#   3. the package itself, with build isolation off - otherwise pip discards
#      the setuptools installed in step 1 and goes looking for another one.
# PIP_NO_INDEX and PIP_FIND_LINKS are exported as well as passed, so that any
# subprocess pip spawns inherits the same offline view rather than falling back
# to the index list in the device's /etc/pip.conf.
pi_ssh "cd '$PHASMID_PI_REMOTE_DIR' && \
    export PIP_NO_INDEX=1 PIP_FIND_LINKS='$PHASMID_PI_REMOTE_DIR/.deploy-wheels' && \
    .venv/bin/pip install --quiet --no-index --find-links .deploy-wheels setuptools wheel && \
    .venv/bin/pip install --quiet --no-index --find-links .deploy-wheels -r requirements.txt && \
    .venv/bin/pip install --quiet --no-deps --no-build-isolation -e ." \
    || die "the install failed on the device"

# ── 7. verify on the device, not here ─────────────────────────────────────────

say "Verifying"

pi_ssh "cd '$PHASMID_PI_REMOTE_DIR' && \
    echo -n '   cryptography : ' && .venv/bin/python -c 'import cryptography;print(cryptography.__version__)' && \
    echo -n '   phasmid      : ' && .venv/bin/python -c 'import phasmid,pathlib;print(pathlib.Path(phasmid.__file__).parent)' && \
    echo -n '   templates    : ' && (grep -q statusInFlight src/phasmid/templates/base.html && echo 'status poller guarded' || echo 'MISSING - old base.html')" \
    || die "verification could not run"

expected="$(python3 -c "import re,pathlib;print(re.search(r'cryptography==(\S+)', pathlib.Path('requirements.txt').read_text()).group(1))")"
say "Done"
info "requirements.txt pins cryptography==$expected - it must match the line above."
info "The browser needs a hard reload (Cmd+Shift+R): base.html changed."
info "Wheels are left in .deploy-wheels/ on both sides; they are gitignored."
