"""Normalize provision_pve_templates entries.

Catalog shapes (operator surface):

Build / templates (image factory) — id + image_url required:

    provision_pve_templates:
      ubuntu-base:                     # key = PVE template name + hosts.provision.clone
        id: 400100
        image_url: https://…/ubuntu-26.04-minimal-cloudimg-amd64.img

Provision / clone — catalog optional. Terraform clones by template *name*
(hosts.provision.clone). When provision_pve_templates is set it is only an
allowlist of those names; id/image_url are not required on the provision path.

Derived at runtime (when resolving a catalog):

    name         → catalog key
    image_file   → basename(image_url) when URL set; else empty string
    template_key → catalog key (alias used by build check state)
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
    out = dict(entry)
    if image_url:
        out["image_url"] = image_url
    else:
        out.pop("image_url", None)
    out["template_key"] = key
    out["name"] = key
    out["image_file"] = _image_basename(image_url)
    # Legacy optional fields — ignore if present; key/url are SoT when URL set.
    out.pop("download_glob", None)
    return out


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
        }
