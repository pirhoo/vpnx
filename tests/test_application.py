#!/usr/bin/env python3
"""Tests for application layer."""

import unittest
from unittest.mock import Mock


from vpnx.application.commands import (
    ConnectAllCommand,
    ConnectCommand,
    ListCommand,
    SetupCommand,
)
from vpnx.application.handlers import ListHandler
from vpnx.domain.value_objects import VPNType


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


if __name__ == "__main__":
    unittest.main()
