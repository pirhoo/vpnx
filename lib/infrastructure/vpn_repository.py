"""VPN configuration repository."""

from pathlib import Path
from typing import List

from domain.services import VPNRepository
from domain.value_objects import VPNType


class FileVPNRepository(VPNRepository):
    """File-based VPN configuration repository."""

    def __init__(self, certs_dir: Path):
        self.certs_dir = certs_dir

    def list_available(self) -> List[VPNType]:
        """List available VPN configurations."""
        if not self.certs_dir.exists():
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
        return self.certs_dir / vpn_type.config_filename
