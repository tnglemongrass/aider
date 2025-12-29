"""File management utilities for Coder."""

import os
from pathlib import Path

from aider.utils import is_image_file, safe_abs_path


class FileManager:
    """Handles file path operations and content management for the Coder."""

    def __init__(self, root, io, abs_fnames=None, abs_read_only_fnames=None):
        """Initialize FileManager.

        Args:
            root: Root directory path
            io: InputOutput instance for reading files
            abs_fnames: Set of absolute file paths in chat
            abs_read_only_fnames: Set of read-only absolute file paths
        """
        self.root = root
        self.io = io
        self.abs_fnames = (
            abs_fnames if abs_fnames is not None else set()
        )
        self.abs_read_only_fnames = (
            abs_read_only_fnames if abs_read_only_fnames is not None else set()
        )
        self.abs_root_path_cache = {}

    def abs_root_path(self, path):
        """Convert a relative path to an absolute path from root."""
        key = path
        if key in self.abs_root_path_cache:
            return self.abs_root_path_cache[key]

        res = Path(self.root) / path
        res = safe_abs_path(res)
        self.abs_root_path_cache[key] = res
        return res

    def get_rel_fname(self, fname):
        """Get relative filename from absolute path."""
        try:
            return os.path.relpath(fname, self.root)
        except ValueError:
            return fname

    def get_inchat_relative_files(self):
        """Get sorted list of relative file paths in chat."""
        files = [self.get_rel_fname(fname) for fname in self.abs_fnames]
        return sorted(set(files))

    def is_file_safe(self, fname):
        """Check if a file path is safe to access."""
        try:
            return Path(self.abs_root_path(fname)).is_file()
        except OSError:
            return False

    def get_abs_fnames_content(self):
        """Yield (filename, content) tuples for files in chat."""
        for fname in list(self.abs_fnames):
            content = self.io.read_text(fname)

            if content is None:
                relative_fname = self.get_rel_fname(fname)
                self.io.tool_warning(f"Dropping {relative_fname} from the chat.")
                self.abs_fnames.remove(fname)
            else:
                yield fname, content

    def get_files_content(self, fence):
        """Get formatted content of all files in chat."""
        prompt = ""
        for fname, content in self.get_abs_fnames_content():
            if not is_image_file(fname):
                relative_fname = self.get_rel_fname(fname)
                prompt += "\n"
                prompt += relative_fname
                prompt += f"\n{fence[0]}\n"
                prompt += content
                prompt += f"{fence[1]}\n"

        return prompt

    def get_read_only_files_content(self, fence):
        """Get formatted content of read-only files."""
        prompt = ""
        for fname in self.abs_read_only_fnames:
            content = self.io.read_text(fname)
            if content is not None and not is_image_file(fname):
                relative_fname = self.get_rel_fname(fname)
                prompt += "\n"
                prompt += relative_fname
                prompt += f"\n{fence[0]}\n"
                prompt += content
                prompt += f"{fence[1]}\n"
        return prompt

    def add_rel_fname(self, rel_fname):
        """Add a relative filename to the chat."""
        self.abs_fnames.add(self.abs_root_path(rel_fname))

    def drop_rel_fname(self, fname):
        """Remove a filename from the chat."""
        abs_fname = self.abs_root_path(fname)
        if abs_fname in self.abs_fnames:
            self.abs_fnames.remove(abs_fname)
            return True
        return False
