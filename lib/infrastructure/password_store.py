"""Password store integration (pass)."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from domain.services import CredentialStore


class PassPasswordStore(CredentialStore):
    """Password store using 'pass' (password-store)."""

    def __init__(self, store_dir: Path):
        self.store_dir = store_dir

    def _env(self) -> dict:
        """Get environment with PASSWORD_STORE_DIR set."""
        return {**os.environ, "PASSWORD_STORE_DIR": str(self.store_dir)}

    def get_password(self, username: str) -> Optional[str]:
        """Get password for username."""
        try:
            result = subprocess.run(
                ["pass", "show", username],
                capture_output=True,
                text=True,
                env=self._env(),
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def is_initialized(self) -> bool:
        """Check if store is initialized."""
        return self.store_dir.is_dir() and (self.store_dir / ".gpg-id").exists()

    def initialize(self, gpg_id: str) -> bool:
        """Initialize the password store."""
        result = subprocess.run(["pass", "init", gpg_id], env=self._env())
        return result.returncode == 0

    def store_password(self, username: str) -> bool:
        """Store password interactively."""
        result = subprocess.run(["pass", "insert", username], env=self._env())
        return result.returncode == 0
