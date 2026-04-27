#!/usr/bin/env python3
"""Tests for application layer."""

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


from vpnx.application.commands import (
    ConnectAllCommand,
    ConnectCommand,
    DownCommand,
    ListCommand,
    SetupCommand,
)
from vpnx.application.handlers import DownHandler, ListHandler
from vpnx.domain.value_objects import VPNType
from vpnx.infrastructure.app_config import AppConfig, VPNConfig
from vpnx.infrastructure.process import CommandResult


class TestCommands(unittest.TestCase):
    """Tests for command objects."""

    def test_setup_command(self):
        cmd = SetupCommand()
        self.assertIsInstance(cmd, SetupCommand)

    def test_list_command(self):
        cmd = ListCommand()
        self.assertIsInstance(cmd, ListCommand)

    def test_connect_command(self):
        cmd = ConnectCommand(VPNType("PROD"))
        self.assertEqual(cmd.vpn_type.name, "PROD")

    def test_connect_all_command(self):
        cmd = ConnectAllCommand([VPNType("PROD"), VPNType("DEV")])
        self.assertIsInstance(cmd, ConnectAllCommand)
        self.assertEqual(len(cmd.vpn_types), 2)

    def test_down_command(self):
        cmd = DownCommand(VPNType("EXT"))
        self.assertEqual(cmd.vpn_type.name, "EXT")
        self.assertIsNone(cmd.dev)

    def test_down_command_with_dev(self):
        cmd = DownCommand(VPNType("EXT"), dev="utun5")
        self.assertEqual(cmd.dev, "utun5")


class TestListHandler(unittest.TestCase):
    """Tests for ListHandler."""

    def setUp(self):
        self.mock_service = Mock()
        self.mock_display = Mock()
        self.handler = ListHandler(self.mock_service, self.mock_display)

    def test_handle_lists_vpns(self):
        self.mock_service.list_vpns.return_value = [VPNType("PROD"), VPNType("DEV")]

        result = self.handler.handle(ListCommand())

        self.assertTrue(result)
        self.mock_display.print.assert_any_call("Available VPNs:")

    def test_handle_empty_list(self):
        self.mock_service.list_vpns.return_value = []

        result = self.handler.handle(ListCommand())

        self.assertTrue(result)
        self.mock_display.print.assert_called_with("Available VPNs:")


class TestDownHandler(unittest.TestCase):
    """Tests for DownHandler."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.script = Path(self.tmp.name) / "down.sh"
        self.script.write_text("#!/bin/sh\nexit 0\n")
        self.script.chmod(self.script.stat().st_mode | stat.S_IXUSR)

        self.runner = Mock()
        self.runner.run_script.return_value = CommandResult(0, "", "")
        self.display = Mock()

        self.vpn = VPNConfig(
            name="EXT",
            display_name="EXT",
            config_path=Path("/fake.ovpn"),
            needs_down_script=True,
            down_script=self.script,
        )
        self.config = AppConfig(
            username="u",
            credentials_path=Path("/tmp/creds"),
            up_script=None,
            down_script=None,
            vpns=[self.vpn],
        )
        self.handler = DownHandler(self.runner, self.display, self.config)

    def test_runs_per_vpn_down_script(self):
        result = self.handler.handle(DownCommand(VPNType("EXT")))

        self.assertTrue(result)
        self.runner.run_script.assert_called_once()
        args, kwargs = self.runner.run_script.call_args
        self.assertEqual(args[0], self.script)
        # default dev passed as positional and via env
        self.assertEqual(args[1], ["utun0"])
        self.assertEqual(kwargs["env"], {"dev": "utun0"})

    def test_uses_explicit_dev(self):
        self.handler.handle(DownCommand(VPNType("EXT"), dev="utun7"))
        args, kwargs = self.runner.run_script.call_args
        self.assertEqual(args[1], ["utun7"])
        self.assertEqual(kwargs["env"], {"dev": "utun7"})

    def test_falls_back_to_global_down_script(self):
        self.vpn.down_script = None
        self.config.down_script = self.script

        result = self.handler.handle(DownCommand(VPNType("EXT")))

        self.assertTrue(result)
        args, _ = self.runner.run_script.call_args
        self.assertEqual(args[0], self.script)

    def test_unknown_vpn(self):
        result = self.handler.handle(DownCommand(VPNType("NOPE")))
        self.assertFalse(result)
        self.display.error.assert_called_once()
        self.runner.run_script.assert_not_called()

    def test_no_script_configured(self):
        self.vpn.down_script = None
        self.config.down_script = None

        result = self.handler.handle(DownCommand(VPNType("EXT")))

        self.assertFalse(result)
        self.display.error.assert_called_once()
        self.runner.run_script.assert_not_called()

    def test_script_missing(self):
        self.vpn.down_script = Path(self.tmp.name) / "nope.sh"

        result = self.handler.handle(DownCommand(VPNType("EXT")))

        self.assertFalse(result)
        self.runner.run_script.assert_not_called()

    def test_script_not_executable(self):
        self.script.chmod(self.script.stat().st_mode & ~0o111)

        result = self.handler.handle(DownCommand(VPNType("EXT")))

        self.assertFalse(result)
        self.runner.run_script.assert_not_called()

    def test_script_failure_returns_false(self):
        self.runner.run_script.return_value = CommandResult(1, "", "boom")
        result = self.handler.handle(DownCommand(VPNType("EXT")))
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
