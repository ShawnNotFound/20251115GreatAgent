"""
Runtime patches applied before Langflow boots.

Langflow secures the generated `.langflow_config` secret key by resetting the
file ACL on Windows. In this environment that ACL ends up denying our own user,
which prevents Langflow from starting because it can no longer rewrite the
secret key on subsequent launches.  Python automatically imports this module
before running any user code, so we hook Langflow's helper to skip the ACL
mutation while still creating the secret file when needed.
"""

from __future__ import annotations

import os
from pathlib import Path

if os.name == "nt":
    try:
        from langflow.services.settings import utils as _settings_utils
    except Exception:
        # Langflow is not available yet (e.g. when running dependency installs).
        # Nothing to patch in that case.
        pass
    else:
        def _noop_set_secure_permissions(_: Path) -> None:
            """Intentional no-op to keep the secret key file readable."""

        def _safe_write_secret_to_file(path: Path | str, value: str) -> None:
            """Original helper without the permission tightening."""
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8")

        _settings_utils.set_secure_permissions = _noop_set_secure_permissions  # type: ignore[attr-defined]
        _settings_utils.write_secret_to_file = _safe_write_secret_to_file  # type: ignore[attr-defined]
