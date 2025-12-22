"""Application configuration loading and saving."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

if TYPE_CHECKING:
    from infrastructure.xdg import XDGPaths


@dataclass
class VPNConfig:
    """Configuration for a single VPN."""

    name: str
    display_name: str
    config_path: Path
    needs_up_script: bool = False
    needs_2fa: bool = True  # Most VPNs need 2FA
    up_script: Optional[Path] = None  # Per-VPN override

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        data = {
            "name": self.name,
            "display": self.display_name,
            "config_path": str(self.config_path),
            "needs_up_script": self.needs_up_script,
            "needs_2fa": self.needs_2fa,
        }
        if self.up_script:
            data["up_script"] = str(self.up_script)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "VPNConfig":
        """Create from dictionary."""
        return cls(
            name=data["name"].upper(),
            display_name=data.get("display", data["name"]),
            config_path=Path(data["config_path"]).expanduser(),
            needs_up_script=data.get("needs_up_script", False),
            needs_2fa=data.get("needs_2fa", True),
            up_script=Path(data["up_script"]).expanduser()
            if data.get("up_script")
            else None,
        )


@dataclass
class AppConfig:
    """Application configuration."""

    username: str
    credentials_dir: Path
    up_script: Optional[Path]
    vpns: List[VPNConfig] = field(default_factory=list)

    def get_vpn(self, name: str) -> Optional[VPNConfig]:
        """Get VPN config by name (case-insensitive)."""
        name_upper = name.upper()
        for vpn in self.vpns:
            if vpn.name.upper() == name_upper:
                return vpn
        return None

    def vpn_names(self) -> List[str]:
        """Get list of VPN names in order."""
        return [v.name for v in self.vpns]

    def add_vpn(self, vpn: VPNConfig) -> None:
        """Add a VPN configuration."""
        # Remove existing with same name
        self.vpns = [v for v in self.vpns if v.name.upper() != vpn.name.upper()]
        self.vpns.append(vpn)

    def remove_vpn(self, name: str) -> bool:
        """Remove a VPN by name. Returns True if found and removed."""
        name_upper = name.upper()
        original_len = len(self.vpns)
        self.vpns = [v for v in self.vpns if v.name.upper() != name_upper]
        return len(self.vpns) < original_len

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        data = {
            "username": self.username,
            "credentials_dir": str(self.credentials_dir),
            "vpns": [v.to_dict() for v in self.vpns],
        }
        if self.up_script:
            data["up_script"] = str(self.up_script)
        return data

    def save(self, path: Path) -> None:
        """Save config to YAML file."""
        if not YAML_AVAILABLE:
            raise RuntimeError(
                "PyYAML is required to save configuration. "
                "Install with: pip install pyyaml"
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.safe_dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        """Load config from YAML file."""
        if not YAML_AVAILABLE:
            raise RuntimeError(
                f"Config file found at {path} but PyYAML is not installed. "
                "Install with: pip install pyyaml"
            )

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty or invalid config file: {path}")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Create from dictionary."""
        vpns = [VPNConfig.from_dict(v) for v in data.get("vpns", [])]

        return cls(
            username=data.get("username", ""),
            credentials_dir=Path(data.get("credentials_dir", "")).expanduser(),
            up_script=Path(data["up_script"]).expanduser()
            if data.get("up_script")
            else None,
            vpns=vpns,
        )

    @classmethod
    def empty(cls, xdg: "XDGPaths") -> "AppConfig":
        """Create empty config with XDG defaults pre-filled."""
        return cls(
            username="",
            credentials_dir=xdg.credentials_dir,
            up_script=None,
            vpns=[],
        )

    def is_credentials_configured(self) -> bool:
        """Check if credentials/password store is configured."""
        gpg_id_file = self.credentials_dir / ".gpg-id"
        return gpg_id_file.exists()
