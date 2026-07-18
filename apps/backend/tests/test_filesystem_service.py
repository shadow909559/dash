import os
from pathlib import Path

import pytest

from dash_backend.tools.filesystem.filesystem_service import (
    read_file,
    write_file,
    list_directory,
    search_files,
    resolve_path_within_sandbox,
    get_sandbox_root,
)


def test_write_and_read_file(tmp_path, monkeypatch):
    base = tmp_path / "user_files"
    base.mkdir()
    monkeypatch.setenv("DASH_FILES_SANDBOX", str(base))
    # Use working_directory relative path
    working_dir = str(Path("."))
    file_rel = "testdir/test.txt"
    content = "hello world\nsecond line"

    res = write_file(file_rel, content, working_directory=working_dir)
    assert "path" in res
    assert res["size_bytes"] == len(content.encode("utf-8"))

    read = read_file(file_rel, working_directory=working_dir)
    assert read["content"] == content
    assert read["size_bytes"] == res["size_bytes"]


def test_path_traversal_prevention(tmp_path, monkeypatch):
    base = tmp_path / "user_files"
    base.mkdir()
    monkeypatch.setenv("DASH_FILES_SANDBOX", str(base))
    # create a file outside sandbox
    external = tmp_path / "outside.txt"
    external.write_text("secret")

    # Attempt to access via traversal
    with pytest.raises(ValueError):
        resolve_path_within_sandbox("../outside.txt", working_directory=".")


def test_list_and_search(tmp_path, monkeypatch):
    base = tmp_path / "user_files"
    base.mkdir()
    monkeypatch.setenv("DASH_FILES_SANDBOX", str(base))
    d = base / "docs"
    d.mkdir()
    f1 = d / "a.txt"
    f1.write_text("alpha beta gamma")
    f2 = d / "b.txt"
    f2.write_text("delta alpha epsilon")

    lst = list_directory("docs", working_directory=".")
    assert lst["total_entries"] >= 2

    search = search_files("alpha", path_str="docs", working_directory=".")
    assert search["total_matches"] >= 2
