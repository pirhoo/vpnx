"""Application commands - represent user intentions."""

from abc import ABC
from dataclasses import dataclass
from typing import List, Optional

from vpnx.domain.value_objects import VPNType


class Command(ABC):
    """Base command interface."""

    pass


@dataclass
class SetupCommand(Command):
    """Setup credentials command."""

    pass


@dataclass
class ListCommand(Command):
    """List available VPNs command."""

    pass


@dataclass
class ConnectCommand(Command):
    """Connect to a single VPN command."""

    vpn_type: VPNType


@dataclass
class ConnectAllCommand(Command):
    """Connect to all configured VPNs in sequence."""

    vpn_types: List[VPNType]


@dataclass
class DownCommand(Command):
    """Manually run the configured down script for a VPN."""

    vpn_type: VPNType
    dev: Optional[str] = None
