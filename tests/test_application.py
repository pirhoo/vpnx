#!/usr/bin/env python3
"""Tests for application layer."""

import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from domain.value_objects import VPNType
from application.commands import (
    SetupCommand,
    ListCommand,
    ConnectCommand,
    ConnectBothCommand,
)
from application.handlers import ListHandler


class TestCommands(unittest.TestCase):
    """Tests for command objects."""

    def test_setup_command(self):
        cmd = SetupCommand()
        self.assertIsInstance(cmd, SetupCommand)

    def test_list_command(self):
        cmd = ListCommand()
        self.assertIsInstance(cmd, ListCommand)

    def test_connect_command(self):
        cmd = ConnectCommand(VPNType("EXT"))
        self.assertEqual(cmd.vpn_type.name, "EXT")

    def test_connect_both_command(self):
        cmd = ConnectBothCommand()
        self.assertIsInstance(cmd, ConnectBothCommand)


class TestListHandler(unittest.TestCase):
    """Tests for ListHandler."""

    def setUp(self):
        self.mock_service = Mock()
        self.mock_display = Mock()
        self.handler = ListHandler(self.mock_service, self.mock_display)

    def test_handle_lists_vpns(self):
        self.mock_service.list_vpns.return_value = [VPNType("EXT"), VPNType("INT")]

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
