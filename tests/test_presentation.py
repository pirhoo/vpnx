#!/usr/bin/env python3
"""Tests for presentation layer."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

os.environ["NO_COLOR"] = "1"

from domain import VPNState, Status
from presentation.terminal import Terminal, strip_ansi, visible_len
from presentation.tui import TUI, Box, StatusLine, SPINNER, STATUS_CONFIG
from presentation.cli import CLI
from application.commands import (
    SetupCommand,
    ListCommand,
    ConnectCommand,
    ConnectBothCommand,
)


class TestStripAnsi(unittest.TestCase):
    """Tests for strip_ansi function."""

    def test_plain_text(self):
        self.assertEqual(strip_ansi("hello"), "hello")

    def test_color_codes(self):
        self.assertEqual(strip_ansi("\033[32mhello\033[0m"), "hello")

    def test_multiple_codes(self):
        self.assertEqual(strip_ansi("\033[1;31mred\033[0m"), "red")

    def test_cursor_codes(self):
        self.assertEqual(strip_ansi("\033[H\033[K"), "")

    def test_empty_string(self):
        self.assertEqual(strip_ansi(""), "")

    def test_mixed_content(self):
        self.assertEqual(strip_ansi("a\033[32mb\033[0mc"), "abc")


class TestVisibleLen(unittest.TestCase):
    """Tests for visible_len function."""

    def test_plain_text(self):
        self.assertEqual(visible_len("hello"), 5)

    def test_with_ansi(self):
        self.assertEqual(visible_len("\033[32mhello\033[0m"), 5)

    def test_empty(self):
        self.assertEqual(visible_len(""), 0)

    def test_unicode(self):
        self.assertEqual(visible_len("●○"), 2)


class TestTerminal(unittest.TestCase):
    """Tests for Terminal class."""

    def setUp(self):
        self.term = Terminal()

    def test_no_color_mode(self):
        self.assertFalse(self.term.use_color)

    def test_color_returns_empty_in_no_color(self):
        self.assertEqual(self.term.color("green"), "")
        self.assertEqual(self.term.color("red"), "")

    def test_reset_returns_empty_in_no_color(self):
        self.assertEqual(self.term.reset(), "")

    def test_home_sequence(self):
        self.assertIn("H", self.term.home())

    def test_clear_line_sequence(self):
        self.assertIn("K", self.term.clear_line())

    def test_default_dimensions(self):
        self.assertGreater(self.term.width, 0)
        self.assertGreater(self.term.height, 0)


class TestBox(unittest.TestCase):
    """Tests for Box class."""

    def setUp(self):
        self.term = Terminal()
        self.box = Box(self.term)

    def test_hline_zero(self):
        self.assertEqual(self.box.hline(0), "")

    def test_hline_positive(self):
        self.assertEqual(self.box.hline(5), "─────")

    def test_top_with_title(self):
        result = self.box.top("Test", 20)
        self.assertTrue(result.startswith("╭"))
        self.assertTrue(result.endswith("╮"))
        self.assertIn("Test", result)

    def test_top_without_title(self):
        result = self.box.top("", 20)
        self.assertTrue(result.startswith("╭"))
        self.assertTrue(result.endswith("╮"))

    def test_bottom(self):
        result = self.box.bottom(20)
        self.assertTrue(result.startswith("╰"))
        self.assertTrue(result.endswith("╯"))

    def test_line_padding(self):
        result = self.box.line("hi", 20)
        self.assertEqual(len(result), 20)

    def test_line_truncation(self):
        long_text = "a" * 50
        result = self.box.line(long_text, 20)
        self.assertEqual(len(result), 20)

    def test_empty_line(self):
        result = self.box.empty(20)
        self.assertEqual(len(result), 20)
        self.assertTrue(result.startswith("│"))
        self.assertTrue(result.endswith("│"))


class TestStatusConfig(unittest.TestCase):
    """Tests for status configuration."""

    def test_all_statuses_configured(self):
        for status in Status:
            self.assertIn(status, STATUS_CONFIG)

    def test_config_tuple_length(self):
        for config in STATUS_CONFIG.values():
            self.assertEqual(len(config), 3)


class TestStatusLine(unittest.TestCase):
    """Tests for StatusLine class."""

    def setUp(self):
        self.term = Terminal()
        self.status = StatusLine(self.term)

    def test_format_plain_connected(self):
        result = self.status.format_plain(Status.CONNECTED)
        self.assertIn("●", result)
        self.assertIn("Connected", result)

    def test_format_plain_disconnected(self):
        result = self.status.format_plain(Status.DISCONNECTED)
        self.assertIn("○", result)
        self.assertIn("Disconnected", result)

    def test_format_plain_connecting(self):
        result = self.status.format_plain(Status.CONNECTING, 0)
        self.assertIn(SPINNER[0], result)

    def test_format_plain_waiting(self):
        result = self.status.format_plain(Status.WAITING)
        self.assertIn("○", result)
        self.assertIn("Waiting", result)

    def test_spinner_animation(self):
        f0 = self.status.format_plain(Status.CONNECTING, 0)
        f1 = self.status.format_plain(Status.CONNECTING, 1)
        self.assertNotEqual(f0, f1)

    def test_spinner_wraps(self):
        f0 = self.status.format_plain(Status.CONNECTING, 0)
        f_wrap = self.status.format_plain(Status.CONNECTING, len(SPINNER))
        self.assertEqual(f0, f_wrap)

    def test_fixed_width(self):
        for status in Status:
            result = self.status.format_plain(status)
            self.assertEqual(len(result), StatusLine.WIDTH)

    def test_format_line(self):
        result = self.status.format_line(Status.CONNECTED, Status.DISCONNECTED, 0)
        self.assertIn("EXT", result)
        self.assertIn("INT", result)


class TestTUI(unittest.TestCase):
    """Tests for TUI class."""

    def setUp(self):
        self.tui = TUI()

    def test_log_lines_count_positive(self):
        result = self.tui._log_lines_count(24)
        self.assertGreater(result, 0)

    def test_log_lines_count_minimum(self):
        result = self.tui._log_lines_count(10)
        self.assertGreaterEqual(result, 2)

    def test_render_box_structure(self):
        lines = self.tui._render_box("Test", ["a", "b"], 3, 40)
        self.assertEqual(len(lines), 5)  # top + 3 content + bottom

    def test_render_box_empty_lines(self):
        lines = self.tui._render_box("Test", [], 3, 40)
        self.assertEqual(len(lines), 5)

    def test_render_box_content_at_bottom(self):
        lines = self.tui._render_box("Test", ["x"], 3, 40)
        self.assertNotIn("x", lines[1])
        self.assertNotIn("x", lines[2])
        self.assertIn("x", lines[3])

    def test_render_includes_status(self):
        state = VPNState(ext_status=Status.CONNECTED, int_status=Status.DISCONNECTED)
        result = self.tui.render(state, 60, 20)
        self.assertIn("Status", result)

    def test_render_includes_logs(self):
        state = VPNState()
        result = self.tui.render(state, 60, 20)
        self.assertIn("EXT Log", result)
        self.assertIn("INT Log", result)

    def test_render_shows_hint_when_no_prompt(self):
        state = VPNState()
        result = self.tui.render(state, 60, 20)
        self.assertIn("Ctrl+C to disconnect", result)

    def test_render_shows_prompt_when_set(self):
        state = VPNState(prompt="Enter code: ")
        result = self.tui.render(state, 60, 20)
        self.assertIn("Enter code:", result)
        self.assertNotIn("Ctrl+C", result)

    def test_render_consistent_width(self):
        state = VPNState()
        result = self.tui.render(state, 60, 20)
        for line in result.split("\n"):
            stripped = strip_ansi(line)
            if stripped:
                self.assertEqual(len(stripped), 60)


class TestCLI(unittest.TestCase):
    """Tests for CLI class."""

    def setUp(self):
        self.cli = CLI()

    def test_parse_setup(self):
        cmd = self.cli.parse(["setup"])
        self.assertIsInstance(cmd, SetupCommand)

    def test_parse_list(self):
        cmd = self.cli.parse(["list"])
        self.assertIsInstance(cmd, ListCommand)

    def test_parse_ext(self):
        cmd = self.cli.parse(["ext"])
        self.assertIsInstance(cmd, ConnectCommand)
        self.assertEqual(cmd.vpn_type.name, "EXT")

    def test_parse_int(self):
        cmd = self.cli.parse(["int"])
        self.assertIsInstance(cmd, ConnectCommand)
        self.assertEqual(cmd.vpn_type.name, "INT")

    def test_parse_both(self):
        cmd = self.cli.parse(["both"])
        self.assertIsInstance(cmd, ConnectBothCommand)

    def test_parse_connect_with_vpn(self):
        cmd = self.cli.parse(["connect", "custom"])
        self.assertIsInstance(cmd, ConnectCommand)
        self.assertEqual(cmd.vpn_type.name, "CUSTOM")

    def test_parse_no_command(self):
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        cmd = self.cli.parse([])
        sys.stdout = old_stdout
        self.assertIsNone(cmd)


if __name__ == "__main__":
    unittest.main()
