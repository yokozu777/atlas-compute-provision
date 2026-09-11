# Terraform state layout (ADR 001)

Durable Terraform state for `atlas-compute-provision` lives **outside** the
Ansible/runtime workspace. Scratch apply files under
`workspace/<cluster_id>/tf_workspace/` are **not** the source of truth.

Canonical decision: [adr/001-tfstate-repo-prefix.md](adr/001-tfstate-repo-prefix.md)
(variant A; **Phase 6** unified-inventory contract). Orchestrator summary:
sibling `atlas-clusterctl` → `docs/workspace.md` / `docs/local-labs.md`.

## In-repo path (unchanged)

On any state remote (inventory or dedicated), durable objects are always:

```text
tfstate/<cluster_id>/terraform.tfstate
```

Never bare `ci/infra/` at the repo root, never under `clusters/` or `workspace/`.

Example multi-purpose remote (atlas-inventory):

```text
atlas-inventory/
  clusters/ci/infra/           # leaf config
  tfstate/ci/infra/…           # durable TF state (SoT in git)
  workspace/…                  # usually untracked runtime
```

## Controller modes (do not confuse)

### A — Second clone (product default / standalone) — Phases 1–5

| Path | Role |
|------|------|
| `$ATLAS_CLUSTER_ROOT/tfstate-repo/` | Checkout/clone of `provision_tf_state_repo` |
| `…/tfstate-repo/tfstate/<cluster_id>/` | Durable objects on disk |
| `workspace/<cluster_id>/tf_workspace/` | Scratch for `terraform apply` only |

Full durable file:

```text
$ATLAS_CLUSTER_ROOT/tfstate-repo/tfstate/<cluster_id>/terraform.tfstate
```

### B — Unified inventory checkout (Phase 6 contract)

When `provision_tf_state_repo` **is** the same git remote as the live inventory
and `clusters.path` already points at that inventory’s `clusters/`:

| Path | Role |
|------|------|
| Inventory repo root (`.git` + `clusters/` + `tfstate/`) | **`provision_tf_state_local_dir`** — single working tree |
| `<inventory>/tfstate/<cluster_id>/` | Durable objects (same tree operators pull) |
| `workspace/<cluster_id>/tf_workspace/` | Scratch only |

**Intent:** no second clone under `atlas-clusterctl/tfstate-repo/` for that lab.
`07` reuses the existing git checkout when remotes match; `11` stages only
`tfstate/<cluster_id>/`.

**Today:** product defaults remain mode A (`…/tfstate-repo`) for standalone. Inventory
labs with `git_push: true` set mode B via
`provision_tf_state_local_dir: "{{ atlas_inventory_root }}"` (clusterctl inject,
Stages 2–3). **Roles (Stage 1):** when `local_dir` is already a matching git
checkout, `07` reuses it (ff-only); `11` stages only `tfstate/<cluster_id>/`.
**CI (Stage 5 / P1):** inventory checkout is that mode-B tree; prepare is ff-only
(fail if ahead/diverged); deploy uses full history (`INV_FETCH_MODE=full`).

## Variables (product defaults)

| Var | Default | Meaning |
|-----|---------|---------|
| `provision_tf_state_local_dir` | `{{ atlas_cluster_root }}/tfstate-repo` | Root of state checkout (mode A). Mode B: inventory repo root |
| `provision_tf_state_repo_prefix` | `tfstate` | In-repo prefix (single segment, no `/`) |
| `provision_tf_state_cluster_path` | `tfstate/{{ cluster_id }}` | Relative path for mkdir / `git add` |
| `provision_tf_state_repo_dir` | `{{ local_dir }}/{{ cluster_path }}` | Directory holding state files |
| `provision_tf_state_repo_file` | `…/terraform.tfstate` | Durable blob |
| `provision_tf_workspace_dir` | `{{ cluster_workspace_root }}/tf_workspace` | Scratch only |
| `provision_tf_state_repo` / `_branch` / `_git_push` | leaf / defaults | Remote URL + opt-in push |
| `provision_tf_state_git_discard_local` | `false` | Opt-in: discard dirty files **under `tfstate/` only** (CI) |

Leaf overlays set repo URL, branch, `git_push`, and git identity. Inventory labs
with `git_push: true` set `provision_tf_state_local_dir: "{{ atlas_inventory_root }}"`
(see inventory leaf catalogs / `tfstate/README.md`). Do **not** invent a second
prefix (wrong combo yields `tfstate/tfstate/…`).

`provision_tf_state_git_discard_local=true` may discard dirty **working-tree**
tracked/untracked files under `tfstate/` before ff-only sync. It **never** runs
whole-repo `reset --hard`, **never** drops unpushed commits, and **never** touches
`clusters/`. Dirty paths outside `tfstate/` always fail the role (clear error).
CI prepare mirrors the same working-tree discard; unpushed commits on the runner
fail prepare instead of silent tip reset.

## Modes

| `provision_tf_state_git_push` | Behaviour |
|-------------------------------|-----------|
| `false` (default) | Ensure `…/tfstate/<id>/` under `local_dir`; no clone/push |
| `true` | Sync `provision_tf_state_repo` into `local_dir` (clone **or** reuse existing matching git); commit `tfstate/<id>/` only |

Roles: `07_tf_state_pull` → apply → `11_tf_state_push`.

## Operator checklist

1. Prefer product defaults for path vars unless adopting Phase 6 unified mode.
2. Never point durable SoT at `workspace/…/tf_workspace/`.
3. On shared inventory remotes, durable blobs live under `tfstate/<cluster_id>/`
   (see inventory `tfstate/README.md`). Bare root `ci/infra/` is legacy.
4. **Do not edit** `$ATLAS_CLUSTER_ROOT/tfstate-repo/clusters/…` — that tree is a
   side effect of cloning inventory as the state remote (mode A). Edit leaf
   config under `clusters.path` only.
5. `./cluster workspace reset` deletes runtime workspace only — durable
   `tfstate/` / `tfstate-repo/…` remains.
6. Phase 5: defaults on provision remote `main`; multi-leaf pull smoke done.
7. Phase 6 Stages 1–5: roles reuse matching `local_dir`; inventory leaves use
   `atlas_inventory_root`; clusterctl narrow docker chown; operator migrate retires
   controller `tfstate-repo/` (ADR 001 Stage 4). CI (Stage 5 / P1): inventory
   checkout is mode-B `local_dir`; jobs never create `tfstate-repo/`; dirty outside
   `tfstate/` fails; working-tree dirt under `tfstate/` discarded; refresh
   ff-only (fail if unpushed/diverged); deploy `INV_FETCH_MODE=full` + shared
   `resource_group: atlas-clusterctl-inventory`.
