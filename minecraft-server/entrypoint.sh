#!/bin/sh

# ==================================================================================================
# entrypoint.sh
#
# Runs on every container start, against the EFS-backed /data volume. Responsible for EULA
# acceptance and setting important server properties.
#
# server.properties handling only sets important properties because paper will fill the rest with
# default values.
#
# whitelist.json is handled differently - an empty file is only created if absent. This means at
# first boot, no players will be allowed. Add players as an op or through RCON.
# ==================================================================================================

set -eu

DATA_DIR="/data"
PROPERTIES_FILE="${DATA_DIR}/server.properties"
WHITELIST_FILE="${DATA_DIR}/whitelist.json"
EULA_FILE="${DATA_DIR}/eula.txt"

# ==================================================================================================
# 1. EULA acceptance
# Write true to eula.txt if eula.txt does not exist so the server doesn't fail to start on the first
# boot with a fresh volume.
# ==================================================================================================
if [ ! -f "${EULA_FILE}" ]; then
    echo "eula=true" > "${EULA_FILE}"
fi

# ==================================================================================================
# 2. Enforce server-port, enable-status, enable-query online-mode, whitelist, and RCON in
# server.properties
#
# set_property KEY VALUE
#   - If KEY already exists in the file (commented or not), replace its line.
#   - If KEY is absent, append it.
# This makes the enforced keys safe to run on both a minimal/missing file and a full,
# Paper-completed one from a prior boot.
#
# Implemented with grep -v + printf rather than sed, so it's safe for arbitrary values that could
# conflict with a sed delimiter.
# ==================================================================================================
set_property() {
    key="$1"
    value="$2"

    if [ ! -f "${PROPERTIES_FILE}" ]; then
        touch "${PROPERTIES_FILE}"
    fi

    grep -v "^${key}=" "${PROPERTIES_FILE}" > "${PROPERTIES_FILE}.tmp" 2>/dev/null || true
    printf '%s=%s\n' "${key}" "${value}" >> "${PROPERTIES_FILE}.tmp"
    mv "${PROPERTIES_FILE}.tmp" "${PROPERTIES_FILE}"
}

# Bind server to the custom obscure port.
set_property "server-port" "35132"

# Suppress status ping responses to scanners.
set_property "enable-status" "false"
set_property "enable-query" "false"

# Require Mojang/Microsoft-authenticated accounts to connect.
set_property "online-mode" "true"

# Enable the whitelist and make Paper actively re-check it (kicks non-whitelisted players
# immediately, not just at initial connection).
set_property "white-list" "true"
set_property "enforce-whitelist" "true"

# Enable RCON for out-of-game admin access (whitelist/op management, etc.).
# Bound to all interfaces inside the container; actual exposure is controlled by the
# AdminIp-restricted security group rule, not here.
set_property "enable-rcon" "true"
set_property "rcon.port" "25575"
set_property "rcon.password" "${RCON_PASSWORD:?RCON_PASSWORD environment variable must be set}"

# ==================================================================================================
# 3. Ensure whitelist.json exists, empty, but only if absent
# Overwriting this file on every boot would wipe out anyone already added. Only create it if it
# doesn't exist at all, which only covers a first boot on a fresh volume.
# ==================================================================================================
if [ ! -f "${WHITELIST_FILE}" ]; then
    echo "[]" > "${WHITELIST_FILE}"
fi

# ==================================================================================================
# 5. Hand off to the real command (the JVM)
# ==================================================================================================
exec "$@"
