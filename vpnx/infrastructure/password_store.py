"""Password store using GPG directly."""

import subprocess
from pathlib import Path
from typing import Optional

from vpnx.domain.services import CredentialStore


class GPGPasswordStore(CredentialStore):
    """Password store using GPG encryption directly.

    Takes a base path and derives:
    - {base_path}.gpg - encrypted password file
    - {base_path}.gpg-id - GPG key ID file
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.password_file = Path(str(base_path) + ".gpg")
        self.gpg_id_file = Path(str(base_path) + ".gpg-id")

    def get_password(self, username: str) -> Optional[str]:
        """Get stored password (username is ignored - single password store)."""
        if not self.password_file.exists():
            return None

        try:
            result = subprocess.run(
                ["gpg", "--quiet", "--decrypt", str(self.password_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def is_initialized(self) -> bool:
        """Check if store is initialized with a GPG key."""
        return self.gpg_id_file.exists()

    def has_password(self) -> bool:
        """Check if a password is stored."""
        return self.password_file.exists()

    def initialize(self, gpg_id: str) -> bool:
        """Initialize the password store with a GPG key ID."""
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.gpg_id_file.write_text(gpg_id.strip() + "\n")
        return True

    def store_password(self, password: str) -> bool:
        """Store password encrypted with GPG."""
        if not self.is_initialized():
            return False

        gpg_id = self.gpg_id_file.read_text().strip()
        if not gpg_id:
            return False

        try:
            result = subprocess.run(
                [
                    "gpg",
                    "--quiet",
                    "--encrypt",
                    "--recipient",
                    gpg_id,
                    "--output",
                    str(self.password_file),
                ],
                input=password,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_gpg_id(self) -> Optional[str]:
        """Get the configured GPG key ID."""
        if not self.gpg_id_file.exists():
            return None
        return self.gpg_id_file.read_text().strip()


# Backward compatibility alias
PassPasswordStore = GPGPasswordStore
