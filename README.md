# atlas-compute-provision

Ansible + Terraform playbooks to **build Proxmox cloud templates** and **provision VMs**
(with DNS/TSIG knobs) for platform stacks (k8s, jenkins, postgresql, redis, kafka, …).

**Canonical playbooks:**
- `playbooks/build_templates.yaml` — PVE cloud images → templates (`templates`)
- `playbooks/provision_nodes.yaml` — Terraform apply / recreate / destroy + SSH wait (`provision`)

**Runner:** `./run.sh`  
**Vars catalog:** `group_vars/all/atlas-compute-provision.yml`  
**Secrets overlay:** `group_vars/all/atlas-compute-provision.secrets.yml` (prefer Ansible Vault)  
**License:** Apache-2.0 (see `LICENSE`)

Validate for the provision path is **`00_validate_provision`** (there is no separate
`01_validate_vars` role in this repository).

```
  ./run.sh / ansible-playbook
              |
              +-- build_templates.yaml  -->  PVE cloud images --> qm templates
              |
              +-- provision_nodes.yaml  -->  Terraform VMs --> wait SSH
                                              |
                                              v
                                    inventory groups (by provision_stack)
                                    k8s | infra | jenkins | postgresql | redis | kafka | …
```

Standalone path: edit inventory + `group_vars/all/atlas-compute-provision.yml` → `./run.sh`.  
Orchestrated path: external orchestrator phases `templates` / `provision`.

## Compatibility

Controller (where Ansible/Terraform run):
- Linux with Ansible **2.14+**, Terraform, SSH client
- Optional: `community.general` (git config) when `provision_tf_state_git_push: true`
- Writable workspace under `./workspace/` (or `CLUSTER_WORKSPACE_*`)

Proxmox / guests:
- Reachable Proxmox API + SSH (`provision_pve_*`)
- Cloud-init capable clone templates listed in `provision_pve_templates`
- Inventory host keys are typically the VM **IP**; each host needs `hostname:` + `provision.*`

Inventory contract depends on **`provision_stack`** (maps in `group_vars/all/atlas-compute-provision.yml`):

| Stack (example) | Inventory groups | Map vars |
|-----------------|------------------|----------|
| `jenkins` (standalone default) | `jslave` | `provision_*_map_jenkins` |
| `gitlab_runner` | `gitlab_runners` | `provision_*_map_gitlab_runner` |
| `infra` | `infra_platform` | `provision_*_map_infra` |
| `k8s` | `k8s_lbs`, `k8s_masters`, `k8s_workers` | `provision_*_map_k8s` |
| `postgresql` | `pgsql_etcd_cluster`, `pgsql_cluster`, `pgsql_lbs` | `provision_*_map_postgresql` |
| `kafka` | `kafka_controllers`, `kafka_brokers` | `provision_*_map_kafka` |
| `mysql` / `redis` | see `stacks/` + examples | `provision_*_map_<stack>` |

Effective maps are resolved by `playbooks/group_vars/all/provision_stack_maps.yml`
(`provision_inventory_group_map` / `provision_tf_module_map`). Use `provision_stack: infra`
for infra-only leaves (separate from k8s).

### Renaming inventory groups

Unlike siblings with a single `*_hosts` targeting var, this repo targets via **map keys**.
To rename a group (example: `jslave` → `my_build_agents`), update **together**:

1. Inventory group name in `hosts` / `inventory.yml`
2. Keys of `provision_inventory_group_map_<stack>`
3. Optional `provision_wait_hosts` (and any orchestrator `--limit` lists)

Keep TF map **values** / module names stable unless you also change `stacks/<stack>/`.

Rename-smoke fixture:

```bash
INVENTORY=examples/rename_smoke/hosts.example.yml \
  EXTRA_VARS_FILE=examples/rename_smoke/maps.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

k8s validate smoke:

```bash
INVENTORY=examples/k8s/hosts.example.yml \
  EXTRA_VARS_FILE=examples/k8s/maps.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

OS bootstrap of guests (users, packages, CA) is **out of scope** here — this repo only
builds templates and creates VMs. Install workloads with the matching sibling playbooks
after SSH is up (`provision_wait_ssh`).

## Quickstart

### Prerequisites

- Ansible 2.14+ on the controller
- `ansible-galaxy collection install -r requirements.yml` (`community.general`, `ansible.posix`)
- Terraform available for `10_tf_apply` (and related TF tags)
- SSH access to Proxmox (`provision_pve_user` / password or key as configured)
- Proxmox API token (`provision_proxmox_token_*`) for Terraform
- DNS TSIG secret when RFC2136 / BIND updates are required by your layout
- Replace every `CHANGEME` in `group_vars/all/atlas-compute-provision.yml` (prefer Ansible Vault / `EXTRA_VARS_FILE`)
- SSH **public** key file at `provision_ssh_public_key_file` (example: `examples/ssh/localuser.pub`)
- `provision.clone` on each inventory host is the **PVE template name** (e.g. `ubuntu-base`).
  Terraform clones by that name. `provision_pve_templates` is **optional** on provision
  (soft allowlist of names). For **templates** build each catalog entry needs
  `id` + `image_url` (`image_file` = URL basename) — factory leaf / `./run.sh templates`.

### Clone

```bash
git clone <atlas-compute-provision-url>
cd atlas-compute-provision
ansible-galaxy collection install -r requirements.yml
```

### Inventory

```bash
cp inventory-example.yml inventory.yml
vi inventory.yml
```

Default catalog stack is **jenkins** (`jslave`). For other stacks / rename, see
`examples/{postgresql,kafka,k8s,rename_smoke}/`:

```bash
INVENTORY=examples/postgresql/hosts.example.yml \
  EXTRA_VARS_FILE=examples/postgresql/provision.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

### Variables

**SoT:** `group_vars/all/atlas-compute-provision.yml` — **REQUIRED** (workspace, stack/maps, PVE/DNS/TF, templates)
and **OPTIONAL** (build_* , wait-SSH, identity).  
Deep knobs live in `roles/*/defaults/` and `stacks/<name>/` when not listed in `group_vars/all/atlas-compute-provision.yml`.

Standalone-safe defaults:

```yaml
provision_stack: jenkins
provision_mode: apply          # apply | recreate | destroy
provision_tf_state_git_push: false   # local TF state only
provision_enforce_live_secrets: false  # true before live PVE/DNS apply
```

Minimum secrets to replace (or supply via vault overlay) **before** a live run —
and set `provision_enforce_live_secrets: true` so validate rejects leftover `CHANGEME`:

```yaml
provision_enforce_live_secrets: true
provision_pve_ssh_password: "CHANGEME"
provision_proxmox_token_id: "CHANGEME"
provision_proxmox_token_secret: "CHANGEME"
provision_dns_key_secret: "CHANGEME"
provision_vm_cipassword: "CHANGEME"
# Optional: provision_dns_tf_manage_a_records: true  # Terraform apex A after VM create
```

```bash
cp examples/secrets.example.yml ~/compute-provision-secrets.yml
# edit, optionally: ansible-vault encrypt ~/compute-provision-secrets.yml
EXTRA_VARS_FILE=~/compute-provision-secrets.yml ./run.sh provision
```

Optional ad-hoc template overlay (without inventory group_vars): `-e @vars-build.yml`.
Prefer `./run.sh templates`, which loads `group_vars/all/atlas-compute-provision.yml`.

### Run

```bash
./run.sh provision --tags 00_validate_provision   # contract check (localhost)
./run.sh templates                                # build PVE templates (needs live PVE)
./run.sh provision                                # TF provision + SSH wait (needs PVE/DNS)
./run.sh provision --tags 08_generate_tf_vars
./run.sh --check -v                               # forwarded to ansible-playbook
```

`00_ensure_workspace` runs on localhost when selected (`tags: 00_ensure_workspace`); orchestrator phases invoke it first explicitly.

Mode / playbook selection:

```bash
./run.sh                 # provision_nodes.yaml (default)
./run.sh provision …
./run.sh templates …
PLAYBOOK=playbooks/build_templates.yaml ./run.sh --tags 01_prepare_system
```

Or manually:

```bash
ansible-playbook -i inventory.yml playbooks/provision_nodes.yaml
ansible-playbook -i inventory.yml playbooks/build_templates.yaml
```

### `./run.sh` environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `INVENTORY` | `inventory.yml` or `inventory-example.yml` | Inventory path (absolutized; also sets `provision_hosts_file`) |
| First arg / mode | `provision` | `provision` or `templates` |
| `PLAYBOOK` | derived from mode | Override playbook path |
| `EXTRA_VARS_FILE` | — | Optional `-e @file` (vaulted secrets / stack overlay) |
| `SSH_KEY` / `ANSIBLE_PRIVATE_KEY_FILE` | `~/.ssh/id_ed25519` or `id_rsa` | SSH private key |
| `CLUSTER_WORKSPACE_ID` | `ci.example.com` | Workspace directory name under parent |
| `CLUSTER_WORKSPACE_PARENT` | `./workspace` (absolute under repo in `./run.sh`) | Parent directory for workspaces |
| `CLUSTER_WORKSPACE_ROOT` | `<parent>/<id>` | Full controller workspace path |
| `ANSIBLE_CONFIG` | `./ansible.cfg` | Ansible config |

`./run.sh` always loads `@group_vars/all/atlas-compute-provision.yml` so inventory under `examples/` still gets the catalog.
All extra CLI arguments are forwarded to `ansible-playbook`.

## Architecture (role order)

### Templates — `playbooks/build_templates.yaml`

1. **00_ensure_workspace** (localhost, `00_ensure_workspace`) — resolve `CLUSTER_WORKSPACE_*`, create dirs  
2. Assert build vars + register Proxmox host in runtime inventory  
3. **00_check_pve_templates** (Proxmox) — decide rebuild vs skip; persist build state  
4. **01_prepare_system** → **02_download_images** → **03_customize_images** (localhost)  
5. **04_upload_images** (localhost) → **05_create_pve_templates** (Proxmox)  
6. Clean build workspace / state when rebuild completed  

| Tag | Stage |
|-----|-------|
| `00_check_pve_templates` | Inspect existing PVE templates |
| `01_prepare_system` | Controller packages for image build |
| `02_download_images` | Fetch cloud images |
| `03_customize_images` | virt-customize (optional) |
| `04_upload_images` | Upload to PVE storage |
| `05_create_pve_templates` | `qm` template create |

### Provision — `playbooks/provision_nodes.yaml`

1. **00_ensure_workspace** (localhost, `00_ensure_workspace`)  
2. **00_validate_provision** — mode/stack/maps, inventory VM layout, SSH pubkey, workspace paths  
3. **06_configure_git** — only when `provision_tf_state_git_push: true`  
4. **07_tf_state_pull** → **08_generate_tf_vars**  
5. **09a_tf_destroy_dns** → **09_hypervisor_cleaner** (recreate/destroy paths)  
6. **10_tf_apply** → **`provision_wait_ssh`** → **11_tf_state_push**  

| Tag | Stage |
|-----|-------|
| `00_validate_provision` | Fail-fast contract (localhost) |
| `06_configure_git` | git user.name / user.email (git-push mode; host keys via GIT_SSH_COMMAND) |
| `07_tf_state_pull` | Pull remote TF state (optional) |
| `08_generate_tf_vars` | Render stack TF from inventory |
| `09a_tf_destroy_dns` | State rm legacy DNS / VM resources |
| `09_hypervisor_cleaner` | Proxmox `qm` destroy helper |
| `10_tf_apply` | Terraform apply |
| `provision_wait_ssh` | Wait root SSH on mapped groups |
| `11_tf_state_push` | Push / sync local TF state |

Typical flow:

```
  templates:
    ensure_workspace --> check_pve --> prepare --> download --> customize
         --> upload --> create_pve_templates

  provision:
    ensure_workspace --> validate_provision --> (git) --> tf_state_pull
         --> generate_tf --> (destroy/cleaner) --> tf_apply --> wait_ssh --> tf_state_push
```

## Terraform state layout

Durable state is **not** under `workspace/…/tf_workspace/` (scratch for apply).

| Layer | Path |
|-------|------|
| Controller checkout | `$ATLAS_CLUSTER_ROOT/tfstate-repo/tfstate/<cluster_id>/` |
| Inside state git remote | `tfstate/<cluster_id>/` |
| Scratch | `{{ cluster_workspace_root }}/tf_workspace/` |

Defaults: `provision_tf_state_local_dir` → `…/tfstate-repo`,
`provision_tf_state_repo_prefix` → `tfstate`,
`provision_tf_state_cluster_path` → `tfstate/{{ cluster_id }}`.

Leaf overlays set `provision_tf_state_repo` / `_git_push` / git identity; leave path
defaults alone unless you follow [docs/adr/001-tfstate-repo-prefix.md](docs/adr/001-tfstate-repo-prefix.md).
Operator guide: [docs/tfstate.md](docs/tfstate.md).

## Stacks and provision modes

| Knob | Standalone default | Meaning |
|------|--------------------|---------|
| `provision_stack` | `jenkins` | Selects `stacks/<name>/` TF layout |
| `provision_mode` | `apply` | `apply` / `recreate` / `destroy` |
| `provision_tf_state_git_push` | `false` | Opt-in remote git state; requires `gitea_host` + git identity (no CHANGEME) |
| `provision_enforce_live_secrets` | `false` | When `true`, reject CHANGEME for PVE/DNS/guest secrets |
| `provision_wait_hosts` | (unset) | Optional `group:group` override for SSH wait |

`provision_mode` behaviour (high level):

| Mode | Cleaner / destroy DNS | `10_tf_apply` | `provision_wait_ssh` |
|------|----------------------|---------------|----------------------|
| `apply` | skipped / no-op path | yes | yes |
| `recreate` | yes | yes | yes |
| `destroy` | yes | skipped | skipped |

Stack overlays (maps only): `examples/jenkins|infra|postgresql|kafka/provision.example.yml`,
plus `examples/k8s/` and `examples/rename_smoke/` for validate smokes.
TF module sources: `modules/proxmox_vm/`, shared providers `stacks/_shared/`.

## Greenfield checklist

1. Controller has Ansible (+ Terraform for apply) and can SSH to Proxmox.  
2. `inventory.yml` matches the chosen `provision_stack` groups; every host has `hostname:` + `provision.*` (`vmid`, `clone`, disks, …).  
3. `provision.clone` is a PVE template name that exists on the hypervisor (optional
   `provision_pve_templates` allowlist if you want early validation).  
4. `group_vars/all/atlas-compute-provision.yml` (or `EXTRA_VARS_FILE`) has real secrets — no leftover `CHANGEME` for a live run.  
5. Set `provision_enforce_live_secrets: true` before apply so validate rejects placeholders.  
6. `provision_ssh_public_key_file` points at a real public key.  
7. `./run.sh provision --tags 00_validate_provision` succeeds (try `examples/rename_smoke/`
   if you renamed inventory groups).  
8. (Optional) `./run.sh templates` builds/refreshes PVE templates.  
9. `./run.sh provision` applies VMs; `provision_wait_ssh` reaches guests.  
10. Hand off to OS-init / workload siblings; re-run provision only when inventory/TF drift requires it.

## Troubleshooting

### `00_validate_provision` fails on maps / stack

Define both `provision_inventory_group_map_<stack>` and `provision_tf_module_map_<stack>`.
Map **values** must equal TF module map **keys**. Ensure `stacks/<provision_stack>/` exists.

### Inventory group missing or empty / rename drift

Every key in the effective `provision_inventory_group_map` must exist in `provision_hosts_file`
(and contain hosts). Nested parents (`postgresql.children`, …) are flattened automatically.

If you renamed a group, update map keys and optional `provision_wait_hosts` in the same change
(see `examples/rename_smoke/`).

### `clone` / template catalog

`provision.clone` is the PVE template **name** passed to Terraform. It must exist on
the hypervisor. `provision_pve_templates` is optional on provision: when set, keys are
a soft allowlist of allowed clone names (id not required).

### Catalog: build vs provision

| Path | `provision_pve_templates` |
|------|---------------------------|
| `./run.sh templates` / `build_templates.yaml` | **Required** — each entry `id` + `image_url` |
| `./run.sh provision` / `00_validate_provision` | **Optional** — omit, or keys-only allowlist |

Use a dedicated golden-templates leaf in the org inventory (e.g. `lab/pve-templates`)
to build once. Stack leaves only need `hosts.provision.clone` matching those template
names. Reserved keys/VMIDs on the factory: `ubuntu-base`/`400100`,
`oracle-base`/`400101`, `debian-base`/`400102`.

See `examples/provision_catalog_clone_only.example.yml`.

### `00_validate_provision` fails on CHANGEME / live secrets

Contract validate allows placeholders when `provision_enforce_live_secrets: false` (standalone default).
Before a live apply set `provision_enforce_live_secrets: true` (see `examples/secrets.example.yml`)
and replace every `CHANGEME` for PVE SSH password, Proxmox token id/secret, DNS TSIG secret,
and guest `provision_vm_cipassword`.

### Git / `gitea_host` required

Only when `provision_tf_state_git_push: true`. Standalone default is `false` — durable
state under `<ATLAS_CLUSTER_ROOT>/tfstate-repo/tfstate/<cluster_id>/` when orchestrated
(ADR 001), or the same layout relative to `atlas_cluster_root` for bare `./run.sh`.
Enabling push also needs `git_user_*` and `provision_tf_state_repo`. Commits use
in-repo path `tfstate/<cluster_id>/` (never bare `ci/infra/` at the remote root).
See [docs/adr/001-tfstate-repo-prefix.md](docs/adr/001-tfstate-repo-prefix.md).

### Workspace path asserts fail

TF/build paths must live under `cluster_workspace_root`. Prefer `./run.sh` (exports absolute
`CLUSTER_WORKSPACE_*`). Role `00_ensure_workspace` re-resolves id/parent/root from env and
re-aligns controller/TF/build paths under the resolved root.

### `provision_hosts_file` not found

`./run.sh` sets `provision_hosts_file` to the absolutized `INVENTORY`. Do not point it at a
path relative to `playbooks/` unless you know the resolution rules.

### Hypervisor cleaner / TF apply fails

Check Proxmox API URL, token, TLS insecure flag, target node, and that VMIDs in inventory are
unique. For recreate/destroy, confirm cleaner SSH credentials (`provision_pve_ssh_password`).

### SSH wait times out

Confirm cloud-init user (`provision_vm_ciuser`, default `root`), network/gateway, and that
templates include qemu-guest-agent when you rely on it. Override groups with `provision_wait_hosts`.

### SSH host key changed after VM recreate

```bash
ssh-keygen -f ~/.ssh/known_hosts -R '192.168.1.50'
```

## Testing / CI

Local checks (same gates as GitHub Actions):

```bash
./tests/run_ci.sh
# or piecemeal:
python3 -m unittest discover -s tests -p 'test_*.py' -v
ansible-playbook --syntax-check -i inventory-example.yml playbooks/provision_nodes.yaml
ansible-playbook --syntax-check -i inventory-example.yml playbooks/build_templates.yaml
ansible-lint --profile min
./scripts/check-no-hardcoded-domains.sh
./run.sh provision --tags 00_validate_provision
```

CI workflow: `.github/workflows/ci.yml` (unit tests, syntax-check both playbooks, ansible-lint `min`, domain scan, publish hygiene).

Optional stricter lint locally: `ansible-lint --profile basic` (style findings; not a merge gate yet).

Layout / fingerprint suite: `tests/test_compute_provision_layout.py`.  
Stacks / TF contract suite: `tests/test_provision_stacks.py`.

**Live PVE / Terraform apply is not part of `./tests/run_ci.sh` / GHA.**

## Project structure

```
atlas-compute-provision/
├── docs/
│   ├── tfstate.md                       # operator guide: durable TF paths
│   └── adr/
│       ├── README.md
│       └── 001-tfstate-repo-prefix.md   # ADR 001: durable TF path (Phase 2 docs)
├── playbooks/
│   ├── build_templates.yaml
│   ├── provision_nodes.yaml
│   └── group_vars/all/provision_stack_maps.yml
├── run.sh
├── ansible.cfg
├── requirements.yml
├── requirements-dev.txt
├── vars-build.yml              # optional -e overlay for templates
├── inventory-example.yml
├── group_vars/
│   └── all/
│       └── atlas-compute-provision.yml
├── examples/
│   ├── secrets.example.yml
│   ├── ssh/localuser.pub
│   ├── jenkins/
│   ├── postgresql/
│   ├── kafka/
│   ├── k8s/
│   ├── rename_smoke/
│   └── internal/               # site-coupled samples (not product path)
├── host_vars/
│   └── example.yml
├── roles/
│   ├── 00_ensure_workspace/
│   ├── 00_validate_provision/
│   ├── 00_check_pve_templates/
│   ├── 01_prepare_system/ … 05_create_pve_templates/
│   ├── 06_configure_git/ … 11_tf_state_push/
│   └── 09a_tf_destroy_dns/
├── stacks/
│   ├── _shared/
│   ├── k8s/ infra/ jenkins/ postgresql/ mysql/ redis/ kafka/
├── modules/
│   └── proxmox_vm/
├── scripts/
│   └── check-no-hardcoded-domains.sh
├── tests/
│   ├── run_ci.sh
│   ├── test_compute_provision_layout.py
│   └── test_provision_stacks.py
├── .github/workflows/ci.yml
├── .ansible-lint
├── LICENSE
└── SECURITY.md
```

## Integrations

External orchestrators can call the same playbooks with their own inventory and group/host vars.
Set `provision_stack`, matching maps, `provision_hosts_file`, PVE/DNS/TF secrets, and workspace
knobs from `group_vars/all/atlas-compute-provision.yml`.

Suggested tag sequences:

- Templates: `00_check_pve_templates` → download/customize → upload → `05_create_pve_templates`
- Provision: `00_validate_provision` → generate TF → apply → `provision_wait_ssh`

Org-specific lab overlays (domains, API tokens, TSIG, remote TF state git) belong in the
orchestrator inventory — not in this repository’s defaults. Site-coupled Jenkins pipeline
sample: `examples/internal/` (not the standalone product path).

## Security

See [`SECURITY.md`](SECURITY.md) for reporting, secret-handling, fingerprint guards, and the
pre-publish git history note. Do not commit real credentials, vault files, terraform state, or
live inventories (`inventory.yml` and local workspace paths are gitignored). Licensed under
[Apache-2.0](LICENSE).

## Contributing

1. Keep `playbooks/build_templates.yaml` and `playbooks/provision_nodes.yaml` as the supported entries.  
2. Document new operator-facing variables in `group_vars/all/atlas-compute-provision.yml` and role/stack defaults.  
3. Extend `tests/test_compute_provision_layout.py` / `tests/test_provision_stacks.py` for contract changes.  
4. Keep `./tests/run_ci.sh` green before opening a PR.  
5. Update this README when tags, stacks, modes, or inventory contracts change.  
6. Keep product sources free of org lab hostnames and non-English operator-facing copy.

## Support

Open an issue in the repository for bugs and questions.
