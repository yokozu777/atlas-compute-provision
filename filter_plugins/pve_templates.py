"""Normalize provision_pve_templates entries.

Catalog shapes (operator surface):

Build / templates (image factory) — id + image_url required:

    provision_pve_templates:
      ubuntu-base:                     # key = PVE template name + hosts.provision.clone
        id: 400100
        image_url: https://…/ubuntu-26.04-minimal-cloudimg-amd64.img
        image_url_backup: https://…/same-file-on-a-mirror.img   # optional

Provision / clone — catalog optional. Terraform clones by template *name*
(hosts.provision.clone). When provision_pve_templates is set it is only an
allowlist of those names; id/image_url are not required on the provision path.

Derived at runtime (when resolving a catalog):

    name         → catalog key
    image_file   → basename(image_url) when URL set; else empty string
    template_key → catalog key (alias used by build check state)

image_url_backup is kept only when non-empty. The download role may replace
image_url and image_file with the URL that actually produced the file.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse


def _image_basename(image_url: str) -> str:
    raw = (image_url or "").strip()
    if not raw:
        return ""
    path = urlparse(raw).path
    name = unquote(path.rsplit("/", 1)[-1] if path else "")
    return name


def resolve_pve_template_entry(entry: Any, key: str) -> dict[str, Any]:
    """Merge derived name/image_file onto one catalog value (key = PVE name)."""
    if entry is None:
        entry = {}
    if not isinstance(entry, dict):
        raise TypeError(f"provision_pve_templates[{key!r}] must be a mapping, got {type(entry)!r}")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("provision_pve_templates keys must be non-empty strings (PVE template name)")

    image_url = str(entry.get("image_url", "") or "").strip()
    backup = str(entry.get("image_url_backup", "") or "").strip()
    out = dict(entry)
    if image_url:
        out["image_url"] = image_url
    else:
        out.pop("image_url", None)
    if backup:
        out["image_url_backup"] = backup
    else:
        out.pop("image_url_backup", None)
    out["template_key"] = key
    out["name"] = key
    out["image_file"] = _image_basename(image_url)
    # Legacy optional fields — ignore if present; key/url are SoT when URL set.
    out.pop("download_glob", None)
    return out


def apply_pve_download_results(templates: Any, chosen: Any) -> list[Any]:
    """Replace image_url and image_file with the URL that was actually saved."""
    if not isinstance(templates, list):
        raise TypeError(f"templates must be a list, got {type(templates)!r}")
    by_name: dict[str, dict[str, Any]] = {}
    if isinstance(chosen, list):
        for row in chosen:
            if isinstance(row, dict) and str(row.get("name") or "").strip():
                by_name[str(row["name"])] = row
    updated: list[Any] = []
    for entry in templates:
        if not isinstance(entry, dict):
            updated.append(entry)
            continue
        picked = by_name.get(str(entry.get("name") or ""))
        if not picked:
            updated.append(entry)
            continue
        merged = dict(entry)
        url = str(picked.get("image_url") or "").strip()
        image_file = str(picked.get("image_file") or "").strip() or _image_basename(url)
        if url:
            merged["image_url"] = url
            merged["image_file"] = image_file
        updated.append(merged)
    return updated


def resolve_pve_templates(templates: Any) -> dict[str, dict[str, Any]]:
    """Resolve a full provision_pve_templates mapping."""
    if templates is None:
        return {}
    if not isinstance(templates, dict):
        raise TypeError(f"provision_pve_templates must be a mapping, got {type(templates)!r}")
    return {str(key): resolve_pve_template_entry(value, str(key)) for key, value in templates.items()}


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "resolve_pve_template_entry": resolve_pve_template_entry,
            "resolve_pve_templates": resolve_pve_templates,
            "pve_template_image_basename": _image_basename,
            "apply_pve_download_results": apply_pve_download_results,
        }
