#!/usr/bin/env python3
"""Tests for infrastructure layer."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from domain.value_objects import VPNType
from infrastructure.process import CommandRunner, CommandResult
from infrastructure.vpn_repository import FileVPNRepository
from infrastructure.log_reader import LogReader


class TestCommandResult(unittest.TestCase):
    """Tests for CommandResult."""

    def test_success_true_on_zero_returncode(self):
        result = CommandResult(0, "output", "")
        self.assertTrue(result.success)

    def test_success_false_on_nonzero_returncode(self):
        result = CommandResult(1, "", "error")
        self.assertFalse(result.success)

    def test_success_false_on_negative_returncode(self):
        result = CommandResult(-1, "", "")
        self.assertFalse(result.success)


class TestCommandRunner(unittest.TestCase):
    """Tests for CommandRunner."""

    def setUp(self):
        self.runner = CommandRunner()

    def test_run_echo(self):
        result = self.runner.run(["echo", "hello"])
        self.assertTrue(result.success)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_run_false_command(self):
        result = self.runner.run(["false"])
        self.assertFalse(result.success)

    def test_run_nonexistent_command(self):
        result = self.runner.run(["nonexistent_command_xyz"])
        self.assertFalse(result.success)
        self.assertIn("not found", result.stderr)

    def test_run_with_timeout(self):
        result = self.runner.run(["sleep", "0.1"], timeout=5)
        self.assertTrue(result.success)

    def test_exists_true(self):
        self.assertTrue(self.runner.exists("echo"))

    def test_exists_false(self):
        self.assertFalse(self.runner.exists("nonexistent_command_xyz"))

    def test_run_captures_stderr(self):
        result = self.runner.run(["sh", "-c", "echo error >&2"])
        self.assertIn("error", result.stderr)


class TestFileVPNRepository(unittest.TestCase):
    """Tests for FileVPNRepository."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo = FileVPNRepository(Path(self.temp_dir))

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_list_available_empty(self):
        vpns = self.repo.list_available()
        self.assertEqual(vpns, [])

    def test_list_available_with_configs(self):
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        Path(self.temp_dir, "client-INT.ovpn").touch()
        vpns = self.repo.list_available()
        names = [v.name for v in vpns]
        self.assertIn("EXT", names)
        self.assertIn("INT", names)

    def test_list_available_ignores_non_matching(self):
        Path(self.temp_dir, "other.ovpn").touch()
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        vpns = self.repo.list_available()
        self.assertEqual(len(vpns), 1)
        self.assertEqual(vpns[0].name, "EXT")

    def test_list_available_nonexistent_dir(self):
        repo = FileVPNRepository(Path("/nonexistent/path"))
        self.assertEqual(repo.list_available(), [])

    def test_exists_true(self):
        Path(self.temp_dir, "client-EXT.ovpn").touch()
        self.assertTrue(self.repo.exists(VPNType("EXT")))

    def test_exists_false(self):
        self.assertFalse(self.repo.exists(VPNType("EXT")))

    def test_config_path(self):
        path = self.repo.config_path(VPNType("EXT"))
        self.assertEqual(path.name, "client-EXT.ovpn")


class TestLogReader(unittest.TestCase):
    """Tests for LogReader."""

    def setUp(self):
        self.reader = LogReader()
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)

    def tearDown(self):
        os.unlink(self.temp_file.name)

    def test_read_tail_empty_file(self):
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, [])

    def test_read_tail_single_line(self):
        self.temp_file.write("hello\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["hello"])

    def test_read_tail_multiple_lines(self):
        self.temp_file.write("line1\nline2\nline3\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["line1", "line2", "line3"])

    def test_read_tail_limits_lines(self):
        self.temp_file.write("line1\nline2\nline3\nline4\nline5\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 2)
        self.assertEqual(lines, ["line4", "line5"])

    def test_read_tail_nonexistent_file(self):
        lines = self.reader.read_tail("/nonexistent/file", 10)
        self.assertEqual(lines, [])

    def test_read_tail_empty_path(self):
        lines = self.reader.read_tail("", 10)
        self.assertEqual(lines, [])

    def test_read_tail_strips_carriage_return(self):
        self.temp_file.write("line1\r\nline2\r\n")
        self.temp_file.close()
        lines = self.reader.read_tail(self.temp_file.name, 10)
        self.assertEqual(lines, ["line1", "line2"])


if __name__ == "__main__":
    unittest.main()
