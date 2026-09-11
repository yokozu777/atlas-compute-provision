"""Normalize git remote URLs for equality checks (TF state Mode B).

CI clones often use ``ssh://git@host/path.git`` while leaf vars use scp-like
``git@host:path.git``. Ansible ``regex_replace`` backrefs are fragile for this;
canonicalize in Python instead.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urlparse


def canonicalize_git_remote(url: Any) -> str:
    """Return a comparable form: ``git@host:path`` (no ``.git``, lowercased).

    Handles:

    - ``ssh://git@host/path.git`` / ``ssh://host:22/path``
    - ``git@host:path.git``
    - ``git+ssh://git@host/path``
    - ``https://host/path.git`` → ``https://host/path`` (host+path only)
    """
    raw = str(url or "").strip()
    if not raw:
        return ""

    raw = re.sub(r"\.git$", "", raw, flags=re.IGNORECASE)

    # scp-like: git@host:path  (already canonical shape)
    scp = re.match(r"^(?P<user>[^/@]+)@(?P<host>[^:]+):(?P<path>.+)$", raw)
    if scp and not raw.lower().startswith(("ssh://", "git+ssh://", "http://", "https://")):
        return f"{scp.group('user').lower()}@{scp.group('host').lower()}:{scp.group('path').lstrip('/')}"

    lowered = raw
    for prefix in ("git+ssh://", "ssh://"):
        if lowered.lower().startswith(prefix):
            # urlparse needs a scheme it understands; force ssh://
            parsed = urlparse("ssh://" + raw[len(prefix) :])
            host = (parsed.hostname or "").lower()
            if not host:
                break
            user = (parsed.username or "git").lower()
            path = unquote(parsed.path or "").lstrip("/")
            if path:
                return f"{user}@{host}:{path}"
            break

    if lowered.lower().startswith(("http://", "https://")):
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        path = unquote(parsed.path or "").lstrip("/")
        scheme = (parsed.scheme or "https").lower()
        if host and path:
            return f"{scheme}://{host}/{path}"
        if host:
            return f"{scheme}://{host}"

    return raw.lower()


def git_remotes_match(left: Any, right: Any) -> bool:
    """True when two remote URL strings refer to the same repo after canonicalize."""
    a = canonicalize_git_remote(left)
    b = canonicalize_git_remote(right)
    return bool(a) and a == b


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {
            "canonicalize_git_remote": canonicalize_git_remote,
            "git_remotes_match": git_remotes_match,
        }
