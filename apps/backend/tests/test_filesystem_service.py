import os
from pathlib import Path

import pytest

from dash_backend.tools.filesystem.filesystem_service import (
    read_file,
    write_file,
    list_directory,
    search_files,
    resolve_path_within_sandbox,
)


def test_write_and_read_file(tmp_path):
    base = tmp_path / "user_files"
    base.mkdir()
    # Temporarily override sandbox root by setting env var is not necessary because default uses cwd/user_files
    # Use working_directory relative path
    working_dir = str(Path("."))
    file_rel = "testdir/test.txt"
    content = "hello world\nsecond line"

    res = write_file(file_rel, content, working_directory=str(base))
    assert "path" in res
    assert res["size_bytes"] == len(content.encode("utf-8"))

    read = read_file(file_rel, working_directory=str(base))
    assert read["content"] == content
    assert read["size_bytes"] == res["size_bytes"]


def test_path_traversal_prevention(tmp_path):
    base = tmp_path / "user_files"
    base.mkdir()
    # create a file outside sandbox
    external = tmp_path / "outside.txt"
    external.write_text("secret")

    # Attempt to access via traversal
    with pytest.raises(ValueError):
        resolve_path_within_sandbox("../outside.txt", working_directory=str(base))


def test_list_and_search(tmp_path):
    base = tmp_path / "user_files"
    base.mkdir()
    d = base / "docs"
    d.mkdir()
    f1 = d / "a.txt"
    f1.write_text("alpha beta gamma")
    f2 = d / "b.txt"
    f2.write_text("delta alpha epsilon")

    lst = list_directory(".", working_directory=str(d))
    assert lst["total_entries"] >= 2

    search = search_files("alpha", path_str=".", working_directory=str(d))
    assert search["total_matches"] >= 2
