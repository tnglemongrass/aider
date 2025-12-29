"""Linting and testing operations for Coder."""

from aider.linter import Linter


class LintTestManager:
    """Handles linting and testing operations for the Coder."""

    def __init__(self, io, root, encoding):
        """Initialize LintTestManager.

        Args:
            io: InputOutput instance
            root: Root directory
            encoding: File encoding
        """
        self.io = io
        self.root = root
        self.linter = Linter(root=root, encoding=encoding)
        self.lint_cmds = None

    def setup_lint_cmds(self, lint_cmds):
        """Setup linter commands.

        Args:
            lint_cmds: Dictionary of language to lint command
        """
        if not lint_cmds:
            return
        self.lint_cmds = lint_cmds
        for lang, cmd in lint_cmds.items():
            self.linter.set_linter(lang, cmd)

    def lint_edited(self, fnames, abs_root_path_func):
        """Lint edited files.

        Args:
            fnames: List of file names to lint
            abs_root_path_func: Function to convert relative to absolute paths

        Returns:
            String with lint errors or empty string
        """
        res = ""
        for fname in fnames:
            if not fname:
                continue
            errors = self.linter.lint(abs_root_path_func(fname))

            if errors:
                res += "\n"
                res += errors
                res += "\n"

        if res:
            self.io.tool_warning(res)

        return res
