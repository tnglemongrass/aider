"""Core implementation of Coder class."""

# Import everything needed for the implementation
import base64
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time
import traceback
from collections import defaultdict
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import List

from rich.console import Console

from aider import __version__, models, prompts, urls, utils
from aider.analytics import Analytics
from aider.commands import Commands
from aider.exceptions import LiteLLMExceptions
from aider.history import ChatSummary
from aider.io import ConfirmGroup, InputOutput
from aider.llm import litellm
from aider.models import RETRY_TIMEOUT
from aider.reasoning_tags import (
    REASONING_TAG,
    format_reasoning_content,
    remove_reasoning_content,
    replace_reasoning_tags,
)
from aider.repo import ANY_GIT_ERROR, GitRepo
from aider.repomap import RepoMap
from aider.utils import format_content, format_messages, format_tokens, is_image_file
from aider.waiting import WaitingSpinner

from ..dump import dump  # noqa: F401
from .chat_chunks import ChatChunks
from .commit_manager import CommitManager
from .file_manager import FileManager
from .lint_test_manager import LintTestManager
from .message_formatter import MessageFormatter
from .platform_detector import PlatformDetector
from .shell_command_manager import ShellCommandManager
from .token_calculator import TokenCalculator


class CoderImpl:
    """Base implementation class for Coder with all methods."""

    def __init__(
        self,
        main_model,
        io,
        repo=None,
        fnames=None,
        add_gitignore_files=False,
        read_only_fnames=None,
        show_diffs=False,
        auto_commits=True,
        dirty_commits=True,
        dry_run=False,
        map_tokens=1024,
        verbose=False,
        stream=True,
        use_git=True,
        cur_messages=None,
        done_messages=None,
        restore_chat_history=False,
        auto_lint=True,
        auto_test=False,
        lint_cmds=None,
        test_cmd=None,
        aider_commit_hashes=None,
        map_mul_no_files=8,
        commands=None,
        summarizer=None,
        total_cost=0.0,
        analytics=None,
        map_refresh="auto",
        cache_prompts=False,
        num_cache_warming_pings=0,
        suggest_shell_commands=True,
        chat_language=None,
        commit_language=None,
        detect_urls=True,
        ignore_mentions=None,
        total_tokens_sent=0,
        total_tokens_received=0,
        file_watcher=None,
        auto_copy_context=False,
        auto_accept_architect=True,
    ):
        # Fill in a dummy Analytics if needed, but it is never .enable()'d
        self.analytics = analytics if analytics is not None else Analytics()

        self.event = self.analytics.event
        self.chat_language = chat_language
        self.commit_language = commit_language
        self.commit_before_message = []
        self.rejected_urls = set()

        self.auto_copy_context = auto_copy_context
        self.auto_accept_architect = auto_accept_architect

        self.ignore_mentions = ignore_mentions
        if not self.ignore_mentions:
            self.ignore_mentions = set()

        self.file_watcher = file_watcher
        if self.file_watcher:
            self.file_watcher.coder = self

        self.suggest_shell_commands = suggest_shell_commands
        self.detect_urls = detect_urls

        self.num_cache_warming_pings = num_cache_warming_pings

        if not fnames:
            fnames = []

        if io is None:
            io = InputOutput()

        # Note: aider_commit_hashes will be set via commit_manager later

        self.chat_completion_call_hashes = []
        self.chat_completion_response_hashes = []
        # Note: need_commit_before_edits is now a property of commit_manager

        self.verbose = verbose
        self.abs_fnames = set()
        self.abs_read_only_fnames = set()
        self.add_gitignore_files = add_gitignore_files

        if cur_messages:
            self.cur_messages = cur_messages
        else:
            self.cur_messages = []

        if done_messages:
            self.done_messages = done_messages
        else:
            self.done_messages = []

        self.io = io

        # Initialize helper classes
        self.platform_detector = PlatformDetector()
        self.shell_command_manager = ShellCommandManager(io, None)  # root set later

        if not auto_commits:
            dirty_commits = False

        self.auto_commits = auto_commits
        self.dirty_commits = dirty_commits

        self.dry_run = dry_run
        self.pretty = self.io.pretty

        self.main_model = main_model
        # Set the reasoning tag name based on model settings or default
        self.reasoning_tag_name = (
            self.main_model.reasoning_tag if self.main_model.reasoning_tag else REASONING_TAG
        )

        # Initialize token calculator
        self.token_calculator = TokenCalculator(main_model, io)
        self.token_calculator.total_cost = total_cost
        self.token_calculator.total_tokens_sent = total_tokens_sent
        self.token_calculator.total_tokens_received = total_tokens_received

        self.stream = stream and main_model.streaming

        if cache_prompts and self.main_model.cache_control:
            self.add_cache_headers = True

        self.show_diffs = show_diffs

        self.commands = commands or Commands(self.io, self)
        self.commands.coder = self

        self.repo = repo
        if use_git and self.repo is None:
            try:
                self.repo = GitRepo(
                    self.io,
                    fnames,
                    None,
                    models=main_model.commit_message_models(),
                )
            except FileNotFoundError:
                pass

        if self.repo:
            self.root = self.repo.root

        for fname in fnames:
            fname = Path(fname)
            if self.repo and self.repo.git_ignored_file(fname) and not self.add_gitignore_files:
                self.io.tool_warning(f"Skipping {fname} that matches gitignore spec.")
                continue

            if self.repo and self.repo.ignored_file(fname):
                self.io.tool_warning(f"Skipping {fname} that matches aiderignore spec.")
                continue

            if not fname.exists():
                if utils.touch_file(fname):
                    self.io.tool_output(f"Creating empty file {fname}")
                else:
                    self.io.tool_warning(f"Can not create {fname}, skipping.")
                    continue

            if not fname.is_file():
                self.io.tool_warning(f"Skipping {fname} that is not a normal file.")
                continue

            fname = str(fname.resolve())

            self.abs_fnames.add(fname)
            self.check_added_files()

        if not self.repo:
            self.root = utils.find_common_root(self.abs_fnames)

        # Initialize file manager after root is determined
        self.file_manager = FileManager(self.root, io, self.abs_fnames, self.abs_read_only_fnames)

        # Update shell command manager with root
        self.shell_command_manager.root = self.root

        if read_only_fnames:
            self.abs_read_only_fnames = set()
            for fname in read_only_fnames:
                abs_fname = self.abs_root_path(fname)
                if os.path.exists(abs_fname):
                    self.abs_read_only_fnames.add(abs_fname)
                else:
                    self.io.tool_warning(f"Error: Read-only file {fname} does not exist. Skipping.")

        if map_tokens is None:
            use_repo_map = main_model.use_repo_map
            map_tokens = 1024
        else:
            use_repo_map = map_tokens > 0

        max_inp_tokens = self.main_model.info.get("max_input_tokens") or 0

        has_map_prompt = hasattr(self, "gpt_prompts") and self.gpt_prompts.repo_content_prefix

        if use_repo_map and self.repo and has_map_prompt:
            self.repo_map = RepoMap(
                map_tokens,
                self.root,
                self.main_model,
                io,
                self.gpt_prompts.repo_content_prefix,
                self.verbose,
                max_inp_tokens,
                map_mul_no_files=map_mul_no_files,
                refresh=map_refresh,
            )

        self.summarizer = summarizer or ChatSummary(
            [self.main_model.weak_model, self.main_model],
            self.main_model.max_chat_history_tokens,
        )

        self.summarizer_thread = None
        self.summarized_done_messages = []
        self.summarizing_messages = None

        if not self.done_messages and restore_chat_history:
            history_md = self.io.read_text(self.io.chat_history_file)
            if history_md:
                self.done_messages = utils.split_chat_history_markdown(history_md)
                self.summarize_start()

        # Linting and testing
        self.lint_test_manager = LintTestManager(io, self.root, io.encoding)
        self.auto_lint = auto_lint
        self.lint_test_manager.setup_lint_cmds(lint_cmds)
        self.lint_cmds = lint_cmds
        self.auto_test = auto_test
        self.test_cmd = test_cmd

        # Commit management
        self.commit_manager = CommitManager(self.repo, io, self.gpt_prompts, self.commands)
        if aider_commit_hashes:
            self.commit_manager.aider_commit_hashes = aider_commit_hashes

        # Message formatting
        self.message_formatter = MessageFormatter(main_model, self.gpt_prompts, io)

        # validate the functions jsonschema
        if self.functions:
            from jsonschema import Draft7Validator

            for function in self.functions:
                Draft7Validator.check_schema(function)

            if self.verbose:
                self.io.tool_output("JSON Schema:")
                self.io.tool_output(json.dumps(self.functions, indent=4))

    def setup_lint_cmds(self, lint_cmds):
        if hasattr(self, 'lint_test_manager'):
            self.lint_test_manager.setup_lint_cmds(lint_cmds)

    # Properties for backward compatibility with token calculator
    @property
    def total_cost(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.total_cost
        return 0.0

    @total_cost.setter
    def total_cost(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.total_cost = value

    @property
    def total_tokens_sent(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.total_tokens_sent
        return 0

    @total_tokens_sent.setter
    def total_tokens_sent(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.total_tokens_sent = value

    @property
    def total_tokens_received(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.total_tokens_received
        return 0

    @total_tokens_received.setter
    def total_tokens_received(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.total_tokens_received = value

    @property
    def message_cost(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.message_cost
        return 0.0

    @message_cost.setter
    def message_cost(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.message_cost = value

    @property
    def message_tokens_sent(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.message_tokens_sent
        return 0

    @message_tokens_sent.setter
    def message_tokens_sent(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.message_tokens_sent = value

    @property
    def message_tokens_received(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.message_tokens_received
        return 0

    @message_tokens_received.setter
    def message_tokens_received(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.message_tokens_received = value

    @property
    def usage_report(self):
        if hasattr(self, 'token_calculator'):
            return self.token_calculator.usage_report
        return None

    @usage_report.setter
    def usage_report(self, value):
        if hasattr(self, 'token_calculator'):
            self.token_calculator.usage_report = value

    @property
    def shell_commands(self):
        if hasattr(self, 'shell_command_manager'):
            return self.shell_command_manager.shell_commands
        return []

    @shell_commands.setter
    def shell_commands(self, value):
        if hasattr(self, 'shell_command_manager'):
            self.shell_command_manager.shell_commands = value

    @property
    def need_commit_before_edits(self):
        if hasattr(self, 'commit_manager'):
            return self.commit_manager.need_commit_before_edits
        return set()

    @need_commit_before_edits.setter
    def need_commit_before_edits(self, value):
        if hasattr(self, 'commit_manager'):
            self.commit_manager.need_commit_before_edits = value

    @property
    def last_aider_commit_hash(self):
        if hasattr(self, 'commit_manager'):
            return self.commit_manager.last_aider_commit_hash
        return None

    @last_aider_commit_hash.setter
    def last_aider_commit_hash(self, value):
        if hasattr(self, 'commit_manager'):
            self.commit_manager.last_aider_commit_hash = value

    @property
    def aider_commit_hashes(self):
        if hasattr(self, 'commit_manager'):
            return self.commit_manager.aider_commit_hashes
        return set()

    @aider_commit_hashes.setter
    def aider_commit_hashes(self, value):
        if hasattr(self, 'commit_manager'):
            self.commit_manager.aider_commit_hashes = value

    def show_announcements(self):
        bold = True
        for line in self.get_announcements():
            self.io.tool_output(line, bold=bold)
            bold = False

    def add_rel_fname(self, rel_fname):
        self.file_manager.add_rel_fname(rel_fname)
        self.check_added_files()

    def drop_rel_fname(self, fname):
        return self.file_manager.drop_rel_fname(fname)

    def abs_root_path(self, path):
        return self.file_manager.abs_root_path(path)

    fences = all_fences
    fence = fences[0]

    def show_pretty(self):
        if not self.pretty:
            return False

        # only show pretty output if fences are the normal triple-backtick
        if self.fence[0][0] != "`":
            return False

        return True

    def _stop_waiting_spinner(self):
        """Stop and clear the waiting spinner if it is running."""
        spinner = getattr(self, "waiting_spinner", None)
        if spinner:
            try:
                spinner.stop()
            finally:
                self.waiting_spinner = None

    def get_abs_fnames_content(self):
        return self.file_manager.get_abs_fnames_content()

    def choose_fence(self):
        all_content = ""
        for _fname, content in self.get_abs_fnames_content():
            all_content += content + "\n"
        for _fname in self.abs_read_only_fnames:
            content = self.io.read_text(_fname)
            if content is not None:
                all_content += content + "\n"

        lines = all_content.splitlines()
        good = False
        for fence_open, fence_close in self.fences:
            if any(line.startswith(fence_open) or line.startswith(fence_close) for line in lines):
                continue
            good = True
            break

        if good:
            self.fence = (fence_open, fence_close)
        else:
            self.fence = self.fences[0]
            self.io.tool_warning(
                "Unable to find a fencing strategy! Falling back to:"
                f" {self.fence[0]}...{self.fence[1]}"
            )

        return

    def get_files_content(self, fnames=None):
        if not fnames:
            fnames = self.abs_fnames

        return self.file_manager.get_files_content(self.fence)

    def get_read_only_files_content(self):
        return self.file_manager.get_read_only_files_content(self.fence)

    def get_cur_message_text(self):
        text = ""
        for msg in self.cur_messages:
            text += msg["content"] + "\n"
        return text

    def get_ident_mentions(self, text):
        # Split the string on any character that is not alphanumeric
        # \W+ matches one or more non-word characters (equivalent to [^a-zA-Z0-9_]+)
        words = set(re.split(r"\W+", text))
        return words

    def get_ident_filename_matches(self, idents):
        all_fnames = defaultdict(set)
        for fname in self.get_all_relative_files():
            # Skip empty paths or just '.'
            if not fname or fname == ".":
                continue

            try:
                # Handle dotfiles properly
                path = Path(fname)
                base = path.stem.lower()  # Use stem instead of with_suffix("").name
                if len(base) >= 5:
                    all_fnames[base].add(fname)
            except ValueError:
                # Skip paths that can't be processed
                continue

        matches = set()
        for ident in idents:
            if len(ident) < 5:
                continue
            matches.update(all_fnames[ident.lower()])

        return matches

    def get_repo_map(self, force_refresh=False):
        if not self.repo_map:
            return

        cur_msg_text = self.get_cur_message_text()
        mentioned_fnames = self.get_file_mentions(cur_msg_text)
        mentioned_idents = self.get_ident_mentions(cur_msg_text)

        mentioned_fnames.update(self.get_ident_filename_matches(mentioned_idents))

        all_abs_files = set(self.get_all_abs_files())
        repo_abs_read_only_fnames = set(self.abs_read_only_fnames) & all_abs_files
        chat_files = set(self.abs_fnames) | repo_abs_read_only_fnames
        other_files = all_abs_files - chat_files

        repo_content = self.repo_map.get_repo_map(
            chat_files,
            other_files,
            mentioned_fnames=mentioned_fnames,
            mentioned_idents=mentioned_idents,
            force_refresh=force_refresh,
        )

        # fall back to global repo map if files in chat are disjoint from rest of repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                all_abs_files,
                mentioned_fnames=mentioned_fnames,
                mentioned_idents=mentioned_idents,
            )

        # fall back to completely unhinted repo
        if not repo_content:
            repo_content = self.repo_map.get_repo_map(
                set(),
                all_abs_files,
            )

        return repo_content

    def get_repo_messages(self):
        return self.message_formatter.get_repo_messages(self.get_repo_map)

    def get_readonly_files_messages(self):
        return self.message_formatter.get_readonly_files_messages(
            self.get_read_only_files_content,
            self.get_images_message,
            self.abs_read_only_fnames,
        )

    def get_chat_files_messages(self):
        return self.message_formatter.get_chat_files_messages(
            self.abs_fnames,
            self.get_files_content,
            self.get_repo_map,
            self.get_images_message,
        )

    def get_images_message(self, fnames):
        return self.message_formatter.get_images_message(fnames, self.get_rel_fname)

    def run_stream(self, user_message):
        self.io.user_input(user_message)
        self.init_before_message()
        yield from self.send_message(user_message)

    def init_before_message(self):
        self.aider_edited_files = set()
        self.reflected_message = None
        self.num_reflections = 0
        self.lint_outcome = None
        self.test_outcome = None
        self.shell_commands = []
        self.message_cost = 0

        if self.repo:
            self.commit_before_message.append(self.repo.get_head_commit_sha())

    def run(self, with_message=None, preproc=True):
        try:
            if with_message:
                self.io.user_input(with_message)
                self.run_one(with_message, preproc)
                return self.partial_response_content
            while True:
                try:
                    if not self.io.placeholder:
                        self.copy_context()
                    user_message = self.get_input()
                    self.run_one(user_message, preproc)
                    self.show_undo_hint()
                except KeyboardInterrupt:
                    self.keyboard_interrupt()
        except EOFError:
            return

    def copy_context(self):
        if self.auto_copy_context:
            self.commands.cmd_copy_context()

    def get_input(self):
        inchat_files = self.get_inchat_relative_files()
        read_only_files = [self.get_rel_fname(fname) for fname in self.abs_read_only_fnames]
        all_files = sorted(set(inchat_files + read_only_files))
        edit_format = "" if self.edit_format == self.main_model.edit_format else self.edit_format
        return self.io.get_input(
            self.root,
            all_files,
            self.get_addable_relative_files(),
            self.commands,
            self.abs_read_only_fnames,
            edit_format=edit_format,
        )

    def preproc_user_input(self, inp):
        if not inp:
            return

        if self.commands.is_command(inp):
            return self.commands.run(inp)

        self.check_for_file_mentions(inp)
        inp = self.check_for_urls(inp)

        return inp

    def run_one(self, user_message, preproc):
        self.init_before_message()

        if preproc:
            message = self.preproc_user_input(user_message)
        else:
            message = user_message

        while message:
            self.reflected_message = None
            list(self.send_message(message))

            if not self.reflected_message:
                break

            if self.num_reflections >= self.max_reflections:
                self.io.tool_warning(f"Only {self.max_reflections} reflections allowed, stopping.")
                return

            self.num_reflections += 1
            message = self.reflected_message

    def check_and_open_urls(self, exc, friendly_msg=None):
        """Check exception for URLs, offer to open in a browser, with user-friendly error msgs."""
        text = str(exc)

        if friendly_msg:
            self.io.tool_warning(text)
            self.io.tool_error(f"{friendly_msg}")
        else:
            self.io.tool_error(text)

        # Exclude double quotes from the matched URL characters
        url_pattern = re.compile(r'(https?://[^\s/$.?#].[^\s"]*)')
        urls = list(set(url_pattern.findall(text)))  # Use set to remove duplicates
        for url in urls:
            url = url.rstrip(".',\"}")  # Added } to the characters to strip
            self.io.offer_url(url)
        return urls

    def check_for_urls(self, inp: str) -> List[str]:
        """Check input for URLs and offer to add them to the chat."""
        if not self.detect_urls:
            return inp

        # Exclude double quotes from the matched URL characters
        url_pattern = re.compile(r'(https?://[^\s/$.?#].[^\s"]*[^\s,.])')
        urls = list(set(url_pattern.findall(inp)))  # Use set to remove duplicates
        group = ConfirmGroup(urls)
        for url in urls:
            if url not in self.rejected_urls:
                url = url.rstrip(".',\"")
                if self.io.confirm_ask(
                    "Add URL to the chat?", subject=url, group=group, allow_never=True
                ):
                    inp += "\n\n"
                    inp += self.commands.cmd_web(url, return_content=True)
                else:
                    self.rejected_urls.add(url)

        return inp

    def keyboard_interrupt(self):
        # Ensure cursor is visible on exit
        Console().show_cursor(True)

        now = time.time()

        thresh = 2  # seconds
        if self.last_keyboard_interrupt and now - self.last_keyboard_interrupt < thresh:
            self.io.tool_warning("\n\n^C KeyboardInterrupt")
            self.event("exit", reason="Control-C")
            sys.exit()

        self.io.tool_warning("\n\n^C again to exit")

        self.last_keyboard_interrupt = now

    def summarize_start(self):
        if not self.summarizer.too_big(self.done_messages):
            return

        self.summarize_end()

        if self.verbose:
            self.io.tool_output("Starting to summarize chat history.")

        self.summarizer_thread = threading.Thread(target=self.summarize_worker)
        self.summarizer_thread.start()

    def summarize_worker(self):
        self.summarizing_messages = list(self.done_messages)
        try:
            self.summarized_done_messages = self.summarizer.summarize(self.summarizing_messages)
        except ValueError as err:
            self.io.tool_warning(err.args[0])

        if self.verbose:
            self.io.tool_output("Finished summarizing chat history.")

    def summarize_end(self):
        if self.summarizer_thread is None:
            return

        self.summarizer_thread.join()
        self.summarizer_thread = None

        if self.summarizing_messages == self.done_messages:
            self.done_messages = self.summarized_done_messages
        self.summarizing_messages = None
        self.summarized_done_messages = []

    def move_back_cur_messages(self, message):
        self.done_messages += self.cur_messages
        self.summarize_start()

        # TODO check for impact on image messages
        if message:
            self.done_messages += [
                dict(role="user", content=message),
                dict(role="assistant", content="Ok."),
            ]
        self.cur_messages = []

    def normalize_language(self, lang_code):
        return self.platform_detector.normalize_language(lang_code)

    def get_user_language(self):
        # Explicit override
        if self.chat_language:
            return self.normalize_language(self.chat_language)

        # System locale
        try:
            import locale
            lang = locale.getlocale()[0]
            if lang:
                lang = self.normalize_language(lang)
            if lang:
                return lang
        except Exception:
            pass

        # Environment variables
        for env_var in ("LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"):
            lang = os.environ.get(env_var)
            if lang:
                lang = lang.split(".")[0]  # Strip encoding if present
                return self.normalize_language(lang)

        return None

    def get_platform_info(self):
        return self.platform_detector.get_platform_info(
            repo=self.repo,
            lint_cmds=self.lint_cmds,
            auto_lint=self.auto_lint,
            test_cmd=self.test_cmd,
            auto_test=self.auto_test,
        )

    def fmt_system_prompt(self, prompt):
        return self.message_formatter.fmt_system_prompt(
            prompt,
            self.fence,
            self.get_user_language,
            self.get_platform_info,
            self.suggest_shell_commands,
        )

    def format_chat_chunks(self):
        return self.message_formatter.format_chat_chunks(
            self.choose_fence,
            self.fence,
            self.get_user_language,
            self.get_platform_info,
            self.suggest_shell_commands,
            self.done_messages,
            self.get_repo_messages,
            self.get_readonly_files_messages,
            self.get_chat_files_messages,
            self.cur_messages,
            self.summarize_end,
            self.add_cache_headers,
        )

    def format_messages(self):
        return self.message_formatter.format_messages(
            self.format_chat_chunks, self.add_cache_headers
        )

    def warm_cache(self, chunks):
        if not self.add_cache_headers:
            return
        if not self.num_cache_warming_pings:
            return
        if not self.ok_to_warm_cache:
            return

        delay = 5 * 60 - 5
        delay = float(os.environ.get("AIDER_CACHE_KEEPALIVE_DELAY", delay))
        self.next_cache_warm = time.time() + delay
        self.warming_pings_left = self.num_cache_warming_pings
        self.cache_warming_chunks = chunks

        if self.cache_warming_thread:
            return

        def warm_cache_worker():
            while self.ok_to_warm_cache:
                time.sleep(1)
                if self.warming_pings_left <= 0:
                    continue
                now = time.time()
                if now < self.next_cache_warm:
                    continue

                self.warming_pings_left -= 1
                self.next_cache_warm = time.time() + delay

                kwargs = dict(self.main_model.extra_params) or dict()
                kwargs["max_tokens"] = 1

                try:
                    completion = litellm.completion(
                        model=self.main_model.name,
                        messages=self.cache_warming_chunks.cacheable_messages(),
                        stream=False,
                        **kwargs,
                    )
                except Exception as err:
                    self.io.tool_warning(f"Cache warming error: {str(err)}")
                    continue

                cache_hit_tokens = getattr(
                    completion.usage, "prompt_cache_hit_tokens", 0
                ) or getattr(completion.usage, "cache_read_input_tokens", 0)

                if self.verbose:
                    self.io.tool_output(f"Warmed {format_tokens(cache_hit_tokens)} cached tokens.")

        self.cache_warming_thread = threading.Timer(0, warm_cache_worker)
        self.cache_warming_thread.daemon = True
        self.cache_warming_thread.start()

        return chunks

    def check_tokens(self, messages):
        return self.token_calculator.check_tokens(messages)

    def send_message(self, inp):
        self.event("message_send_starting")

        # Notify IO that LLM processing is starting
        self.io.llm_started()

        self.cur_messages += [
            dict(role="user", content=inp),
        ]

        chunks = self.format_messages()
        messages = chunks.all_messages()
        if not self.check_tokens(messages):
            return
        self.warm_cache(chunks)

        if self.verbose:
            utils.show_messages(messages, functions=self.functions)

        self.multi_response_content = ""
        if self.show_pretty():
            self.waiting_spinner = WaitingSpinner("Waiting for " + self.main_model.name)
            self.waiting_spinner.start()
            if self.stream:
                self.mdstream = self.io.get_assistant_mdstream()
            else:
                self.mdstream = None
        else:
            self.mdstream = None

        retry_delay = 0.125

        litellm_ex = LiteLLMExceptions()

        self.usage_report = None
        exhausted = False
        interrupted = False
        try:
            while True:
                try:
                    yield from self.send(messages, functions=self.functions)
                    break
                except litellm_ex.exceptions_tuple() as err:
                    ex_info = litellm_ex.get_ex_info(err)

                    if ex_info.name == "ContextWindowExceededError":
                        exhausted = True
                        break

                    should_retry = ex_info.retry
                    if should_retry:
                        retry_delay *= 2
                        if retry_delay > RETRY_TIMEOUT:
                            should_retry = False

                    if not should_retry:
                        self.mdstream = None
                        self.check_and_open_urls(err, ex_info.description)
                        break

                    err_msg = str(err)
                    if ex_info.description:
                        self.io.tool_warning(err_msg)
                        self.io.tool_error(ex_info.description)
                    else:
                        self.io.tool_error(err_msg)

                    self.io.tool_output(f"Retrying in {retry_delay:.1f} seconds...")
                    time.sleep(retry_delay)
                    continue
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except FinishReasonLength:
                    # We hit the output limit!
                    if not self.main_model.info.get("supports_assistant_prefill"):
                        exhausted = True
                        break

                    self.multi_response_content = self.get_multi_response_content_in_progress()

                    if messages[-1]["role"] == "assistant":
                        messages[-1]["content"] = self.multi_response_content
                    else:
                        messages.append(
                            dict(role="assistant", content=self.multi_response_content, prefix=True)
                        )
                except Exception as err:
                    self.mdstream = None
                    lines = traceback.format_exception(type(err), err, err.__traceback__)
                    self.io.tool_warning("".join(lines))
                    self.io.tool_error(str(err))
                    self.event("message_send_exception", exception=str(err))
                    return
        finally:
            if self.mdstream:
                self.live_incremental_response(True)
                self.mdstream = None

            # Ensure any waiting spinner is stopped
            self._stop_waiting_spinner()

            self.partial_response_content = self.get_multi_response_content_in_progress(True)
            self.remove_reasoning_content()
            self.multi_response_content = ""

        ###
        # print()
        # print("=" * 20)
        # dump(self.partial_response_content)

        self.io.tool_output()

        self.show_usage_report()

        self.add_assistant_reply_to_cur_messages()

        if exhausted:
            if self.cur_messages and self.cur_messages[-1]["role"] == "user":
                self.cur_messages += [
                    dict(
                        role="assistant",
                        content="FinishReasonLength exception: you sent too many tokens",
                    ),
                ]

            self.show_exhausted_error()
            self.num_exhausted_context_windows += 1
            return

        if self.partial_response_function_call:
            args = self.parse_partial_args()
            if args:
                content = args.get("explanation") or ""
            else:
                content = ""
        elif self.partial_response_content:
            content = self.partial_response_content
        else:
            content = ""

        if not interrupted:
            add_rel_files_message = self.check_for_file_mentions(content)
            if add_rel_files_message:
                if self.reflected_message:
                    self.reflected_message += "\n\n" + add_rel_files_message
                else:
                    self.reflected_message = add_rel_files_message
                return

            try:
                if self.reply_completed():
                    return
            except KeyboardInterrupt:
                interrupted = True

        if interrupted:
            if self.cur_messages and self.cur_messages[-1]["role"] == "user":
                self.cur_messages[-1]["content"] += "\n^C KeyboardInterrupt"
            else:
                self.cur_messages += [dict(role="user", content="^C KeyboardInterrupt")]
            self.cur_messages += [
                dict(role="assistant", content="I see that you interrupted my previous reply.")
            ]
            return

        edited = self.apply_updates()

        if edited:
            self.aider_edited_files.update(edited)
            saved_message = self.auto_commit(edited)

            if not saved_message and hasattr(self.gpt_prompts, "files_content_gpt_edits_no_repo"):
                saved_message = self.gpt_prompts.files_content_gpt_edits_no_repo

            self.move_back_cur_messages(saved_message)

        if self.reflected_message:
            return

        if edited and self.auto_lint:
            lint_errors = self.lint_edited(edited)
            self.auto_commit(edited, context="Ran the linter")
            self.lint_outcome = not lint_errors
            if lint_errors:
                ok = self.io.confirm_ask("Attempt to fix lint errors?")
                if ok:
                    self.reflected_message = lint_errors
                    return

        shared_output = self.run_shell_commands()
        if shared_output:
            self.cur_messages += [
                dict(role="user", content=shared_output),
                dict(role="assistant", content="Ok"),
            ]

        if edited and self.auto_test:
            test_errors = self.commands.cmd_test(self.test_cmd)
            self.test_outcome = not test_errors
            if test_errors:
                ok = self.io.confirm_ask("Attempt to fix test errors?")
                if ok:
                    self.reflected_message = test_errors
                    return

    def reply_completed(self):
        pass

    def show_exhausted_error(self):
        output_tokens = 0
        if self.partial_response_content:
            output_tokens = self.main_model.token_count(self.partial_response_content)
        max_output_tokens = self.main_model.info.get("max_output_tokens") or 0

        input_tokens = self.main_model.token_count(self.format_messages().all_messages())
        max_input_tokens = self.main_model.info.get("max_input_tokens") or 0

        total_tokens = input_tokens + output_tokens

        fudge = 0.7

        out_err = ""
        if output_tokens >= max_output_tokens * fudge:
            out_err = " -- possibly exceeded output limit!"

        inp_err = ""
        if input_tokens >= max_input_tokens * fudge:
            inp_err = " -- possibly exhausted context window!"

        tot_err = ""
        if total_tokens >= max_input_tokens * fudge:
            tot_err = " -- possibly exhausted context window!"

        res = ["", ""]
        res.append(f"Model {self.main_model.name} has hit a token limit!")
        res.append("Token counts below are approximate.")
        res.append("")
        res.append(f"Input tokens: ~{input_tokens:,} of {max_input_tokens:,}{inp_err}")
        res.append(f"Output tokens: ~{output_tokens:,} of {max_output_tokens:,}{out_err}")
        res.append(f"Total tokens: ~{total_tokens:,} of {max_input_tokens:,}{tot_err}")

        if output_tokens >= max_output_tokens:
            res.append("")
            res.append("To reduce output tokens:")
            res.append("- Ask for smaller changes in each request.")
            res.append("- Break your code into smaller source files.")
            if "diff" not in self.main_model.edit_format:
                res.append("- Use a stronger model that can return diffs.")

        if input_tokens >= max_input_tokens or total_tokens >= max_input_tokens:
            res.append("")
            res.append("To reduce input tokens:")
            res.append("- Use /tokens to see token usage.")
            res.append("- Use /drop to remove unneeded files from the chat session.")
            res.append("- Use /clear to clear the chat history.")
            res.append("- Break your code into smaller source files.")

        res = "".join([line + "\n" for line in res])
        self.io.tool_error(res)
        self.io.offer_url(urls.token_limits)

    def lint_edited(self, fnames):
        return self.lint_test_manager.lint_edited(fnames, self.abs_root_path)

    def __del__(self):
        """Cleanup when the Coder object is destroyed."""
        self.ok_to_warm_cache = False

    def add_assistant_reply_to_cur_messages(self):
        if self.partial_response_content:
            self.cur_messages += [dict(role="assistant", content=self.partial_response_content)]
        if self.partial_response_function_call:
            self.cur_messages += [
                dict(
                    role="assistant",
                    content=None,
                    function_call=self.partial_response_function_call,
                )
            ]

    def get_file_mentions(self, content, ignore_current=False):
        words = set(word for word in content.split())

        # drop sentence punctuation from the end
        words = set(word.rstrip(",.!;:?") for word in words)

        # strip away all kinds of quotes
        quotes = "\"'`*_"
        words = set(word.strip(quotes) for word in words)

        if ignore_current:
            addable_rel_fnames = self.get_all_relative_files()
            existing_basenames = {}
        else:
            addable_rel_fnames = self.get_addable_relative_files()

            # Get basenames of files already in chat or read-only
            existing_basenames = {os.path.basename(f) for f in self.get_inchat_relative_files()} | {
                os.path.basename(self.get_rel_fname(f)) for f in self.abs_read_only_fnames
            }

        mentioned_rel_fnames = set()
        fname_to_rel_fnames = {}
        for rel_fname in addable_rel_fnames:
            normalized_rel_fname = rel_fname.replace("\\", "/")
            normalized_words = set(word.replace("\\", "/") for word in words)
            if normalized_rel_fname in normalized_words:
                mentioned_rel_fnames.add(rel_fname)

            fname = os.path.basename(rel_fname)

            # Don't add basenames that could be plain words like "run" or "make"
            if "/" in fname or "\\" in fname or "." in fname or "_" in fname or "-" in fname:
                if fname not in fname_to_rel_fnames:
                    fname_to_rel_fnames[fname] = []
                fname_to_rel_fnames[fname].append(rel_fname)

        for fname, rel_fnames in fname_to_rel_fnames.items():
            # If the basename is already in chat, don't add based on a basename mention
            if fname in existing_basenames:
                continue
            # If the basename mention is unique among addable files and present in the text
            if len(rel_fnames) == 1 and fname in words:
                mentioned_rel_fnames.add(rel_fnames[0])

        return mentioned_rel_fnames

    def check_for_file_mentions(self, content):
        mentioned_rel_fnames = self.get_file_mentions(content)

        new_mentions = mentioned_rel_fnames - self.ignore_mentions

        if not new_mentions:
            return

        added_fnames = []
        group = ConfirmGroup(new_mentions)
        for rel_fname in sorted(new_mentions):
            if self.io.confirm_ask(
                "Add file to the chat?", subject=rel_fname, group=group, allow_never=True
            ):
                self.add_rel_fname(rel_fname)
                added_fnames.append(rel_fname)
            else:
                self.ignore_mentions.add(rel_fname)

        if added_fnames:
            return prompts.added_files.format(fnames=", ".join(added_fnames))

    def send(self, messages, model=None, functions=None):
        self.got_reasoning_content = False
        self.ended_reasoning_content = False

        if not model:
            model = self.main_model

        self.partial_response_content = ""
        self.partial_response_function_call = dict()

        self.io.log_llm_history("TO LLM", format_messages(messages))

        completion = None
        try:
            hash_object, completion = model.send_completion(
                messages,
                functions,
                self.stream,
                self.temperature,
            )
            self.chat_completion_call_hashes.append(hash_object.hexdigest())

            if self.stream:
                yield from self.show_send_output_stream(completion)
            else:
                self.show_send_output(completion)

            # Calculate costs for successful responses
            self.calculate_and_show_tokens_and_cost(messages, completion)

        except LiteLLMExceptions().exceptions_tuple() as err:
            ex_info = LiteLLMExceptions().get_ex_info(err)
            if ex_info.name == "ContextWindowExceededError":
                # Still calculate costs for context window errors
                self.calculate_and_show_tokens_and_cost(messages, completion)
            raise
        except KeyboardInterrupt as kbi:
            self.keyboard_interrupt()
            raise kbi
        finally:
            self.io.log_llm_history(
                "LLM RESPONSE",
                format_content("ASSISTANT", self.partial_response_content),
            )

            if self.partial_response_content:
                self.io.ai_output(self.partial_response_content)
            elif self.partial_response_function_call:
                # TODO: push this into subclasses
                args = self.parse_partial_args()
                if args:
                    self.io.ai_output(json.dumps(args, indent=4))

    def show_send_output(self, completion):
        # Stop spinner once we have a response
        self._stop_waiting_spinner()

        if self.verbose:
            print(completion)

        if not completion.choices:
            self.io.tool_error(str(completion))
            return

        show_func_err = None
        show_content_err = None
        try:
            if completion.choices[0].message.tool_calls:
                self.partial_response_function_call = (
                    completion.choices[0].message.tool_calls[0].function
                )
        except AttributeError as func_err:
            show_func_err = func_err

        try:
            reasoning_content = completion.choices[0].message.reasoning_content
        except AttributeError:
            try:
                reasoning_content = completion.choices[0].message.reasoning
            except AttributeError:
                reasoning_content = None

        try:
            self.partial_response_content = completion.choices[0].message.content or ""
        except AttributeError as content_err:
            show_content_err = content_err

        resp_hash = dict(
            function_call=str(self.partial_response_function_call),
            content=self.partial_response_content,
        )
        resp_hash = hashlib.sha1(json.dumps(resp_hash, sort_keys=True).encode())
        self.chat_completion_response_hashes.append(resp_hash.hexdigest())

        if show_func_err and show_content_err:
            self.io.tool_error(show_func_err)
            self.io.tool_error(show_content_err)
            raise Exception("No data found in LLM response!")

        show_resp = self.render_incremental_response(True)

        if reasoning_content:
            formatted_reasoning = format_reasoning_content(
                reasoning_content, self.reasoning_tag_name
            )
            show_resp = formatted_reasoning + show_resp

        show_resp = replace_reasoning_tags(show_resp, self.reasoning_tag_name)

        self.io.assistant_output(show_resp, pretty=self.show_pretty())

        if (
            hasattr(completion.choices[0], "finish_reason")
            and completion.choices[0].finish_reason == "length"
        ):
            raise FinishReasonLength()

    def show_send_output_stream(self, completion):
        received_content = False

        for chunk in completion:
            if len(chunk.choices) == 0:
                continue

            if (
                hasattr(chunk.choices[0], "finish_reason")
                and chunk.choices[0].finish_reason == "length"
            ):
                raise FinishReasonLength()

            try:
                func = chunk.choices[0].delta.function_call
                # dump(func)
                for k, v in func.items():
                    if k in self.partial_response_function_call:
                        self.partial_response_function_call[k] += v
                    else:
                        self.partial_response_function_call[k] = v
                received_content = True
            except AttributeError:
                pass

            text = ""

            try:
                reasoning_content = chunk.choices[0].delta.reasoning_content
            except AttributeError:
                try:
                    reasoning_content = chunk.choices[0].delta.reasoning
                except AttributeError:
                    reasoning_content = None

            if reasoning_content:
                if not self.got_reasoning_content:
                    text += f"<{REASONING_TAG}>\n\n"
                text += reasoning_content
                self.got_reasoning_content = True
                received_content = True

            try:
                content = chunk.choices[0].delta.content
                if content:
                    if self.got_reasoning_content and not self.ended_reasoning_content:
                        text += f"\n\n</{self.reasoning_tag_name}>\n\n"
                        self.ended_reasoning_content = True

                    text += content
                    received_content = True
            except AttributeError:
                pass

            if received_content:
                self._stop_waiting_spinner()
            self.partial_response_content += text

            if self.show_pretty():
                self.live_incremental_response(False)
            elif text:
                # Apply reasoning tag formatting
                text = replace_reasoning_tags(text, self.reasoning_tag_name)
                try:
                    sys.stdout.write(text)
                except UnicodeEncodeError:
                    # Safely encode and decode the text
                    safe_text = text.encode(sys.stdout.encoding, errors="backslashreplace").decode(
                        sys.stdout.encoding
                    )
                    sys.stdout.write(safe_text)
                sys.stdout.flush()
                yield text

        if not received_content:
            self.io.tool_warning("Empty response received from LLM. Check your provider account?")

    def live_incremental_response(self, final):
        show_resp = self.render_incremental_response(final)
        # Apply any reasoning tag formatting
        show_resp = replace_reasoning_tags(show_resp, self.reasoning_tag_name)
        self.mdstream.update(show_resp, final=final)

    def render_incremental_response(self, final):
        return self.get_multi_response_content_in_progress()

    def remove_reasoning_content(self):
        """Remove reasoning content from the model's response."""

        self.partial_response_content = remove_reasoning_content(
            self.partial_response_content,
            self.reasoning_tag_name,
        )

    def calculate_and_show_tokens_and_cost(self, messages, completion=None):
        self.token_calculator.calculate_and_show_tokens_and_cost(messages, completion)
        # Update local references for backwards compatibility
        self.usage_report = self.token_calculator.usage_report
        self.message_tokens_sent = self.token_calculator.message_tokens_sent
        self.message_tokens_received = self.token_calculator.message_tokens_received

    def compute_costs_from_tokens(
        self, prompt_tokens, completion_tokens, cache_write_tokens, cache_hit_tokens
    ):
        return self.token_calculator.compute_costs_from_tokens(
            prompt_tokens, completion_tokens, cache_write_tokens, cache_hit_tokens
        )

    def show_usage_report(self):
        self.token_calculator.show_usage_report(
            event_callback=self.event, edit_format=self.edit_format
        )
        # Update local references for backwards compatibility
        self.total_cost = self.token_calculator.total_cost
        self.total_tokens_sent = self.token_calculator.total_tokens_sent
        self.total_tokens_received = self.token_calculator.total_tokens_received
        self.message_cost = self.token_calculator.message_cost
        self.message_tokens_sent = self.token_calculator.message_tokens_sent
        self.message_tokens_received = self.token_calculator.message_tokens_received

    def get_multi_response_content_in_progress(self, final=False):
        cur = self.multi_response_content or ""
        new = self.partial_response_content or ""

        if new.rstrip() != new and not final:
            new = new.rstrip()

        return cur + new

    def get_rel_fname(self, fname):
        return self.file_manager.get_rel_fname(fname)

    def get_inchat_relative_files(self):
        return self.file_manager.get_inchat_relative_files()

    def is_file_safe(self, fname):
        return self.file_manager.is_file_safe(fname)

    def get_all_relative_files(self):
        if self.repo:
            files = self.repo.get_tracked_files()
        else:
            files = self.get_inchat_relative_files()

        # This is quite slow in large repos
        # files = [fname for fname in files if self.is_file_safe(fname)]

        return sorted(set(files))

    def get_all_abs_files(self):
        files = self.get_all_relative_files()
        files = [self.abs_root_path(path) for path in files]
        return files

    def get_addable_relative_files(self):
        all_files = set(self.get_all_relative_files())
        inchat_files = set(self.get_inchat_relative_files())
        read_only_files = set(self.get_rel_fname(fname) for fname in self.abs_read_only_fnames)
        return all_files - inchat_files - read_only_files

    def check_for_dirty_commit(self, path):
        self.commit_manager.check_for_dirty_commit(path, self.dirty_commits)

    def allowed_to_edit(self, path):
        full_path = self.abs_root_path(path)
        if self.repo:
            need_to_add = not self.repo.path_in_repo(path)
        else:
            need_to_add = False

        if full_path in self.abs_fnames:
            self.check_for_dirty_commit(path)
            return True

        if self.repo and self.repo.git_ignored_file(path):
            self.io.tool_warning(f"Skipping edits to {path} that matches gitignore spec.")
            return

        if not Path(full_path).exists():
            if not self.io.confirm_ask("Create new file?", subject=path):
                self.io.tool_output(f"Skipping edits to {path}")
                return

            if not self.dry_run:
                if not utils.touch_file(full_path):
                    self.io.tool_error(f"Unable to create {path}, skipping edits.")
                    return

                # Seems unlikely that we needed to create the file, but it was
                # actually already part of the repo.
                # But let's only add if we need to, just to be safe.
                if need_to_add:
                    self.repo.repo.git.add(full_path)

            self.abs_fnames.add(full_path)
            self.check_added_files()
            return True

        if not self.io.confirm_ask(
            "Allow edits to file that has not been added to the chat?",
            subject=path,
        ):
            self.io.tool_output(f"Skipping edits to {path}")
            return

        if need_to_add:
            self.repo.repo.git.add(full_path)

        self.abs_fnames.add(full_path)
        self.check_added_files()
        self.check_for_dirty_commit(path)

        return True

    warning_given = False

    def check_added_files(self):
        if self.warning_given:
            return

        warn_number_of_files = 4
        warn_number_of_tokens = 20 * 1024

        num_files = len(self.abs_fnames)
        if num_files < warn_number_of_files:
            return

        tokens = 0
        for fname in self.abs_fnames:
            if is_image_file(fname):
                continue
            content = self.io.read_text(fname)
            tokens += self.main_model.token_count(content)

        if tokens < warn_number_of_tokens:
            return

        self.io.tool_warning("Warning: it's best to only add files that need changes to the chat.")
        self.io.tool_warning(urls.edit_errors)
        self.warning_given = True

    def prepare_to_edit(self, edits):
        res = []
        seen = dict()

        self.need_commit_before_edits = set()

        for edit in edits:
            path = edit[0]
            if path is None:
                res.append(edit)
                continue
            if path == "python":
                dump(edits)
            if path in seen:
                allowed = seen[path]
            else:
                allowed = self.allowed_to_edit(path)
                seen[path] = allowed

            if allowed:
                res.append(edit)

        self.dirty_commit()
        self.need_commit_before_edits = set()

        return res

    def apply_updates(self):
        edited = set()
        try:
            edits = self.get_edits()
            edits = self.apply_edits_dry_run(edits)
            edits = self.prepare_to_edit(edits)
            edited = set(edit[0] for edit in edits)

            self.apply_edits(edits)
        except ValueError as err:
            self.num_malformed_responses += 1

            err = err.args[0]

            self.io.tool_error("The LLM did not conform to the edit format.")
            self.io.tool_output(urls.edit_errors)
            self.io.tool_output()
            self.io.tool_output(str(err))

            self.reflected_message = str(err)
            return edited

        except ANY_GIT_ERROR as err:
            self.io.tool_error(str(err))
            return edited
        except Exception as err:
            self.io.tool_error("Exception while updating files:")
            self.io.tool_error(str(err), strip=False)

            traceback.print_exc()

            self.reflected_message = str(err)
            return edited

        for path in edited:
            if self.dry_run:
                self.io.tool_output(f"Did not apply edit to {path} (--dry-run)")
            else:
                self.io.tool_output(f"Applied edit to {path}")

        return edited

    def parse_partial_args(self):
        # dump(self.partial_response_function_call)

        data = self.partial_response_function_call.get("arguments")
        if not data:
            return

        try:
            return json.loads(data)
        except JSONDecodeError:
            pass

        try:
            return json.loads(data + "]}")
        except JSONDecodeError:
            pass

        try:
            return json.loads(data + "}]}")
        except JSONDecodeError:
            pass

        try:
            return json.loads(data + '"}]}')
        except JSONDecodeError:
            pass

    # commits...

    def get_context_from_history(self, history):
        return self.commit_manager.get_context_from_history(history)

    def auto_commit(self, edited, context=None):
        result = self.commit_manager.auto_commit(
            edited, context, self.cur_messages,
            self.auto_commits, self.dry_run, self.show_diffs
        )
        # Sync state back to coder
        self.last_aider_commit_hash = self.commit_manager.last_aider_commit_hash
        self.aider_commit_hashes = self.commit_manager.aider_commit_hashes
        return result

    def show_auto_commit_outcome(self, res):
        self.commit_manager.show_auto_commit_outcome(res, self.show_diffs)
        # Sync state back to coder
        self.last_aider_commit_hash = self.commit_manager.last_aider_commit_hash
        self.aider_commit_hashes = self.commit_manager.aider_commit_hashes

    def show_undo_hint(self):
        self.commit_manager.show_undo_hint(self.commit_before_message)

    def dirty_commit(self):
        result = self.commit_manager.dirty_commit(self.dirty_commits)
        self.need_commit_before_edits = self.commit_manager.need_commit_before_edits
        return result

    def get_edits(self, mode="update"):
        return []

    def apply_edits(self, edits):
        return

    def apply_edits_dry_run(self, edits):
        return edits

    def run_shell_commands(self):
        return self.shell_command_manager.run_shell_commands(self.suggest_shell_commands)

    def handle_shell_commands(self, commands_str, group):
        return self.shell_command_manager.handle_shell_commands(commands_str, group)
