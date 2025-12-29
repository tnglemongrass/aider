"""
Tests for the typing_example module.

Demonstrates how to test type-hinted code.
"""

from pathlib import Path
from typing import Dict, List, Union

import pytest

from aider.typing_example import (
    FileProcessor,
    advanced_process,
    find_files,
    get_file_stats,
    process_file,
    split_path,
)


def test_process_file_exists(tmp_path: Path) -> None:
    """Test processing an existing file."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = process_file(str(test_file))
    assert result == "test content"


def test_process_file_not_exists(tmp_path: Path) -> None:
    """Test processing a non-existent file."""
    result = process_file(str(tmp_path / "nonexistent.txt"))
    assert result is None


def test_get_file_stats(tmp_path: Path) -> None:
    """Test getting file statistics."""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    stats = get_file_stats(str(test_file))
    assert isinstance(stats, dict)
    assert stats["extension"] == ".py"
    assert stats["name"] == "test.py"
    assert stats["size"] > 0


def test_find_files(tmp_path: Path) -> None:
    """Test finding files with specific extensions."""
    # Create test files
    (tmp_path / "file1.py").write_text("# Python file")
    (tmp_path / "file2.txt").write_text("Text file")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file3.py").write_text("# Another Python file")

    results = find_files(str(tmp_path), [".py"])
    assert len(results) == 2
    assert all(isinstance(p, Path) for p in results)


def test_split_path() -> None:
    """Test splitting a file path."""
    directory, filename = split_path("/path/to/file.txt")
    assert directory == "/path/to"
    assert filename == "file.txt"


class TestFileProcessor:
    """Tests for the FileProcessor class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test FileProcessor initialization."""
        processor = FileProcessor(str(tmp_path), max_size=1024)
        assert processor.base_dir == tmp_path
        assert processor.max_size == 1024
        assert processor.processed_files == []

    def test_can_process_valid_file(self, tmp_path: Path) -> None:
        """Test checking if a valid file can be processed."""
        processor = FileProcessor(str(tmp_path), max_size=1024)
        test_file = tmp_path / "small.txt"
        test_file.write_text("small content")

        assert processor.can_process(str(test_file)) is True

    def test_can_process_large_file(self, tmp_path: Path) -> None:
        """Test checking if a large file can be processed."""
        processor = FileProcessor(str(tmp_path), max_size=10)
        test_file = tmp_path / "large.txt"
        test_file.write_text("a" * 100)

        assert processor.can_process(str(test_file)) is False

    def test_process_valid_file(self, tmp_path: Path) -> None:
        """Test processing a valid file."""
        processor = FileProcessor(str(tmp_path), max_size=1024)
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = processor.process(str(test_file))
        assert result is not None
        assert result["path"] == str(test_file)
        assert result["processed"] is True
        assert processor.get_processed_count() == 1

    def test_process_invalid_file(self, tmp_path: Path) -> None:
        """Test processing an invalid file."""
        processor = FileProcessor(str(tmp_path), max_size=10)
        test_file = tmp_path / "large.txt"
        test_file.write_text("a" * 100)

        result = processor.process(str(test_file))
        assert result is None
        assert processor.get_processed_count() == 0


def test_advanced_process(tmp_path: Path) -> None:
    """Test advanced file processing."""
    # Create test files
    test_file1 = tmp_path / "file1.txt"
    test_file1.write_text("content1")
    test_file2 = tmp_path / "file2.txt"
    test_file2.write_text("content2")

    results = advanced_process([str(test_file1), str(test_file2)])
    assert len(results) == 2
    assert all(isinstance(r, dict) for r in results)
    assert all("path" in r and "size" in r and "is_file" in r for r in results)


def test_advanced_process_with_options(tmp_path: Path) -> None:
    """Test advanced processing with options."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    results = advanced_process([str(test_file)], options={"verbose": True})
    assert len(results) == 1


def test_advanced_process_empty_list() -> None:
    """Test advanced processing with empty file list."""
    results = advanced_process([])
    assert results == []
