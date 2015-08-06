#!/usr/bin/env python
#
# Tests for git-edit-index.
#
# Home page:
#
#    https://github.com/s3rvac/git-edit-index
#
# License:
#
#    The MIT License (MIT)
#
#    Copyright (c) 2015 Petr Zemek <s3rvac@gmail.com> and contributors.
#
#    Permission is hereby granted, free of charge, to any person obtaining a
#    copy of this software and associated documentation files (the "Software"),
#    to deal in the Software without restriction, including without limitation
#    the rights to use, copy, modify, merge, publish, distribute, sublicense,
#    and/or sell copies of the Software, and to permit persons to whom the
#    Software is furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
#    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#

import io
import os
import subprocess
import unittest
from unittest import mock

from git_edit_index import editor_cmd
from git_edit_index import editor_cmd_from_env
from git_edit_index import editor_cmd_from_git
from git_edit_index import git_status
from git_edit_index import parse_args
from git_edit_index import perform_git_action
from git_edit_index import repository_path


# Do not inherit from unittest.TestCase because WithPatching is a mixin, not a
# base class for tests.
class WithPatching:
    """Mixin for tests that perform patching during their setup."""

    def patch(self, what, with_what):
        """Patches `what` with `with_what`."""
        patcher = mock.patch(what, with_what)
        patcher.start()
        self.addCleanup(patcher.stop)


class GitStatusTests(unittest.TestCase, WithPatching):
    """Tests for `git_status()`."""

    def setUp(self):
        super().setUp()

        self.subprocess = mock.Mock()
        self.patch('git_edit_index.subprocess', self.subprocess)

    def test_calls_correct_git_command_and_returns_correct_status(self):
        STATUS = 'status'
        self.subprocess.check_output.return_value = STATUS

        status = git_status()

        self.assertEqual(status, STATUS)
        self.subprocess.check_output.assert_called_once_with(
            ['git', 'status', '--porcelain', '-z'],
            universal_newlines=True
        )


class EditorCmdFromGitTests(unittest.TestCase, WithPatching):
    """Tests for `editor_cmd_from_git()`."""

    def setUp(self):
        super().setUp()

        self.subprocess = mock.Mock()
        self.patch('git_edit_index.subprocess', self.subprocess)

    def test_calls_correct_git_command(self):
        editor_cmd_from_git()

        self.subprocess.check_output.assert_called_once_with(
            ['git', 'config', 'core.editor'],
            universal_newlines=True
        )

    def test_returns_correct_cmd_when_editor_is_set(self):
        CMD = ['gvim', '-f']
        self.subprocess.check_output.return_value = '{}\n'.format(
            ' '.join(CMD)
        )

        cmd = editor_cmd_from_git()

        self.assertEqual(cmd, CMD)

    def test_returns_none_when_editor_is_not_set(self):
        self.subprocess.CalledProcessError = subprocess.CalledProcessError
        self.subprocess.check_output.side_effect = subprocess.CalledProcessError(
            1, 'git cmd'
        )

        cmd = editor_cmd_from_git()

        self.assertIsNone(cmd)


class EditorCmdTests(unittest.TestCase, WithPatching):
    """Tests for `editor_cmd()`."""

    def setUp(self):
        super().setUp()

        self.editor_cmd_from_git = mock.Mock()
        self.patch('git_edit_index.editor_cmd_from_git', self.editor_cmd_from_git)

        self.editor_cmd_from_env = mock.Mock()
        self.patch('git_edit_index.editor_cmd_from_env', self.editor_cmd_from_env)

    def test_returns_editor_cmd_from_git_when_set(self):
        CMD = ['gvim', '-f']
        self.editor_cmd_from_git.return_value = CMD
        self.editor_cmd_from_env.return_value = None

        cmd = editor_cmd()

        self.assertEqual(cmd, CMD)

    def test_returns_editor_cmd_from_env_when_set_and_git_editor_is_not_set(self):
        CMD = ['gvim', '-f']
        self.editor_cmd_from_git.return_value = None
        self.editor_cmd_from_env.return_value = CMD

        cmd = editor_cmd()

        self.assertEqual(cmd, CMD)

    def test_raises_runtime_error_when_no_editor_is_set(self):
        self.editor_cmd_from_git.return_value = None
        self.editor_cmd_from_env.return_value = None

        with self.assertRaisesRegex(RuntimeError, 'No editor found\.'):
            editor_cmd()


class EditorCmdFromEndTests(unittest.TestCase, WithPatching):
    """Tests for `editor_cmd_from_env()`."""

    def setUp(self):
        super().setUp()

        self.os = mock.Mock()
        self.patch('git_edit_index.os', self.os)

    def test_returns_correct_cmd_when_editor_is_set(self):
        CMD = ['gvim', '-f']
        self.os.environ = {'EDITOR': ' '.join(CMD)}

        cmd = editor_cmd_from_env()

        self.assertEqual(cmd, CMD)

    def test_returns_none_when_editor_is_not_set(self):
        self.os.environ = {}

        cmd = editor_cmd_from_env()

        self.assertIsNone(cmd)


class PerformGitActionTests(unittest.TestCase, WithPatching):
    """Tests for `perform_git_action()`."""

    def setUp(self):
        super().setUp()

        self.subprocess = mock.Mock()
        self.patch('git_edit_index.subprocess', self.subprocess)

        self.repository_path = mock.Mock()
        self.patch('git_edit_index.repository_path', self.repository_path)

    def test_calls_git_with_proper_arguments_when_action_is_single_command(self):
        self.repository_path.return_value = '/'

        perform_git_action('add', 'file.txt')

        self.subprocess.call.assert_called_once_with(
            ['git', 'add', '--', os.path.join('/', 'file.txt')],
            stdout=self.subprocess.PIPE
        )

    def test_calls_git_with_proper_arguments_when_action_is_compound_command(self):
        self.repository_path.return_value = '/'

        perform_git_action(['rm', '--cached'], 'file.txt')

        self.subprocess.call.assert_called_once_with(
            ['git', 'rm', '--cached', '--', os.path.join('/', 'file.txt')],
            stdout=self.subprocess.PIPE
        )


class RepositoryPathTests(unittest.TestCase, WithPatching):
    """Tests for `repository_path()`."""

    def setUp(self):
        super().setUp()

        self.subprocess = mock.Mock()
        self.patch('git_edit_index.subprocess', self.subprocess)

    def test_calls_correct_git_command_and_returns_correct_path(self):
        REPOSITORY_PATH = '/path/to/repo'
        self.subprocess.check_output.return_value = '{}\n'.format(
            REPOSITORY_PATH
        )

        path = repository_path()

        self.assertEqual(path, REPOSITORY_PATH)
        self.subprocess.check_output.assert_called_once_with(
            ['git', 'rev-parse', '--show-toplevel'],
            universal_newlines=True
        )


class ParseArgsTests(unittest.TestCase, WithPatching):
    """Tests for `parse_args()`."""

    def setUp(self):
        super().setUp()

        self.stdout = io.StringIO()
        self.patch('sys.stdout', self.stdout)

        self.stderr = io.StringIO()
        self.patch('sys.stderr', self.stderr)

    def test_prints_help_and_exits_when_requested(self):
        with self.assertRaises(SystemExit) as cm:
            parse_args(['git-edit-index', '--help'])
        self.assertEqual(cm.exception.code, 0)

    def test_prints_error_message_and_exits_when_invalid_parameter_is_given(self):
        with self.assertRaises(SystemExit) as cm:
            parse_args(['git-edit-index', '--xyz'])
        self.assertNotEqual(cm.exception.code, 0)
