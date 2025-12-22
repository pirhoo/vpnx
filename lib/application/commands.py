"""Application commands - represent user intentions."""

from abc import ABC
from dataclasses import dataclass
from typing import List

from domain.value_objects import VPNType


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
