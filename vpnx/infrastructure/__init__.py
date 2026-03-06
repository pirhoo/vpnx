"""Infrastructure layer - external system integrations."""

from vpnx.infrastructure.app_config import AppConfig, VPNConfig
from vpnx.infrastructure.config_parser import ManagementConfig, OpenVPNConfigParser
from vpnx.infrastructure.log_reader import LogReader
from vpnx.infrastructure.management import (
    Bytecount,
    ManagementClient,
    ManagementEvent,
    ManagementState,
)
from vpnx.infrastructure.password_store import GPGPasswordStore, PassPasswordStore
from vpnx.infrastructure.port_allocator import PortAllocator
from vpnx.infrastructure.process import CommandRunner
from vpnx.infrastructure.vpn_process import OpenVPNProcessManager
from vpnx.infrastructure.vpn_repository import FileVPNRepository
from vpnx.infrastructure.xdg import XDGPaths

__all__ = [
    "CommandRunner",
    "FileVPNRepository",
    "OpenVPNProcessManager",
    "GPGPasswordStore",
    "PassPasswordStore",  # Backward compatibility alias
    "LogReader",
    "PortAllocator",
    "OpenVPNConfigParser",
    "ManagementConfig",
    "ManagementClient",
    "ManagementState",
    "ManagementEvent",
    "Bytecount",
    "AppConfig",
    "VPNConfig",
    "XDGPaths",
]
