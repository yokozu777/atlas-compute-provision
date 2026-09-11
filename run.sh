#!/usr/bin/env bash
# Standalone runner for atlas-compute-provision.
#
# Usage:
#   cp inventory-example.yml inventory.yml   # edit hosts / VMIDs
#   # edit group_vars/all/atlas-compute-provision.yml (site secrets); stable defaults live in
#   # playbooks/group_vars/all/provision_defaults.yml
#   ./run.sh                                 # provision_nodes.yaml (default)
#   ./run.sh provision --tags 00_validate_provision
#   ./run.sh templates                       # build_templates.yaml
#   ./run.sh templates --tags 00_check_pve_templates,01_prepare_system
#   ./run.sh --check -v
#
# Env overrides:
#   INVENTORY                     inventory path (default: ./inventory.yml or inventory-example.yml)
#   PLAYBOOK                      playbook path (overrides mode: templates|provision)
#   EXTRA_VARS_FILE               optional ansible -e @file (e.g. vaulted secrets)
#   SSH_KEY / ANSIBLE_PRIVATE_KEY_FILE
#   CLUSTER_WORKSPACE_ID          workspace dir name under parent (overrides group_vars)
#   CLUSTER_WORKSPACE_PARENT      parent dir for workspaces (default: ./workspace)
#   CLUSTER_WORKSPACE_ROOT        full workspace path (overrides ID/parent-based default)
#   ANSIBLE_CONFIG                default: ./ansible.cfg
#
# Vars: group_vars/all/atlas-compute-provision.yml + optional host_vars/<host>.yml
# Stack overlays: examples/{jenkins,postgresql,kafka}/provision.example.yml via EXTRA_VARS_FILE
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export ANSIBLE_CONFIG="${ANSIBLE_CONFIG:-${ROOT}/ansible.cfg}"
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o StrictHostKeyChecking=no}"

if [[ -n "${SSH_KEY:-}" ]]; then
  export ANSIBLE_PRIVATE_KEY_FILE="${ANSIBLE_PRIVATE_KEY_FILE:-${SSH_KEY}}"
elif [[ -z "${ANSIBLE_PRIVATE_KEY_FILE:-}" ]]; then
  for candidate in "${HOME}/.ssh/id_ed25519" "${HOME}/.ssh/id_rsa"; do
    if [[ -f "${candidate}" ]]; then
      export ANSIBLE_PRIVATE_KEY_FILE="${candidate}"
      break
    fi
  done
fi

if [[ -n "${INVENTORY:-}" ]]; then
  :
elif [[ -f "${ROOT}/inventory.yml" ]]; then
  INVENTORY="${ROOT}/inventory.yml"
else
  INVENTORY="${ROOT}/inventory-example.yml"
fi

# Ansible localhost file lookups resolve relative paths against the playbook dir.
if [[ "${INVENTORY}" != /* ]]; then
  INVENTORY="${ROOT}/${INVENTORY#./}"
fi

MODE="provision"
if [[ $# -gt 0 ]]; then
  case "$1" in
    templates|provision)
      MODE="$1"
      shift
      ;;
  esac
fi

if [[ -n "${PLAYBOOK:-}" ]]; then
  :
elif [[ "${MODE}" == "templates" ]]; then
  PLAYBOOK="${ROOT}/playbooks/build_templates.yaml"
else
  PLAYBOOK="${ROOT}/playbooks/provision_nodes.yaml"
fi

CLUSTER_WORKSPACE_ID="${CLUSTER_WORKSPACE_ID:-ci.example.com}"
CLUSTER_WORKSPACE_PARENT="${CLUSTER_WORKSPACE_PARENT:-${ROOT}/workspace}"
# Resolve relative parent/root against repo root so Ansible localhost tasks land in-tree.
if [[ "${CLUSTER_WORKSPACE_PARENT}" != /* ]]; then
  CLUSTER_WORKSPACE_PARENT="${ROOT}/${CLUSTER_WORKSPACE_PARENT#./}"
fi
export CLUSTER_WORKSPACE_ID
export CLUSTER_WORKSPACE_PARENT
if [[ -n "${CLUSTER_WORKSPACE_ROOT:-}" && "${CLUSTER_WORKSPACE_ROOT}" != /* ]]; then
  CLUSTER_WORKSPACE_ROOT="${ROOT}/${CLUSTER_WORKSPACE_ROOT#./}"
fi
export CLUSTER_WORKSPACE_ROOT="${CLUSTER_WORKSPACE_ROOT:-${CLUSTER_WORKSPACE_PARENT}/${CLUSTER_WORKSPACE_ID}}"
mkdir -p "${CLUSTER_WORKSPACE_ROOT}"

if [[ ! -f "${INVENTORY}" ]]; then
  echo "error: inventory not found: ${INVENTORY}" >&2
  echo "hint: cp inventory-example.yml inventory.yml && edit hosts" >&2
  exit 1
fi

if [[ ! -f "${PLAYBOOK}" ]]; then
  echo "error: playbook not found: ${PLAYBOOK}" >&2
  exit 1
fi

if ! command -v ansible-playbook >/dev/null 2>&1; then
  echo "error: ansible-playbook not found in PATH" >&2
  exit 1
fi

EXTRA_VARS=()
# Always load the product catalog so inventory under examples/ still works.
if [[ -f "${ROOT}/group_vars/all/atlas-compute-provision.yml" ]]; then
  EXTRA_VARS+=(-e "@${ROOT}/group_vars/all/atlas-compute-provision.yml")
fi
if [[ -n "${EXTRA_VARS_FILE:-}" ]]; then
  if [[ ! -f "${EXTRA_VARS_FILE}" ]]; then
    echo "error: EXTRA_VARS_FILE not found: ${EXTRA_VARS_FILE}" >&2
    exit 1
  fi
  EXTRA_VARS+=(-e "@${EXTRA_VARS_FILE}")
fi

# Keep provision_hosts_file aligned with the inventory actually used by this run.
EXTRA_VARS+=(-e "provision_hosts_file=${INVENTORY}")

echo "mode:      ${MODE}"
echo "inventory: ${INVENTORY}"
echo "playbook:  ${PLAYBOOK}"
echo "ssh key:   ${ANSIBLE_PRIVATE_KEY_FILE:-<(none — password/agent auth)>}"
echo "workspace: ${CLUSTER_WORKSPACE_ROOT}"
if [[ -n "${EXTRA_VARS_FILE:-}" ]]; then
  echo "extra:     @${EXTRA_VARS_FILE}"
fi

exec ansible-playbook \
  -i "${INVENTORY}" \
  "${PLAYBOOK}" \
  "${EXTRA_VARS[@]}" \
  "$@"
