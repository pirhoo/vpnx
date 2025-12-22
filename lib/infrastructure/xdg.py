"""XDG Base Directory Specification paths."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class XDGPaths:
    """XDG-compliant paths for the application."""

    config_home: Path  # ~/.config/vpnx
    data_home: Path  # ~/.local/share/vpnx
    cache_home: Path  # ~/.cache/vpnx

    APP_NAME = "vpnx"

    @classmethod
    def default(cls) -> "XDGPaths":
        """Create XDG paths from environment or defaults."""
        home = Path.home()

        config_base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        data_base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))

        return cls(
            config_home=config_base / cls.APP_NAME,
            data_home=data_base / cls.APP_NAME,
            cache_home=cache_base / cls.APP_NAME,
        )

    @property
    def config_file(self) -> Path:
        """Path to the main configuration file."""
        return self.config_home / "config.yaml"

    @property
    def credentials_path(self) -> Path:
        """Path to the encrypted credentials file."""
        return self.data_home / "credentials"

    @property
    def logs_dir(self) -> Path:
        """Path to the logs directory."""
        return self.cache_home / "logs"

    @property
    def up_script(self) -> Path:
        """Path to the default up script."""
        return self.config_home / "up.sh"

    def ensure_dirs(self) -> None:
        """Create all XDG directories if they don't exist."""
        self.config_home.mkdir(parents=True, exist_ok=True)
        self.data_home.mkdir(parents=True, exist_ok=True)
        self.cache_home.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
