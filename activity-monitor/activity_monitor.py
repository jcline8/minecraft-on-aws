#!/usr/bin/env python3
"""
activity_monitor.py

Sidecar process for the Minecraft ECS task. Runs alongside the Paper server container
(same task, same network namespace) and every POLL_INTERVAL_SECONDS:
  1. Connects to the Paper server's RCON console on localhost, via the `mcrcon` library.
  2. Sends the `list` command.
  3. Determines whether any players are currently connected (binary, not a headcount).
  4. Publishes a single CloudWatch metric: Namespace "Minecraft", MetricName "HostIsActive",
     Value 0 or 1.

Failure handling (validated by hand against a real Paper server + mcrcon CLI before writing this):
  - Auth failure (wrong password)      -> distinct, known failure. Skip the cycle.
  - Connection refused / unreachable   -> would otherwise hang indefinitely (confirmed against
                                           the mcrcon C CLI). Guarded here with an explicit
                                           socket-level connect timeout, applied BEFORE connect()
                                           is called -- the mcrcon library's own `timeout` param
                                           only guards socket reads via SIGALRM, not the initial
                                           connect() call, so it does not by itself prevent this
                                           hang. See _connect_with_timeout() below.
  - Any other unexpected error         -> skip the cycle, never crash the loop.

On any failure, NOTHING is published for that cycle. This is intentional: the alarm built on
this metric uses TreatMissingData: notBreaching, so a missing datapoint is treated as "not idle"
rather than corrupting the signal with a guessed value.

Environment variables:
  RCON_PASSWORD           Required. Same password injected into the Paper container.
  POLL_INTERVAL_SECONDS   Optional. Defaults to 100 (3 samples per 300s alarm period).
  RCON_TIMEOUT_SECONDS    Optional. Defaults to 5. Applies to both connect and read.
"""

import logging
import os
import socket
import sys
import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from mcrcon import MCRcon, MCRconException

# ==================================================================================================
# Configuration
# ==================================================================================================
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASSWORD = os.environ.get("RCON_PASSWORD")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "100"))
RCON_TIMEOUT_SECONDS = int(os.environ.get("RCON_TIMEOUT_SECONDS", "5"))

CLOUDWATCH_NAMESPACE = "Minecraft"
CLOUDWATCH_METRIC_NAME = "HostIsActive"

# The exact, fixed string Paper/vanilla/Spigot emit for the `list` command when no players are
# connected. There is no variable content (no names) in this case, so exact-prefix match is
# sufficient and more robust than a regex over the whole (variable-length) response.
EMPTY_SERVER_PREFIX = "There are 0 of a max of"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("activity_monitor")


def _connect_with_timeout(mcr: MCRcon) -> None:
    """
    Connect an MCRcon instance with a connect-phase timeout.

    mcrcon's own `timeout` constructor arg only arms a SIGALRM guard inside _read(), which does
    NOT cover the initial socket.connect() call inside MCRcon.connect(). Left unguarded, a
    connect() against an unreachable/unresponsive host can block for the OS-level TCP timeout
    (60s+) or indefinitely -- confirmed by hand against the mcrcon C CLI when pointed at a bad
    port/host, and again against this exact code path (see below).

    IMPORTANT / history of this function: an earlier version of this patch pre-created a socket
    and called settimeout() on it BEFORE calling mcr.connect(), assuming connect() would reuse
    that socket. It does not: MCRcon.connect()'s first line is
    `self.socket = socket.socket(...)`, which unconditionally overwrites whatever was pre-set,
    discarding the timeout along with it. That version was verified only mechanically (the
    socket accepted a timeout value) and NOT behaviorally -- when actually tested against a live
    unreachable host, it hung for 3+ minutes with no timeout applied at all.

    This version instead temporarily replaces the `socket.socket` constructor that mcrcon's
    module calls internally, so that whatever socket object connect() creates for itself already
    has the timeout applied at construction time -- there is no window where an un-timed-out
    socket exists. This was confirmed against a real unreachable host to fail in ~timeout
    seconds rather than hang.
    """
    import mcrcon as mcrcon_module

    original_socket_ctor = mcrcon_module.socket.socket

    def _timed_socket_ctor(*args, **kwargs):
        sock = original_socket_ctor(*args, **kwargs)
        sock.settimeout(RCON_TIMEOUT_SECONDS)
        return sock

    mcrcon_module.socket.socket = _timed_socket_ctor
    try:
        mcr.connect()
    finally:
        mcrcon_module.socket.socket = original_socket_ctor


def fetch_list_response() -> str:
    """
    Open a fresh RCON connection, authenticate, run `list`, and return the raw response text.
    A new connection is used per cycle rather than kept alive, since polls are
    POLL_INTERVAL_SECONDS apart and a short-lived connection avoids having to detect/handle a
    stale or half-open socket between cycles.
    """
    if not RCON_PASSWORD:
        raise MCRconException("RCON_PASSWORD environment variable is not set")

    mcr = MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT, timeout=RCON_TIMEOUT_SECONDS)
    try:
        _connect_with_timeout(mcr)
        return mcr.command("list")
    finally:
        mcr.disconnect()


def is_server_active(list_response: str) -> bool:
    """True if the `list` response indicates at least one player is connected."""
    return not list_response.strip().startswith(EMPTY_SERVER_PREFIX)


def publish_metric(cloudwatch_client, is_active: bool) -> None:
    cloudwatch_client.put_metric_data(
        Namespace=CLOUDWATCH_NAMESPACE,
        MetricData=[
            {
                "MetricName": CLOUDWATCH_METRIC_NAME,
                "Value": 1.0 if is_active else 0.0,
                "Unit": "None",
            }
        ],
    )


def run_cycle(cloudwatch_client) -> None:
    list_response = fetch_list_response()
    active = is_server_active(list_response)
    publish_metric(cloudwatch_client, active)
    log.info("published HostIsActive=%d", 1 if active else 0)


def main() -> None:
    cloudwatch_client = boto3.client("cloudwatch")
    log.info(
        "starting activity monitor: poll_interval=%ss rcon_timeout=%ss namespace=%s metric=%s",
        POLL_INTERVAL_SECONDS,
        RCON_TIMEOUT_SECONDS,
        CLOUDWATCH_NAMESPACE,
        CLOUDWATCH_METRIC_NAME,
    )

    while True:
        try:
            run_cycle(cloudwatch_client)
        except (MCRconException, OSError, socket.timeout) as exc:
            # Covers: auth failure, connect timeout, connection refused, connection reset --
            # all expected during boot/shutdown windows or transient hiccups. Skip this cycle;
            # nothing is published, and TreatMissingData: notBreaching absorbs it.
            log.warning("skipping cycle: RCON error: %s", exc)
        except (BotoCoreError, ClientError) as exc:
            log.warning("skipping cycle: CloudWatch error: %s", exc)
        except Exception as exc:  # noqa: BLE001 - last-resort guard so the loop never dies
            log.error("skipping cycle: unexpected error: %s", exc)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
