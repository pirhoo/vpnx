"""VPN configuration repository."""

from pathlib import Path
from typing import Dict, List, Optional

from domain.services import VPNRepository
from domain.value_objects import VPNType


class FileVPNRepository(VPNRepository):
    """File-based VPN configuration repository.

    Supports two modes:
    1. Config-based: Explicit path mapping from VPN names to config files
    2. Directory-based (legacy): Scan directory for client-*.ovpn files
    """

    def __init__(
        self,
        certs_dir: Optional[Path] = None,
        config_paths: Optional[Dict[str, Path]] = None,
    ):
        """Initialize repository.

        Args:
            certs_dir: Base directory for VPN configs (legacy mode)
            config_paths: Mapping of VPN names to config file paths (new mode)
        """
        self.certs_dir = certs_dir
        self.config_paths = config_paths or {}

    def list_available(self) -> List[VPNType]:
        """List available VPN configurations."""
        # New mode: use explicit config paths
        if self.config_paths:
            return [VPNType(name) for name in self.config_paths.keys()]

        # Legacy mode: scan directory
        if not self.certs_dir or not self.certs_dir.exists():
            return []
        vpns = []
        for path in sorted(self.certs_dir.glob("client-*.ovpn")):
            name = path.stem.replace("client-", "")
            vpns.append(VPNType(name))
        return vpns

    def exists(self, vpn_type: VPNType) -> bool:
        """Check if VPN configuration exists."""
        return self.config_path(vpn_type).exists()

    def config_path(self, vpn_type: VPNType) -> Path:
        """Get path to VPN config file."""
        # New mode: use explicit config paths
        name_upper = vpn_type.name.upper()
        if name_upper in self.config_paths:
            return self.config_paths[name_upper]

        # Legacy mode: construct from directory
        if self.certs_dir:
            return self.certs_dir / vpn_type.config_filename

        raise ValueError(f"No config path for VPN: {vpn_type.name}")
