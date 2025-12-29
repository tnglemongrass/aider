"""
Example module demonstrating type hints best practices for the Aider codebase.

This module serves as a reference for contributors adding type hints to existing code
or writing new typed code.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


def process_file(file_path: str) -> Optional[str]:
    """
    Process a file and return its contents.

    Args:
        file_path: Path to the file to process

    Returns:
        File contents as a string, or None if file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        return None
    return path.read_text()


def get_file_stats(file_path: str) -> Dict[str, Union[int, str]]:
    """
    Get statistics about a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary containing file statistics (size, extension, etc.)
    """
    path = Path(file_path)
    return {
        "size": path.stat().st_size if path.exists() else 0,
        "extension": path.suffix,
        "name": path.name,
    }


def find_files(directory: str, extensions: List[str]) -> List[Path]:
    """
    Find all files in a directory with given extensions.

    Args:
        directory: Directory to search
        extensions: List of file extensions to match (e.g., ['.py', '.txt'])

    Returns:
        List of Path objects for matching files
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []

    result: List[Path] = []
    for ext in extensions:
        result.extend(dir_path.glob(f"**/*{ext}"))
    return result


def split_path(file_path: str) -> Tuple[str, str]:
    """
    Split a file path into directory and filename.

    Args:
        file_path: Path to split

    Returns:
        Tuple of (directory, filename)
    """
    path = Path(file_path)
    return str(path.parent), path.name


class FileProcessor:
    """Example class with typed attributes and methods."""

    def __init__(self, base_dir: str, max_size: int = 1024 * 1024) -> None:
        """
        Initialize the file processor.

        Args:
            base_dir: Base directory for file operations
            max_size: Maximum file size to process in bytes
        """
        self.base_dir: Path = Path(base_dir)
        self.max_size: int = max_size
        self.processed_files: List[str] = []

    def can_process(self, file_path: str) -> bool:
        """
        Check if a file can be processed.

        Args:
            file_path: Path to the file

        Returns:
            True if file can be processed, False otherwise
        """
        path = Path(file_path)
        return path.exists() and path.stat().st_size <= self.max_size

    def process(self, file_path: str) -> Optional[Dict[str, Union[str, int]]]:
        """
        Process a file and return metadata.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary with file metadata, or None if processing failed
        """
        if not self.can_process(file_path):
            return None

        self.processed_files.append(file_path)
        return {
            "path": file_path,
            "size": Path(file_path).stat().st_size,
            "processed": True,
        }

    def get_processed_count(self) -> int:
        """
        Get the number of processed files.

        Returns:
            Count of processed files
        """
        return len(self.processed_files)


# Type aliases for complex types
FileMetadata = Dict[str, Union[str, int, bool]]
ProcessResult = Tuple[bool, Optional[str]]


def advanced_process(
    files: List[str], options: Optional[Dict[str, bool]] = None
) -> List[FileMetadata]:
    """
    Advanced file processing with optional configuration.

    Args:
        files: List of file paths to process
        options: Optional processing options

    Returns:
        List of file metadata dictionaries
    """
    if options is None:
        options = {}

    results: List[FileMetadata] = []
    for file_path in files:
        path = Path(file_path)
        if path.exists():
            results.append(
                {
                    "path": str(path),
                    "size": path.stat().st_size,
                    "is_file": path.is_file(),
                }
            )
    return results
