"""Git commit and repository management for Coder."""

from aider.repo import ANY_GIT_ERROR


class CommitManager:
    """Handles git commit operations for the Coder."""

    def __init__(self, repo, io, gpt_prompts, commands):
        """Initialize CommitManager.

        Args:
            repo: GitRepo instance or None
            io: InputOutput instance
            gpt_prompts: Prompts object
            commands: Commands object
        """
        self.repo = repo
        self.io = io
        self.gpt_prompts = gpt_prompts
        self.commands = commands
        self.last_aider_commit_hash = None
        self.last_aider_commit_message = None
        self.aider_commit_hashes = set()
        self.need_commit_before_edits = set()

    def get_context_from_history(self, history):
        """Extract context from chat history.

        Args:
            history: List of message dictionaries

        Returns:
            Formatted context string
        """
        context = ""
        if history:
            for msg in history:
                context += "\n" + msg["role"].upper() + ": " + msg["content"] + "\n"

        return context

    def auto_commit(self, edited, context=None, cur_messages=None,
                    auto_commits=True, dry_run=False, show_diffs=False):
        """Automatically commit edited files.

        Args:
            edited: Set of edited file paths
            context: Optional context string
            cur_messages: Current message history
            auto_commits: Whether auto commits are enabled
            dry_run: Whether this is a dry run
            show_diffs: Whether to show diffs after commit

        Returns:
            Formatted commit message or None
        """
        if not self.repo or not auto_commits or dry_run:
            return

        if not context and cur_messages:
            context = self.get_context_from_history(cur_messages)

        try:
            res = self.repo.commit(fnames=edited, context=context, aider_edits=True, coder=None)
            if res:
                self.show_auto_commit_outcome(res, show_diffs)
                commit_hash, commit_message = res
                return self.gpt_prompts.files_content_gpt_edits.format(
                    hash=commit_hash,
                    message=commit_message,
                )

            return self.gpt_prompts.files_content_gpt_no_edits
        except ANY_GIT_ERROR as err:
            self.io.tool_error(f"Unable to commit: {str(err)}")
            return

    def show_auto_commit_outcome(self, res, show_diffs=False):
        """Show the outcome of an auto commit.

        Args:
            res: Tuple of (commit_hash, commit_message)
            show_diffs: Whether to show diffs
        """
        commit_hash, commit_message = res
        self.last_aider_commit_hash = commit_hash
        self.aider_commit_hashes.add(commit_hash)
        self.last_aider_commit_message = commit_message
        if show_diffs:
            self.commands.cmd_diff()

    def show_undo_hint(self, commit_before_message):
        """Show hint about undo command.

        Args:
            commit_before_message: List of commit hashes before message
        """
        if not commit_before_message:
            return
        if commit_before_message[-1] != self.repo.get_head_commit_sha():
            self.io.tool_output("You can use /undo to undo and discard each aider commit.")

    def dirty_commit(self, dirty_commits=True):
        """Commit dirty files that need to be committed before edits.

        Args:
            dirty_commits: Whether dirty commits are enabled

        Returns:
            True if committed, None otherwise
        """
        if not self.need_commit_before_edits:
            return
        if not dirty_commits:
            return
        if not self.repo:
            return

        self.repo.commit(fnames=self.need_commit_before_edits, coder=None)

        # files changed, move cur messages back behind the files messages
        # self.move_back_cur_messages(self.gpt_prompts.files_content_local_edits)
        return True

    def check_for_dirty_commit(self, path, dirty_commits=True):
        """Check if a file needs to be committed before editing.

        Args:
            path: File path to check
            dirty_commits: Whether dirty commits are enabled
        """
        if not self.repo:
            return
        if not dirty_commits:
            return
        if not self.repo.is_dirty(path):
            return

        # We need a committed copy of the file in order to /undo, so skip this
        # fullp = Path(self.abs_root_path(path))
        # if not fullp.stat().st_size:
        #     return

        self.io.tool_output(f"Committing {path} before applying edits.")
        self.need_commit_before_edits.add(path)
