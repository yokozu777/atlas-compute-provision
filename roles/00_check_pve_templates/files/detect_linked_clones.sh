#!/usr/bin/env bash
# Detect Proxmox linked clones of a template VMID via pmxcfs conf files.
#
# Usage:
#   detect_linked_clones.sh <template_vmid>
#
# Env:
#   PVE_QEMU_CONF_ROOT  Root with <node>/qemu-server/*.conf
#                       (default: /etc/pve/nodes). Override in tests.
#
# Prints space-separated child VMIDs (sorted), or empty line if none.
# Exit:
#   0  success (zero or more clones; empty greenfield PVE is OK)
#   2  invalid args
#   3  conf root missing / not a directory (misconfigured / not a PVE host)
set -euo pipefail

tid="${1:-}"
if [[ -z "${tid}" || ! "${tid}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: usage: detect_linked_clones.sh <numeric_template_vmid>" >&2
  exit 2
fi

CONF_ROOT="${PVE_QEMU_CONF_ROOT:-/etc/pve/nodes}"
if [[ ! -d "${CONF_ROOT}" ]]; then
  echo "ERROR: PVE qemu conf root is not a directory: ${CONF_ROOT}" >&2
  exit 3
fi

shopt -s nullglob
confs=("${CONF_ROOT}"/*/qemu-server/*.conf)
# Fresh PVE / wiped node: qemu-server dirs exist but have no *.conf yet.
# That means zero linked clones — not a misconfiguration.
if ((${#confs[@]} == 0)); then
  printf '\n'
  exit 0
fi

matches="$(mktemp)"
trap 'rm -f "${matches}"' EXIT

# Linked clones advertise parent: <tid> and/or disk refs base-<tid>-…
# Do not match bare /<tid>/ paths (noisy). grep rc 1 = no hits.
set +e
grep -HlE \
  -e "^parent: ${tid}$" \
  -e "base-${tid}-" \
  "${confs[@]}" >"${matches}" 2>/dev/null
grep_rc=$?
set -e

if ((grep_rc > 1)); then
  echo "ERROR: conf scan failed (grep rc=${grep_rc})" >&2
  exit "${grep_rc}"
fi

vmids="$(
  sed 's|.*/||; s|\.conf$||' "${matches}" \
    | grep -vx "${tid}" \
    | sort -n \
    | paste -sd' ' - || true
)"
printf '%s\n' "${vmids}"
exit 0
