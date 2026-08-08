"""Tests for restoring the executable bit HACS drops on install."""

from __future__ import annotations

import stat

from custom_components.rf433_outlets import ensure_executable

EXECUTABLE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _make(tmp_path, mode):
    path = tmp_path / "codesend"
    path.write_bytes(b"#!/bin/sh\n")
    path.chmod(mode)
    return path


def test_adds_the_executable_bits_when_they_are_missing(tmp_path):
    path = _make(tmp_path, 0o644)
    assert ensure_executable(path) is True
    assert path.stat().st_mode & EXECUTABLE == EXECUTABLE


def test_keeps_the_read_and_write_bits(tmp_path):
    path = _make(tmp_path, 0o640)
    ensure_executable(path)
    assert path.stat().st_mode & 0o777 == 0o751


def test_leaves_an_already_executable_file_alone(tmp_path):
    path = _make(tmp_path, 0o755)
    assert ensure_executable(path) is False
    assert path.stat().st_mode & 0o777 == 0o755


def test_reports_no_change_for_a_missing_file(tmp_path):
    """Sending a code reports that better than a startup warning could."""
    assert ensure_executable(tmp_path / "nope") is False
