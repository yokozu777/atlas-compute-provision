# ADR 001 — TF state under `tfstate/<cluster_id>/` inside the state repo (variant A)

- **Status:** Accepted (Phase 5 complete; Phase 6 Stages 1–5)
- **Date:** 2026-07-28 (Phase 6 contract: 2026-08-03; Stages 1–5: 2026-08-03)
- **Deciders:** atlas-compute-provision + atlas-clusterctl maintainers
- **Related:** [README.md](../../README.md), [tfstate.md](../tfstate.md);
  orchestrator `atlas-clusterctl` → `docs/workspace.md` / `docs/stacks/compute-provision.md` /
  `docs/local-labs.md`;
  roles `07_tf_state_pull` / `11_tf_state_push` / `00_validate_provision`
- **Phases:** 0–5 (in-repo path variant A) **done**; **Phase 6** Stages 1–5
  **landed** (unified inventory `local_dir` + CI harden P1)

## Context

Durable Terraform state must not live in `workspace/<cluster_id>/tf_workspace/`
(scratch for `terraform apply`). Orchestrator docs describe a third sibling tree
for durable state.

**Pre-Phase 1 defaults (historical):**

| Var | Default | Effect |
|-----|---------|--------|
| `provision_tf_state_local_dir` | `$ATLAS_CLUSTER_ROOT/tfstate` | local durable root |
| `provision_tf_state_cluster_path` | `{{ cluster_id }}` e.g. `ci/infra` | relative path inside local dir |
| Full local path | `…/tfstate/ci/infra/terraform.tfstate` | OK for local-only |

When `provision_tf_state_git_push: true`, `07_tf_state_pull` **cloned**
`provision_tf_state_repo` into `provision_tf_state_local_dir`. Lab leaves often
set that repo to **atlas-inventory**. Relative path stayed bare `{{ cluster_id }}`,
so git commits landed at inventory **repo root**:

```text
atlas-inventory/
  clusters/ci/infra/     # leaf config — correct
  ci/infra/              # TF state — pollutes root (undesired)
  workspace/…            # runtime (usually untracked)
```

`00_validate_provision` historically asserted `provision_tf_state_cluster_path == cluster_id`
while its fail_msg already hinted at `tfstate/ci/redis/` — contract drift (fixed in Phase 1).

### Problem

1. Inventory (or any multi-purpose state repo) root fills with `ci/`, `dev/`, …
2. `local_dir` name `tfstate` is overloaded: both “logical sibling” and “git clone root”
3. Scratch (`tf_workspace`) vs durable path is easy to confuse for operators

## Decision (variant A)

**Separate the git checkout root from the in-repo durable prefix.**

Always store durable objects at:

```text
<provision_tf_state_local_dir>/tfstate/<cluster_id>/terraform.tfstate
```

In git (when push is enabled), the committed path is always:

```text
tfstate/<cluster_id>/
```

never bare `<cluster_id>/` at the state-repo root, and never under `clusters/` or
`workspace/`.

### Chosen layout

```text
$ATLAS_CLUSTER_ROOT/
  workspace/<cluster_id>/          # runtime (orchestrator)
    tf_workspace/                  # scratch apply workdir ONLY
  tfstate-repo/                    # checkout/clone of provision_tf_state_repo
    tfstate/
      ci/infra/
        terraform.tfstate
        .terraform.lock.hcl        # optional
      dev/mxhash/
        …
```

When the remote is atlas-inventory, a `git pull` on the operator’s inventory
checkout shows the same **in-repo** prefix (root stays tidy):

```text
atlas-inventory/
  clusters/…
  tfstate/ci/infra/terraform.tfstate
  # no ci/infra/ at repo root
```

`tfstate-repo/` under `$ATLAS_CLUSTER_ROOT` may be a full clone of inventory
(includes `clusters/` etc.); that is an implementation detail of using inventory
as the state remote. Operators still edit leaf config under `clusters.path`, not
inside `tfstate-repo/clusters/`.

### Variable contract (Phase 1 — implemented)

| Var | Default | Meaning |
|-----|---------|---------|
| `provision_tf_state_local_dir` | `{{ atlas_cluster_root }}/tfstate-repo` | Root of state checkout (git clone when push) or plain dir when local-only |
| `provision_tf_state_repo_prefix` | `tfstate` | **New.** In-repo durable prefix (single path segment; no slash) |
| `provision_tf_state_cluster_path` | `{{ provision_tf_state_repo_prefix }}/{{ cluster_id }}` | Relative path inside `local_dir` / git add path |
| `provision_tf_state_repo_dir` | `{{ local_dir }}/{{ cluster_path }}` | Directory holding state files |
| `provision_tf_state_repo_file` | `{{ repo_dir }}/terraform.tfstate` | Durable state blob |
| `provision_tf_workspace_dir` | `{{ cluster_workspace_root }}/tf_workspace` | **Unchanged** — scratch only |
| `provision_tf_state_repo` / `_branch` / `_git_push` | leaf / defaults | Unchanged semantics |

Derived identity rule (validate):

```text
provision_tf_state_cluster_path == provision_tf_state_repo_prefix ~ '/' ~ cluster_id
```

Forbidden relative paths:

- `^clusters/`
- `^workspace/`
- bare `{{ cluster_id }}` without the prefix (after Phase 1 cutover)
- `provision_tf_state_repo_prefix` empty or containing `/`

### Modes

| Mode | `git_push` | `local_dir` behaviour | Objects on disk |
|------|------------|----------------------|-----------------|
| Local-only | `false` | Ensure directory (not necessarily a git repo) | `…/tfstate-repo/tfstate/<id>/` |
| Git-backed | `true` | Clone/pull `provision_tf_state_repo` into `local_dir` | Same relative `tfstate/<id>/` inside clone; commit + push that path |

Dedicated state-only remotes use the **same** in-repo prefix (`tfstate/<id>/`) so
inventory and dedicated repos share one layout language.

### Rejected alternatives

| Option | Why rejected |
|--------|----------------|
| **B** — set `local_dir` to the live inventory checkout + `cluster_path=tfstate/<id>` | **Softened in Phase 6.** Naive coupling (force whole-tree reset, `git add .`) remains rejected. Constrained reuse of the operator/CI inventory checkout is **accepted** under Phase 6 rules below. |
| Durable state in `workspace/…/tf_workspace/` | Scratch is reset/deleted by `workspace reset`; must not be SoT |
| Keep bare `{{ cluster_id }}` in git | Pollutes multi-purpose repo roots (current pain) |
| `local_dir=…/tfstate` **and** `cluster_path=tfstate/<id>` | Double prefix `…/tfstate/tfstate/<id>/` — confusing |
| Force state under `clusters/<id>/` | Forbidden already; mixes config and state lifecycle |

## Consequences

### Positive

- Inventory (or any shared remote) root no longer accumulates env folders for state
- In-repo path matches the documented durable name `tfstate/…`
- Clear split: `tfstate-repo/` (checkout) vs `tf_workspace/` (scratch) vs `clusters/` (config)

### Negative / work

- Phase 1 renamed default `local_dir` (`tfstate` → `tfstate-repo`) — existing lab clones need migration (Phase 3)
- Validate now requires `cluster_path == prefix/cluster_id`
- One-time `git mv ci/infra tfstate/ci/infra` (and peers) on remotes that already pushed bare paths

### Non-goals (this ADR)

- Remote HTTP/S3 Terraform backends
- Storing state inside `workspace/`
- Changing `cluster_id` shape (`env/name`)
- Auto-deleting legacy bare paths without an explicit migrate step (Phase 3)

## Phase 1 acceptance criteria (implementation gate)

1. Defaults match the variable table above (both `roles/00_ensure_workspace/defaults` and
   `playbooks/group_vars/all/provision_defaults.yml`).
2. `07` / `11` create, copy, `git add` using `provision_tf_state_cluster_path` with prefix.
3. `00_validate_provision` enforces prefix rule; forbids `clusters/` / `workspace/` / bare id.
4. Layout/unit tests updated; no Cyrillic in product sources.
5. README + orchestrator `docs/workspace.md` describe `tfstate-repo/` + in-repo `tfstate/<id>/`.
6. **No** double prefix; **no** durable writes to `tf_workspace/` beyond scratch sync.

## Phase 2 acceptance criteria (docs gate)

1. Sibling operator guide `docs/tfstate.md` exists and states controller vs in-repo paths.
2. README has a **Terraform state layout** section linking ADR + `tfstate.md`.
3. Orchestrator `docs/workspace.md` / `docs/stacks/compute-provision.md` match live defaults
   (`tfstate-repo` + `tfstate/<cluster_id>/`).
4. Catalog / secrets examples tell leaves to set repo/push only (not path overrides).
5. Layout test asserts Phase 2 status + guide presence.

## Phase 4 acceptance criteria (operator / live pull)

1. Inventory `.gitignore` keeps `tfstate/` tracked; ignores `/workspace/` only.
2. Leaf overlays do not override `local_dir` / `cluster_path` / `repo_prefix`.
3. Bare root `ci/` / `dev/` state trees remain absent.
4. Live `00_ensure_workspace` + `07_tf_state_pull` for `ci/infra` resolves:
   - `provision_tf_state_local_dir` → `$ATLAS_CLUSTER_ROOT/tfstate-repo`
   - `provision_tf_state_cluster_path` → `tfstate/ci/infra`
   - existing `terraform.tfstate` (no empty re-init)
5. Product defaults with ADR 001 must be present in the playbook checkout used
   for the pull (publish sibling `atlas-compute-provision` before relying on
   `source: git` + `sync: always`).

## Phase 4 (done for ci/infra lab)

Verified 2026-07-28 on controller:

| Check | Result |
|-------|--------|
| Inventory tracks `tfstate/ci/infra`, `tfstate/dev/mxhash` | yes |
| `.gitignore` documents tracked `tfstate/` | yes |
| Leaf path overrides | none |
| `07_tf_state_pull` (`ci/infra`) | ok — skipped empty init |
| Durable path | `…/tfstate-repo/tfstate/ci/infra/terraform.tfstate` |
| Serial / resources | `2` / `1` (unchanged) |

Note: until ADR 001 is on `atlas-compute-provision` remote `main`, use a local
sibling mount (or rsync into `workspace/…/repos/`) before `repos sync`, otherwise
git sync restores pre-ADR defaults.

## Phase 3 acceptance criteria (migration gate)

1. State remote has `tfstate/<cluster_id>/terraform.tfstate` for migrated leaves.
2. Bare root `ci/` / `dev/` state trees are gone from that remote.
3. Controller uses `$ATLAS_CLUSTER_ROOT/tfstate-repo/` (legacy `…/tfstate/` clone retired).
4. Serial/resource counts preserved across `git mv` (no empty re-init).
5. ADR status documents Phase 3 complete for the migrated remote.

## Phase 3 migration (done for atlas-inventory lab remote)

Remote layout after migrate:

```bash
git mv ci/infra tfstate/ci/infra
git mv dev/mxhash tfstate/dev/mxhash
# commit + push
# replace obsolete $ATLAS_CLUSTER_ROOT/tfstate clone; next 07 uses tfstate-repo
```

Confirm `terraform plan` after `07_tf_state_pull` sees existing resources (same lineage).

Other remotes that still have bare `<cluster_id>/` should apply the same `git mv`.

## Phase 5 acceptance criteria (publish + multi-leaf smoke)

1. ADR 001 product defaults are on `atlas-compute-provision` remote `main`
   (no rsync/sibling bypass required for `source: git` + `sync: always`).
2. Normal `./cluster repos sync` + `./cluster run --phases provision
   --tags 00_ensure_workspace,07_tf_state_pull` for at least two leaves
   (`ci/infra`, `dev/mxhash`) resolves:
   - `local_dir` → `$ATLAS_CLUSTER_ROOT/tfstate-repo`
   - `cluster_path` → `tfstate/<cluster_id>`
   - existing durable state (no empty re-init)
3. Serial / resource counts preserved vs Phase 3 migrate baselines.
4. Optional: `terraform plan -refresh=false` against scratch + durable state
   shows **0 to add / 0 to destroy** (in-place drift only is acceptable).
5. Layout/unit tests assert Phase 5 status; ADR index updated.

## Phase 5 (done)

Verified 2026-07-28 after publish `b2573d5` on provision remote `main`:

| Check | Result |
|-------|--------|
| `repos sync` uses published defaults | yes (`tfstate-repo` + `repo_prefix: tfstate`) |
| `07_tf_state_pull` `ci/infra` (normal clusterctl path) | ok — serial `2`, resources `1` |
| `07_tf_state_pull` `dev/mxhash` | ok — serial `34`, resources `6` |
| Durable paths | `…/tfstate-repo/tfstate/{ci/infra,dev/mxhash}/` |
| `terraform plan -refresh=false` (`ci/infra`) | `Plan: 0 to add, 1 to change, 0 to destroy` (startup_shutdown drift only) |
| Empty re-init skipped | yes |

Apply smoke was intentionally **not** run (no VM recreate / no state serial bump).

## Phase 6 — Unified inventory `local_dir` (contract)

**Status:** Contract accepted 2026-08-03. **Stages 1–5 landed** (roles, inventory
leaf `local_dir`, clusterctl inject + narrow chown, operator migrate smoke, CI
ff-only + full deploy fetch + inventory `resource_group`). Product default
`local_dir` remains `$ATLAS_CLUSTER_ROOT/tfstate-repo` for standalone; lab leaves
that push into inventory set `local_dir: "{{ atlas_inventory_root }}"`.

### Problem (operator)

Phases 1–5 fixed the **in-repo** path (`tfstate/<cluster_id>/`) but kept a **second
git working tree** on the controller:

```text
atlas-inventory/          # clusters.path — edit configs here
  clusters/…
  tfstate/…               # SoT after pull (same remote)
atlas-clusterctl/
  tfstate-repo/           # 07 clones the SAME remote again
    clusters/…            # confusing duplicate
    tfstate/…
```

Operators edit the wrong tree, leave dirty files under `tfstate-repo/clusters/…`,
and `07` fails with `Local modifications exist (force=no)`.

### Decision

Keep ADR 001 **in-repo** layout unchanged. For labs where
`provision_tf_state_repo` **is** the inventory remote and `clusters.path` already
points at that inventory’s `clusters/`:

1. **`provision_tf_state_local_dir`** SHOULD be the **inventory repository root**
   (directory that contains `.git/`, `clusters/`, and `tfstate/`) — the same
   checkout used for leaf config — **not** a second clone under
   `$ATLAS_CLUSTER_ROOT/tfstate-repo`.
2. Durable blobs remain at
   `<local_dir>/tfstate/<cluster_id>/terraform.tfstate`
   (= inventory `tfstate/<cluster_id>/` on disk and in git).
3. **`07_tf_state_pull`** MUST **reuse** an existing git checkout when
   `local_dir/.git` exists and `origin` (or configured remote) matches
   `provision_tf_state_repo` — fetch/ff-only (or equivalent); MUST NOT clone a
   parallel tree by default in that situation. Matching MUST treat equivalent
   SSH URL forms as equal (e.g. `ssh://git@host/path.git` vs
   `git@host:path.git`) via `canonicalize_git_remote` / `git_remotes_match`.
4. **`11_tf_state_push`** MUST stage **only**
   `provision_tf_state_cluster_path` (`tfstate/<cluster_id>/…`) — never
   `git add` of `clusters/` or unrelated paths.
5. Whole-repo `git reset --hard` / `force: yes` on inventory **MUST NOT** be the
   default. Optional opt-in may discard local changes **only under** `tfstate/`
   (CI), never under `clusters/` by default.
6. Standalone / dedicated state remotes keep today’s default:
   `local_dir={{ atlas_cluster_root }}/tfstate-repo`.

### How inventory root is identified (contract)

Not magic: leaf/group_vars set `provision_tf_state_local_dir` explicitly, **or**
controller/inventory derive it as the parent of `clusters.path` /
`ATLAS_CLUSTERS_ROOT` when that parent is a git checkout of
`provision_tf_state_repo`. Derivation rules are implementation detail; the
**observable** contract is one working tree for config + durable `tfstate/`.

### Non-goals (Phase 6 contract)

- Changing `provision_tf_state_repo_prefix` / forbidding `tfstate-repo` as a
  product default for standalone
- Separate dedicated `vms_state` remote (optional hardening later)
- Non-root docker executor / SSH key split

### Phase 6 acceptance criteria (docs / contract gate)

1. This section exists; ADR header status mentions Phase 6 contract.
2. `docs/tfstate.md` describes **two controller modes**: legacy second clone vs
   unified inventory root; in-repo path unchanged.
3. Orchestrator `docs/workspace.md` + `docs/local-labs.md` + `docs/execution.md`
   state mode B + narrow docker chown (`tfstate/` + `.git/` only).
4. Inventory leaves with `git_push: true` set
   `provision_tf_state_local_dir: "{{ atlas_inventory_root }}"`.
5. Layout test asserts Phase 6 contract needles; Phase 5 historical section remains.
6. **Stage 1 (roles):** `07` reuses matching `local_dir` git checkout (ff-only);
   `11` stages only `tfstate/<cluster_id>/`; dirty outside prefix fails;
   `provision_tf_state_git_discard_local` discards under prefix only.
7. **Stage 3 (clusterctl):** inject `atlas_inventory_root`; post-docker chown does
   **not** reclaim the whole inventory mount.
8. **Stage 4 (migrate):** inventory SoT verified; controller `tfstate-repo/`
   retired to `tfstate-repo.legacy.bak`; `07` smoke on ≥2 leaves uses inventory
   root without recreating mode-A clone.
9. **Stage 5 (CI):** runner inventory checkout = mode-B `local_dir`; jobs never
   create controller `tfstate-repo/`; dirty outside `tfstate/` fails with a clear
   message; dirty working tree under `tfstate/` uses CI discard; refresh is
   ff-only (fail if ahead/diverged); deploy uses `INV_FETCH_MODE=full` + shared
   inventory `resource_group`.

## Stage 4 — Operator migrate (done 2026-08-03)

Verified on controller lab:

| Check | Result |
|-------|--------|
| Inventory vs legacy serial (`ci/postgresql`) | inventory `352` > legacy `124` (same lineage) |
| Inventory vs legacy serial (`ci/redis`) | inventory `221` > legacy `32` |
| `mv tfstate-repo tfstate-repo.legacy.bak` | done |
| `07` `ci/postgresql` (Stage 1 roles + mode B) | ff-only reuse; serial `352` / resources `3`; no empty re-init |
| `07` `ci/redis` | ff-only reuse; serial `221` / resources `4` |
| Mode-A clone recreated? | no |
| Leaf `atlas_inventory_root` preserved through ff-only | yes |

**Operator checklist (other machines):**

```bash
# 1) Publish/merge Stages 1–3 (compute-provision roles + inventory leaves + clusterctl)
git -C atlas-inventory pull --ff-only
# 2) Confirm inventory tfstate serials are SoT (compare old tfstate-repo if unsure)
# 3) Retire second clone
mv atlas-clusterctl/tfstate-repo atlas-clusterctl/tfstate-repo.legacy.bak
# 4) Smoke pull (no apply required)
./cluster --cluster ci/postgresql --executor local run --phases provision \
  --tags 00_ensure_workspace,07_tf_state_pull
./cluster --cluster ci/redis --executor local run --phases provision \
  --tags 00_ensure_workspace,07_tf_state_pull
# 5) Confirm log: tf state local dir: <inventory-root>
#    and task "Fetch and fast-forward existing matching checkout"
# 6) After a real apply, 11 commits only tfstate/<cluster_id>/
```

Do **not** point operators at `tfstate-repo/` after migrate. Delete
`tfstate-repo.legacy.bak` once confident (optional).

## Stage 5 — CI (done 2026-08-03; P1 harden + P2 docs same day)

Orchestrator samples (`examples/internal/`):

| Check | Result |
|-------|--------|
| Inventory checkout = mode-B `local_dir` | `clusters.path` → `<INVENTORY_DIR>/clusters`; parent = `atlas_inventory_root` |
| Shared prepare helper | `examples/internal/ci/prepare_inventory_checkout.sh` |
| Refresh | `fetch` + named branch + `merge --ff-only` (never `-B FETCH_HEAD`) |
| Local ahead / diverged | fail (protect unpushed TF commits) |
| Dirty outside `tfstate/` | fail with clear msg (no whole-repo reset) |
| Dirty working tree under `tfstate/` | discard files only (not commits) |
| `INV_FETCH_MODE` | seed `shallow`; deploy `full` (unshallow/deepen as needed) |
| GitLab mutex | `resource_group: atlas-clusterctl-inventory` (seed + deploy) |
| Run inject | default `-e provision_tf_state_git_discard_local=true` (working tree only) |
| Opt-out | `TFSTATE_GIT_DISCARD_LOCAL=false` or EXTRA_VARS token |
| Controller `tfstate-repo/` | never created; leftover → NOTE only |

Wired in GitLab `gitlab-ci.jobs.yml` (seed + deploy) and Jenkins
`Jenkinsfile` / `Jenkinsfile.local` / `seed/Jenkinsfile`. Docs:
`docs/gitlab-ci.md`, `docs/jenkins.md`.

## Status of this document

Phases **0–5 complete** (decision, defaults, docs, inventory migrate, live pull,
publish + multi-leaf smoke). **Phase 6 contract accepted**; **Stages 1–5 landed**
(P1 CI harden: full fetch on deploy, inventory resource_group, ff-only refresh;
P2 docs: mode-B examples in orchestrator guides, ADR header clarity).
