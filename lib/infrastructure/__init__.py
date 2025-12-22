"""Infrastructure layer - external system integrations."""

from infrastructure.process import CommandRunner
from infrastructure.vpn_repository import FileVPNRepository
from infrastructure.vpn_process import OpenVPNProcessManager
from infrastructure.password_store import GPGPasswordStore, PassPasswordStore
from infrastructure.log_reader import LogReader
from infrastructure.port_allocator import PortAllocator
from infrastructure.config_parser import OpenVPNConfigParser, ManagementConfig
from infrastructure.management import (
    ManagementClient,
    ManagementState,
    ManagementEvent,
    Bytecount,
)
from infrastructure.app_config import AppConfig, VPNConfig
from infrastructure.xdg import XDGPaths

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
